from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    facts: list[str]
    edges: list[dict[str, Any]]
    nodes: list[dict[str, Any]]

    @property
    def total_count(self) -> int:
        return len(self.facts) + len(self.nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "facts": list(self.facts),
            "edges": [dict(edge) for edge in self.edges],
            "nodes": [dict(node) for node in self.nodes],
            "total_count": self.total_count,
        }

    def to_text(self) -> str:
        lines = [f"Search query: {self.query}", f"Facts found: {len(self.facts)}"]
        for index, fact in enumerate(self.facts, start=1):
            lines.append(f"{index}. {fact}")
        if self.nodes:
            lines.append("Entities:")
            for node in self.nodes:
                lines.append(f"- {node.get('name', 'Unknown')}: {node.get('summary', '')}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class PanoramaResult:
    query: str
    active_facts: list[str]
    historical_facts: list[str]
    nodes: list[dict[str, Any]]
    total_edges: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "active_facts": list(self.active_facts),
            "historical_facts": list(self.historical_facts),
            "nodes": [dict(node) for node in self.nodes],
            "total_nodes": len(self.nodes),
            "total_edges": self.total_edges,
        }

    def to_text(self) -> str:
        lines = [
            f"Panorama query: {self.query}",
            f"Graph scope: {len(self.nodes)} nodes, {self.total_edges} edges",
            "Active facts:",
        ]
        for index, fact in enumerate(self.active_facts, start=1):
            lines.append(f"{index}. {fact}")
        if self.historical_facts:
            lines.append("Historical facts:")
            for index, fact in enumerate(self.historical_facts, start=1):
                lines.append(f"{index}. {fact}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class InsightForgeResult:
    query: str
    simulation_requirement: str
    sub_queries: list[str]
    facts: list[str]
    entities: list[dict[str, Any]]
    relationship_chains: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": list(self.sub_queries),
            "facts": list(self.facts),
            "entities": [dict(entity) for entity in self.entities],
            "relationship_chains": list(self.relationship_chains),
            "total_facts": len(self.facts),
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationship_chains),
        }

    def to_text(self) -> str:
        lines = [
            f"Insight query: {self.query}",
            f"Simulation requirement: {self.simulation_requirement}",
            "Sub-queries:",
            *[f"- {query}" for query in self.sub_queries],
            "Relevant facts:",
        ]
        for index, fact in enumerate(self.facts, start=1):
            lines.append(f"{index}. {fact}")
        if self.relationship_chains:
            lines.append("Relationship chains:")
            lines.extend(f"- {chain}" for chain in self.relationship_chains)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AgentInterviewResult:
    agent_id: int
    agent_name: str
    question: str
    answer: str
    profile: dict[str, Any]
    facts: list[str] = field(default_factory=list)
    recent_actions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "question": self.question,
            "answer": self.answer,
            "profile": dict(self.profile),
            "facts": list(self.facts),
            "recent_actions": [dict(action) for action in self.recent_actions],
        }

    def to_text(self) -> str:
        lines = [
            f"Interview agent: {self.agent_name} ({self.agent_id})",
            f"Question: {self.question}",
            f"Answer: {self.answer}",
        ]
        if self.facts:
            lines.append("Referenced facts:")
            lines.extend(f"- {fact}" for fact in self.facts)
        return "\n".join(lines)


