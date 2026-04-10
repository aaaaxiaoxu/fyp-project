from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .zep_tools import ZepToolsService

ExplorerEventName = Literal["status", "tool_call", "tool_result", "answer_chunk", "final_answer", "error"]


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


class ExplorerAgent:
    def __init__(
        self,
        *,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        tools: ZepToolsService,
    ) -> None:
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        self.tools = tools

    def ask(self, question: str) -> ExplorerRunResult:
        tool_name, tool_result = self._run_search_tool(question)
        answer = self._compose_answer(question, tool_name, tool_result)
        return self._to_result(
            mode="ask",
            question=question,
            answer=answer,
            tool_name=tool_name,
            tool_result=tool_result,
        )

    def interview(self, agent_id: int, question: str) -> ExplorerRunResult:
        result = self.tools.interview_agent(agent_id, question)
        answer = result.answer
        return self._to_result(
            mode="interview",
            question=question,
            answer=answer,
            tool_name="interview_agents",
            tool_result=result.to_dict(),
            agent_id=agent_id,
        )

    def _run_search_tool(self, question: str) -> tuple[str, dict[str, Any]]:
        lower = question.lower()
        if any(token in lower for token in ("全貌", "overview", "panorama", "整体", "all")):
            result = self.tools.panorama_search(question)
            return "panorama_search", result.to_dict()
        if any(token in lower for token in ("分析", "影响", "原因", "why", "impact", "cause")):
            result = self.tools.insight_forge(question, simulation_requirement=self.simulation_requirement)
            return "insight_forge", result.to_dict()
        result = self.tools.quick_search(question)
        return "quick_search", result.to_dict()

    def _compose_answer(self, question: str, tool_name: str, tool_result: dict[str, Any]) -> str:
        facts = self._facts_from_tool_result(tool_result)
        if not facts:
            return (
                f"I could not find a directly matching graph fact for '{question}'. "
                "The Explorer can still inspect the simulation graph, but this answer should be treated as low confidence."
            )

        quoted_facts = "\n".join(f'> "{fact}"' for fact in facts[:4])
        return (
            f"Based on `{tool_name}` over graph `{self.graph_id}`, the simulation evidence points to these facts:\n"
            f"{quoted_facts}\n\n"
            f"Answer: {self._synthesize_from_facts(question, facts)}"
        )

    def _synthesize_from_facts(self, question: str, facts: list[str]) -> str:
        lead = facts[0]
        if len(facts) == 1:
            return f"For '{question}', the strongest available fact is: {lead}"
        return (
            f"For '{question}', the strongest available fact is: {lead} "
            f"Related facts provide additional context across {len(facts)} retrieved graph statements."
        )

    def _facts_from_tool_result(self, tool_result: dict[str, Any]) -> list[str]:
        facts: list[str] = []
        for key in ("facts", "active_facts", "historical_facts"):
            for item in tool_result.get(key, []) or []:
                fact = str(item).strip()
                if fact and fact not in facts:
                    facts.append(fact)
        return facts

    def _to_result(
        self,
        *,
        mode: Literal["ask", "interview"],
        question: str,
        answer: str,
        tool_name: str,
        tool_result: dict[str, Any],
        agent_id: int | None = None,
    ) -> ExplorerRunResult:
        base = {
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "mode": mode,
        }
        events = [
            ExplorerEvent("status", {**base, "status": "started"}),
            ExplorerEvent(
                "tool_call",
                {
                    **base,
                    "tool_name": tool_name,
                    "parameters": {"question": question, **({"agent_id": agent_id} if agent_id is not None else {})},
                },
            ),
            ExplorerEvent(
                "tool_result",
                {
                    **base,
                    "tool_name": tool_name,
                    "result": tool_result,
                },
            ),
        ]
        for chunk in self._chunk_answer(answer):
            events.append(ExplorerEvent("answer_chunk", {**base, "chunk": chunk}))
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

    def _chunk_answer(self, answer: str, *, chunk_size: int = 280) -> list[str]:
        if len(answer) <= chunk_size:
            return [answer]

        chunks: list[str] = []
        cursor = 0
        while cursor < len(answer):
            chunks.append(answer[cursor : cursor + chunk_size])
            cursor += chunk_size
        return chunks
