from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from ..utils.llm_client import LLMClient
from .zep_tools import ZepToolsService

ExplorerEventName = Literal["status", "tool_call", "tool_result", "answer_chunk", "final_answer", "error"]
ExplorerMode = Literal["ask", "interview"]
ExplorerToolName = Literal["quick_search", "panorama_search", "insight_forge", "interview_agents"]

_ALLOWED_SEARCH_TOOLS: tuple[ExplorerToolName, ...] = ("quick_search", "panorama_search", "insight_forge")
_MAX_OBSERVATION_CHARS = 7000


@dataclass(frozen=True, slots=True)
class ExplorerEvent:
    event: ExplorerEventName
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ExplorerRunResult:
    events: list[ExplorerEvent]
    answer: str
    tool_name: str
    tool_result: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolObservation:
    tool_name: ExplorerToolName
    tool_input: dict[str, Any]
    tool_result: dict[str, Any]


class ExplorerAgent:
    def __init__(
        self,
        *,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        tools: ZepToolsService,
        llm_client: LLMClient | None = None,
        max_tool_steps: int = 3,
    ) -> None:
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        self.tools = tools
        self._llm_client = llm_client
        self.max_tool_steps = max(1, min(max_tool_steps, 5))

    def ask(self, question: str) -> ExplorerRunResult:
        return self._run(mode="ask", question=question)

    def interview(self, agent_id: int, question: str) -> ExplorerRunResult:
        return self._run(mode="interview", question=question, agent_id=agent_id)

    @property
    def _client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _run(
        self,
        *,
        mode: ExplorerMode,
        question: str,
        agent_id: int | None = None,
    ) -> ExplorerRunResult:
        base = self._base_event_data(mode)
        events: list[ExplorerEvent] = [ExplorerEvent("status", {**base, "status": "started"})]
        observations: list[ToolObservation] = []
        final_answer = ""

        if mode == "interview":
            if agent_id is None:
                raise ValueError("agent_id is required for interview mode")
            observation = self._execute_tool(
                "interview_agents",
                {"agent_id": agent_id, "question": question},
                question=question,
                agent_id=agent_id,
            )
            observations.append(observation)
            self._append_tool_events(events, base, observation, step=1)
            final_answer = self._generate_final_answer(mode=mode, question=question, observations=observations, agent_id=agent_id)
            return self._finalize_result(
                events=events,
                base=base,
                answer=final_answer,
                observations=observations,
                agent_id=agent_id,
            )

        for step in range(1, self.max_tool_steps + 1):
            decision = self._plan_next_step(question=question, observations=observations)
            action = str(decision.get("action") or "tool").strip().lower()

            if action == "final" and observations:
                final_answer = str(decision.get("answer") or "").strip()
                if final_answer:
                    break
            if action == "final" and not observations:
                decision = {"tool_name": "quick_search", "tool_input": {"query": question, "limit": 10}}

            tool_name, tool_input = self._tool_from_decision(decision, question)
            observation = self._execute_tool(tool_name, tool_input, question=question, agent_id=agent_id)
            observations.append(observation)
            self._append_tool_events(events, base, observation, step=step)

        if not final_answer:
            final_answer = self._generate_final_answer(mode=mode, question=question, observations=observations, agent_id=agent_id)

        return self._finalize_result(
            events=events,
            base=base,
            answer=final_answer,
            observations=observations,
            agent_id=agent_id,
        )

    def _plan_next_step(self, *, question: str, observations: list[ToolObservation]) -> dict[str, Any]:
        return self._client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Explorer Agent for a social simulation. Use tools to answer with evidence from "
                        "the Zep graph and OASIS simulation artifacts. Return only a JSON object. Do not reveal "
                        "hidden chain-of-thought. Use at least one tool before finalizing.\n\n"
                        "Available tools:\n"
                        "- quick_search: targeted lookup of graph facts and entity summaries.\n"
                        "- panorama_search: broad overview across active and historical graph facts.\n"
                        "- insight_forge: causal or impact analysis using sub-queries and relationship chains.\n\n"
                        "Schema for a tool call:\n"
                        "{\"action\":\"tool\",\"tool_name\":\"quick_search|panorama_search|insight_forge\","
                        "\"tool_input\":{\"query\":\"...\",\"limit\":10},\"rationale\":\"brief user-visible reason\"}\n"
                        "Schema for final answer after observations exist:\n"
                        "{\"action\":\"final\",\"answer\":\"...\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Simulation ID: {self.simulation_id}\n"
                        f"Graph ID: {self.graph_id}\n"
                        f"Simulation requirement: {self.simulation_requirement}\n"
                        f"User question: {question}\n\n"
                        f"Tool observations so far:\n{self._observations_for_prompt(observations)}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=900,
        )

    def _tool_from_decision(self, decision: dict[str, Any], question: str) -> tuple[ExplorerToolName, dict[str, Any]]:
        raw_tool_name = str(decision.get("tool_name") or "").strip()
        if raw_tool_name not in _ALLOWED_SEARCH_TOOLS:
            raise ValueError(f"Explorer LLM selected unsupported tool: {raw_tool_name or '<missing>'}")

        raw_input = decision.get("tool_input") or {}
        tool_input = dict(raw_input) if isinstance(raw_input, dict) else {}
        tool_input.setdefault("query", question)
        return raw_tool_name, tool_input  # type: ignore[return-value]

    def _execute_tool(
        self,
        tool_name: ExplorerToolName,
        tool_input: dict[str, Any],
        *,
        question: str,
        agent_id: int | None = None,
    ) -> ToolObservation:
        query = str(tool_input.get("query") or question).strip() or question
        limit = _bounded_int(tool_input.get("limit"), default=10, minimum=1, maximum=50)

        if tool_name == "quick_search":
            result = self.tools.quick_search(query, limit=limit).to_dict()
        elif tool_name == "panorama_search":
            include_expired = _coerce_bool(tool_input.get("include_expired"), default=True)
            result = self.tools.panorama_search(query, include_expired=include_expired, limit=limit).to_dict()
        elif tool_name == "insight_forge":
            max_sub_queries = _bounded_int(tool_input.get("max_sub_queries"), default=4, minimum=1, maximum=8)
            result = self.tools.insight_forge(
                query,
                simulation_requirement=self.simulation_requirement,
                max_sub_queries=max_sub_queries,
                limit=limit,
            ).to_dict()
        elif tool_name == "interview_agents":
            resolved_agent_id = _bounded_int(tool_input.get("agent_id", agent_id), default=-1, minimum=-1, maximum=10_000_000)
            if resolved_agent_id < 0:
                raise ValueError("agent_id is required for interview_agents")
            result = self.tools.interview_agent(resolved_agent_id, str(tool_input.get("question") or question)).to_dict()
        else:
            raise ValueError(f"Unsupported Explorer tool: {tool_name}")

        return ToolObservation(
            tool_name=tool_name,
            tool_input={**tool_input, "query": query},
            tool_result=result,
        )

    def _generate_final_answer(
        self,
        *,
        mode: ExplorerMode,
        question: str,
        observations: list[ToolObservation],
        agent_id: int | None,
    ) -> str:
        if mode == "interview":
            system_prompt = (
                "You are the interviewed simulation agent. Answer in first person using the provided persona, "
                "recent actions, and graph facts. Do not invent facts not present in the observations. If evidence "
                "is thin, say what is uncertain. Do not expose chain-of-thought."
            )
        else:
            system_prompt = (
                "You are Explorer Agent. Answer the user with a concise, evidence-grounded response based on the "
                "tool observations. Cite or paraphrase concrete graph facts and simulation actions. If the tools "
                "did not find enough evidence, say that clearly. Do not expose chain-of-thought."
            )

        return self._client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Mode: {mode}\n"
                        f"Simulation ID: {self.simulation_id}\n"
                        f"Graph ID: {self.graph_id}\n"
                        f"Simulation requirement: {self.simulation_requirement}\n"
                        f"Agent ID: {agent_id if agent_id is not None else 'N/A'}\n"
                        f"Question: {question}\n\n"
                        f"Tool observations:\n{self._observations_for_prompt(observations)}\n\n"
                        "Write the final answer now."
                    ),
                },
            ],
            temperature=0.35,
            max_tokens=1200,
        )

    def _append_tool_events(
        self,
        events: list[ExplorerEvent],
        base: dict[str, Any],
        observation: ToolObservation,
        *,
        step: int,
    ) -> None:
        events.append(
            ExplorerEvent(
                "tool_call",
                {
                    **base,
                    "step": step,
                    "tool_name": observation.tool_name,
                    "parameters": observation.tool_input,
                },
            )
        )
        events.append(
            ExplorerEvent(
                "tool_result",
                {
                    **base,
                    "step": step,
                    "tool_name": observation.tool_name,
                    "result": observation.tool_result,
                },
            )
        )

    def _finalize_result(
        self,
        *,
        events: list[ExplorerEvent],
        base: dict[str, Any],
        answer: str,
        observations: list[ToolObservation],
        agent_id: int | None = None,
    ) -> ExplorerRunResult:
        for chunk in self._chunk_answer(answer):
            events.append(ExplorerEvent("answer_chunk", {**base, "chunk": chunk}))

        tool_name = observations[-1].tool_name if observations else "quick_search"
        tool_result = observations[-1].tool_result if observations else {}
        events.append(
            ExplorerEvent(
                "final_answer",
                {
                    **base,
                    "answer": answer,
                    "tool_name": tool_name,
                    **({"agent_id": agent_id} if agent_id is not None else {}),
                },
            )
        )
        return ExplorerRunResult(events=events, answer=answer, tool_name=tool_name, tool_result=tool_result)

    def _base_event_data(self, mode: ExplorerMode) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "mode": mode,
        }

    def _observations_for_prompt(self, observations: list[ToolObservation]) -> str:
        if not observations:
            return "No tool observations yet."

        chunks = []
        for index, observation in enumerate(observations, start=1):
            chunks.append(
                json.dumps(
                    {
                        "step": index,
                        "tool_name": observation.tool_name,
                        "tool_input": observation.tool_input,
                        "tool_result": observation.tool_result,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        text = "\n".join(chunks)
        if len(text) > _MAX_OBSERVATION_CHARS:
            return f"{text[:_MAX_OBSERVATION_CHARS]}\n...[truncated]..."
        return text

    def _chunk_answer(self, answer: str, *, chunk_size: int = 280) -> list[str]:
        if len(answer) <= chunk_size:
            return [answer]

        chunks: list[str] = []
        cursor = 0
        while cursor < len(answer):
            chunks.append(answer[cursor : cursor + chunk_size])
            cursor += chunk_size
        return chunks


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default