class ZepToolsService:
    """Local, cache-first graph tools for Explorer Agent.

    The source data is the project's cached Zep graph payload. This avoids Zep
    rate limits during Explorer reads while still grounding answers in facts
    originally produced by Zep.
    """

    def __init__(
        self,
        graph_data: dict[str, Any],
        *,
        profiles: list[dict[str, Any]] | None = None,
        actions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.graph_data = graph_data
        self.graph_id = str(graph_data.get("graph_id") or "")
        self.nodes = [dict(node) for node in graph_data.get("nodes", []) or []]
        self.edges = [dict(edge) for edge in graph_data.get("edges", []) or []]
        self.profiles = [dict(profile) for profile in profiles or []]
        self.actions = [dict(action) for action in actions or []]
        self.node_map = {str(node.get("uuid") or ""): node for node in self.nodes}
        self._hydrate_edge_names()

    def quick_search(self, query: str, *, limit: int = 10) -> SearchResult:
        limit = max(1, min(limit, 50))
        ranked_edges = self._rank_edges(query)[:limit]
        ranked_nodes = self._rank_nodes(query)[: max(1, limit // 2)]

        facts = []
        seen: set[str] = set()
        for edge in ranked_edges:
            fact = str(edge.get("fact") or "").strip()
            if fact and fact not in seen:
                facts.append(fact)
                seen.add(fact)
        for node in ranked_nodes:
            summary = str(node.get("summary") or "").strip()
            name = str(node.get("name") or "Entity").strip()
            fact = f"{name}: {summary}" if summary else ""
            if fact and fact not in seen:
                facts.append(fact)
                seen.add(fact)

        return SearchResult(
            query=query,
            facts=facts[:limit],
            edges=ranked_edges,
            nodes=ranked_nodes,
        )

    def panorama_search(self, query: str, *, include_expired: bool = True, limit: int = 50) -> PanoramaResult:
        limit = max(1, min(limit, 100))
        active: list[tuple[int, str]] = []
        historical: list[tuple[int, str]] = []

        for edge in self.edges:
            fact = str(edge.get("fact") or "").strip()
            if not fact:
                continue
            score = self._score_text(query, self._edge_text(edge))
            if self._is_historical_edge(edge):
                historical.append((score, self._temporal_fact(edge, fact)))
            else:
                active.append((score, fact))

        active_facts = [fact for _, fact in self._sort_scored(active)[:limit]]
        historical_facts = [fact for _, fact in self._sort_scored(historical)[:limit]] if include_expired else []

        return PanoramaResult(
            query=query,
            active_facts=active_facts,
            historical_facts=historical_facts,
            nodes=self._rank_nodes(query)[:limit],
            total_edges=len(self.edges),
        )

    def insight_forge(
        self,
        query: str,
        *,
        simulation_requirement: str,
        max_sub_queries: int = 4,
        limit: int = 15,
    ) -> InsightForgeResult:
        sub_queries = self._build_sub_queries(query, simulation_requirement, max_sub_queries)
        facts: list[str] = []
        edges: list[dict[str, Any]] = []
        seen_facts: set[str] = set()

        for sub_query in sub_queries:
            result = self.quick_search(sub_query, limit=limit)
            edges.extend(result.edges)
            for fact in result.facts:
                if fact not in seen_facts:
                    facts.append(fact)
                    seen_facts.add(fact)

        entity_ids = {
            str(edge.get("source_node_uuid") or "")
            for edge in edges
            if edge.get("source_node_uuid")
        } | {
            str(edge.get("target_node_uuid") or "")
            for edge in edges
            if edge.get("target_node_uuid")
        }
        entities = [self.node_map[node_id] for node_id in entity_ids if node_id in self.node_map]
        chains = self._relationship_chains(edges)
        return InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=sub_queries,
            facts=facts[:limit],
            entities=entities[:limit],
            relationship_chains=chains[:limit],
        )

    def interview_agent(self, agent_id: int, question: str, *, fact_limit: int = 5) -> AgentInterviewResult:
        profile = self._find_profile(agent_id)
        if profile is None:
            raise ValueError(f"Agent {agent_id} profile not found")

        name = str(profile.get("name") or profile.get("username") or f"Agent {agent_id}")
        persona = str(profile.get("persona") or profile.get("bio") or "No persona text is available.")
        topics = ", ".join(str(topic) for topic in profile.get("interested_topics", [])[:4])
        query = " ".join(part for part in [name, topics, question] if part).strip()
        facts = self.quick_search(query, limit=fact_limit).facts
        recent_actions = self._recent_actions_for_agent(agent_id, limit=5)

        action_summary = ""
        if recent_actions:
            action_bits = [
                f"round {action.get('round_number', 'N/A')} {action.get('platform', 'unknown')} "
                f"{action.get('action_type', 'ACTION')}: {action.get('content') or action.get('topic') or ''}".strip()
                for action in recent_actions
            ]
            action_summary = " Recent observed actions: " + " | ".join(action_bits)

        fact_summary = " ".join(f'"{fact}"' for fact in facts[:2])
        answer = (
            f"I am {name}. From my persona: {persona} "
            f"My response to '{question}' is grounded in the simulation facts: {fact_summary or 'no direct fact matched.'}"
            f"{action_summary}"
        ).strip()

        return AgentInterviewResult(
            agent_id=agent_id,
            agent_name=name,
            question=question,
            answer=answer,
            profile=profile,
            facts=facts,
            recent_actions=recent_actions,
        )

    def _hydrate_edge_names(self) -> None:
        for edge in self.edges:
            source_uuid = str(edge.get("source_node_uuid") or "")
            target_uuid = str(edge.get("target_node_uuid") or "")
            edge.setdefault("source_node_name", self.node_map.get(source_uuid, {}).get("name", ""))
            edge.setdefault("target_node_name", self.node_map.get(target_uuid, {}).get("name", ""))

    def _rank_edges(self, query: str) -> list[dict[str, Any]]:
        scored = [(self._score_text(query, self._edge_text(edge)), edge) for edge in self.edges if edge.get("fact")]
        sorted_edges = [edge for _, edge in self._sort_scored(scored)]
        return sorted_edges

    def _rank_nodes(self, query: str) -> list[dict[str, Any]]:
        scored = [(self._score_text(query, self._node_text(node)), node) for node in self.nodes]
        sorted_nodes = [node for _, node in self._sort_scored(scored)]
        return sorted_nodes

    def _score_text(self, query: str, text: str) -> int:
        query_lower = query.strip().lower()
        text_lower = text.lower()
        if not query_lower:
            return 1

        score = 0
        if query_lower in text_lower:
            score += 100
        for token in self._tokens(query_lower):
            if token in text_lower:
                score += 10
        return score

    def _tokens(self, query: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", query.lower())
        return tokens or ([query.lower()] if query.strip() else [])

    def _sort_scored(self, items: list[tuple[int, Any]]) -> list[tuple[int, Any]]:
        positive = [item for item in items if item[0] > 0]
        source = positive if positive else items
        return sorted(source, key=lambda item: item[0], reverse=True)

    def _edge_text(self, edge: dict[str, Any]) -> str:
        return " ".join(
            str(part)
            for part in (
                edge.get("fact"),
                edge.get("name"),
                edge.get("fact_type"),
                edge.get("source_node_name"),
                edge.get("target_node_name"),
            )
            if part
        )

    def _node_text(self, node: dict[str, Any]) -> str:
        return " ".join(
            str(part)
            for part in (
                node.get("name"),
                node.get("summary"),
                " ".join(str(label) for label in node.get("labels", []) or []),
                " ".join(str(value) for value in (node.get("attributes") or {}).values() if value),
            )
            if part
        )

    def _is_historical_edge(self, edge: dict[str, Any]) -> bool:
        return bool(edge.get("invalid_at") or edge.get("expired_at"))

    def _temporal_fact(self, edge: dict[str, Any], fact: str) -> str:
        start = edge.get("valid_at") or edge.get("created_at") or "unknown"
        end = edge.get("invalid_at") or edge.get("expired_at") or "unknown"
        return f"[{start} - {end}] {fact}"

    def _build_sub_queries(self, query: str, simulation_requirement: str, max_queries: int) -> list[str]:
        candidates = [
            query,
            f"{query} key entities",
            f"{query} causes and impact",
            simulation_requirement,
        ]
        unique: list[str] = []
        for candidate in candidates:
            stripped = candidate.strip()
            if stripped and stripped not in unique:
                unique.append(stripped)
        return unique[: max(1, max_queries)]

    def _relationship_chains(self, edges: list[dict[str, Any]]) -> list[str]:
        chains: list[str] = []
        seen: set[str] = set()
        for edge in edges:
            source = str(edge.get("source_node_name") or edge.get("source_node_uuid") or "source")
            target = str(edge.get("target_node_name") or edge.get("target_node_uuid") or "target")
            name = str(edge.get("name") or edge.get("fact_type") or "relates_to")
            chain = f"{source} --[{name}]--> {target}"
            if chain not in seen:
                seen.add(chain)
                chains.append(chain)
        return chains

    def _find_profile(self, agent_id: int) -> dict[str, Any] | None:
        for profile in self.profiles:
            try:
                if int(profile.get("user_id") or -1) == int(agent_id):
                    return profile
            except (TypeError, ValueError):
                continue
        return None

    def _recent_actions_for_agent(self, agent_id: int, *, limit: int) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for action in self.actions:
            try:
                if int(action.get("agent_id") or -1) == int(agent_id):
                    matched.append(action)
            except (TypeError, ValueError):
                continue
        return matched[-limit:]
