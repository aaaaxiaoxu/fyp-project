from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zep_cloud.client import Zep

from ..settings import settings
from ..utils import fetch_all_edges, fetch_all_nodes, get_logger

logger = get_logger("fyp.zep_entity_reader")


@dataclass(frozen=True, slots=True)
class EntityNode:
    uuid: str
    name: str
    labels: list[str]
    summary: str
    attributes: dict[str, Any]
    related_edges: list[dict[str, Any]] = field(default_factory=list)
    related_nodes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": list(self.labels),
            "summary": self.summary,
            "attributes": dict(self.attributes),
            "related_edges": [dict(item) for item in self.related_edges],
            "related_nodes": [dict(item) for item in self.related_nodes],
        }


@dataclass(frozen=True, slots=True)
class FilteredEntities:
    entities: list[EntityNode]
    entity_types: set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [entity.to_dict() for entity in self.entities],
            "entity_types": sorted(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: Zep | None = None,
    ) -> None:
        self.client = client or self._build_client(api_key=api_key, base_url=base_url)

    def get_graph_data(self, graph_id: str) -> dict[str, Any]:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        node_map = {node["uuid"]: node for node in nodes}

        for edge in edges:
            edge["source_node_name"] = node_map.get(edge["source_node_uuid"], {}).get("name", "")
            edge["target_node_name"] = node_map.get(edge["target_node_uuid"], {}).get("name", "")

        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def get_all_nodes(self, graph_id: str) -> list[dict[str, Any]]:
        nodes = fetch_all_nodes(self.client, graph_id)
        return [
            {
                "uuid": str(getattr(node, "uuid_", None) or getattr(node, "uuid", "") or ""),
                "name": getattr(node, "name", "") or "",
                "labels": list(getattr(node, "labels", None) or []),
                "summary": getattr(node, "summary", "") or "",
                "attributes": dict(getattr(node, "attributes", None) or {}),
                "created_at": str(getattr(node, "created_at", None)) if getattr(node, "created_at", None) else None,
            }
            for node in nodes
        ]

    def get_all_edges(self, graph_id: str) -> list[dict[str, Any]]:
        edges = fetch_all_edges(self.client, graph_id)
        edge_rows: list[dict[str, Any]] = []
        for edge in edges:
            episodes = getattr(edge, "episodes", None) or getattr(edge, "episode_ids", None) or []
            if not isinstance(episodes, list):
                episodes = [episodes]
            edge_rows.append(
                {
                    "uuid": str(getattr(edge, "uuid_", None) or getattr(edge, "uuid", "") or ""),
                    "name": getattr(edge, "name", "") or "",
                    "fact": getattr(edge, "fact", "") or "",
                    "fact_type": getattr(edge, "fact_type", None) or getattr(edge, "name", "") or "",
                    "source_node_uuid": str(getattr(edge, "source_node_uuid", "") or ""),
                    "target_node_uuid": str(getattr(edge, "target_node_uuid", "") or ""),
                    "attributes": dict(getattr(edge, "attributes", None) or {}),
                    "created_at": str(getattr(edge, "created_at", None)) if getattr(edge, "created_at", None) else None,
                    "valid_at": str(getattr(edge, "valid_at", None)) if getattr(edge, "valid_at", None) else None,
                    "invalid_at": str(getattr(edge, "invalid_at", None)) if getattr(edge, "invalid_at", None) else None,
                    "expired_at": str(getattr(edge, "expired_at", None)) if getattr(edge, "expired_at", None) else None,
                    "episodes": [str(item) for item in episodes if item],
                }
            )
        return edge_rows

    def filter_defined_entities(
        self,
        graph_id: str,
        *,
        defined_entity_types: list[str] | None = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        logger.info("filtering entities for graph %s", graph_id)
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {node["uuid"]: node for node in all_nodes}

        filtered_entities: list[EntityNode] = []
        entity_types_found: set[str] = set()
        for node in all_nodes:
            custom_labels = [label for label in node["labels"] if label not in {"Entity", "Node"}]
            if not custom_labels:
                continue

            if defined_entity_types is not None:
                matching = [label for label in custom_labels if label in defined_entity_types]
                if not matching:
                    continue
                entity_type = matching[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)
            related_edges: list[dict[str, Any]] = []
            related_node_uuids: set[str] = set()
            if enrich_with_edges:
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append(
                            {
                                "direction": "outgoing",
                                "edge_name": edge["name"],
                                "fact": edge["fact"],
                                "target_node_uuid": edge["target_node_uuid"],
                            }
                        )
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append(
                            {
                                "direction": "incoming",
                                "edge_name": edge["name"],
                                "fact": edge["fact"],
                                "source_node_uuid": edge["source_node_uuid"],
                            }
                        )
                        related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = [
                {
                    "uuid": node_map[related_uuid]["uuid"],
                    "name": node_map[related_uuid]["name"],
                    "labels": list(node_map[related_uuid]["labels"]),
                    "summary": node_map[related_uuid]["summary"],
                }
                for related_uuid in related_node_uuids
                if related_uuid in node_map
            ]

            filtered_entities.append(
                EntityNode(
                    uuid=node["uuid"],
                    name=node["name"],
                    labels=list(node["labels"]),
                    summary=node["summary"],
                    attributes=dict(node["attributes"]),
                    related_edges=related_edges,
                    related_nodes=related_nodes,
                )
            )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=len(all_nodes),
            filtered_count=len(filtered_entities),
        )

    def _build_client(self, *, api_key: str | None, base_url: str | None) -> Zep:
        resolved_api_key = (api_key or settings.ZEP_API_KEY).strip()
        if not resolved_api_key:
            raise ValueError("ZEP_API_KEY 未配置")

        resolved_base_url = (base_url if base_url is not None else settings.ZEP_BASE_URL).strip() or None
        return Zep(api_key=resolved_api_key, base_url=resolved_base_url)
