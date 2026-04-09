from __future__ import annotations

import re
import time
import uuid
import warnings
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import Field
from zep_cloud import EpisodeData, EntityEdgeSourceTarget
from zep_cloud.client import Zep
from zep_cloud.external_clients.ontology import EdgeModel, EntityModel, EntityText

from ..settings import settings
from ..utils import fetch_all_edges, fetch_all_nodes, get_logger
from .text_processor import TextProcessor

logger = get_logger("fyp.graph_builder")

ProgressCallback = Callable[[int, str, dict[str, Any] | None], None]
_RESERVED_PROPERTY_NAMES = {"uuid", "name", "group_id", "name_embedding", "summary", "created_at"}


@dataclass(frozen=True, slots=True)
class GraphBuildResult:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: list[str]
    chunk_count: int
    graph_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": list(self.entity_types),
            "chunk_count": self.chunk_count,
        }


class GraphBuilderService:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: Zep | None = None,
        send_delay_s: float = 1.0,
        poll_interval_s: float = 3.0,
    ) -> None:
        self._send_delay_s = max(0.0, send_delay_s)
        self._poll_interval_s = max(0.1, poll_interval_s)
        self.client = client or self._build_client(api_key=api_key, base_url=base_url)

    def build_graph(
        self,
        *,
        text: str,
        ontology: dict[str, Any],
        graph_name: str,
        chunk_size: int = settings.DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = settings.DEFAULT_CHUNK_OVERLAP,
        batch_size: int = 3,
        progress_callback: ProgressCallback | None = None,
        episode_timeout_s: int = 600,
    ) -> GraphBuildResult:
        if not text.strip():
            raise ValueError("graph build text cannot be empty")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")

        chunks = TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
        if not chunks:
            raise ValueError("graph build text cannot be split into chunks")

        self._emit_progress(
            progress_callback,
            10,
            "split text into chunks",
            {
                "stage": "split_text",
                "chunk_count": len(chunks),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        )

        graph_id = self.create_graph(graph_name)
        self._emit_progress(
            progress_callback,
            20,
            "created zep graph",
            {"stage": "create_graph", "graph_id": graph_id},
        )

        self.set_ontology(graph_id, ontology)
        self._emit_progress(
            progress_callback,
            30,
            "set ontology",
            {
                "stage": "set_ontology",
                "graph_id": graph_id,
                "entity_type_count": len(ontology.get("entity_types", [])),
                "edge_type_count": len(ontology.get("edge_types", [])),
            },
        )

        episode_uuids = self.add_text_batches(
            graph_id=graph_id,
            chunks=chunks,
            batch_size=batch_size,
            progress_callback=lambda ratio, detail: self._emit_progress(
                progress_callback,
                30 + int(ratio * 35),
                "adding text chunks to zep",
                {"stage": "add_text_batches", "graph_id": graph_id, **detail},
            ),
        )

        self._emit_progress(
            progress_callback,
            65,
            "waiting for zep episode processing",
            {
                "stage": "wait_for_episodes",
                "graph_id": graph_id,
                "episode_count": len(episode_uuids),
            },
        )
        self.wait_for_episodes(
            episode_uuids,
            timeout_s=episode_timeout_s,
            progress_callback=lambda ratio, detail: self._emit_progress(
                progress_callback,
                65 + int(ratio * 25),
                "processing graph episodes",
                {"stage": "wait_for_episodes", "graph_id": graph_id, **detail},
            ),
        )

        self._emit_progress(
            progress_callback,
            95,
            "fetching graph data",
            {"stage": "fetch_graph_data", "graph_id": graph_id},
        )
        graph_data = self.get_graph_data(graph_id)
        entity_types = sorted(
            {
                label
                for node in graph_data["nodes"]
                for label in node.get("labels", [])
                if label not in {"Entity", "Node"}
            }
        )
        return GraphBuildResult(
            graph_id=graph_id,
            node_count=int(graph_data["node_count"]),
            edge_count=int(graph_data["edge_count"]),
            entity_types=entity_types,
            chunk_count=len(chunks),
            graph_data=graph_data,
        )

    def create_graph(self, name: str) -> str:
        graph_id = f"fyp_{uuid.uuid4().hex[:16]}"
        self.client.graph.create(
            graph_id=graph_id,
            name=name.strip() or "FYP Graph",
            description="FYP social simulation graph",
        )
        return graph_id

    def set_ontology(self, graph_id: str, ontology: dict[str, Any]) -> None:
        warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

        entity_types: dict[str, type[EntityModel]] = {}
        for entity_def in ontology.get("entity_types", []):
            # handle models that return "type" or "label" instead of "name"
            entity_name = (
                str(entity_def.get("name") or entity_def.get("type") or entity_def.get("label") or "").strip()
            )
            if not entity_name:
                continue

            description = str(entity_def.get("description", "")).strip() or f"{entity_name} entity"
            attrs: dict[str, Any] = {"__doc__": description, "__annotations__": {}}
            annotations = attrs["__annotations__"]
            for attr_def in entity_def.get("attributes", []):
                if isinstance(attr_def, str):
                    raw_attr_name = attr_def.strip()
                    attr_description = raw_attr_name
                else:
                    raw_attr_name = str(attr_def.get("name", "")).strip()
                    attr_description = str(attr_def.get("description", "")).strip()
                if not raw_attr_name:
                    continue
                safe_attr_name = self._safe_property_name(raw_attr_name)
                annotations[safe_attr_name] = EntityText
                attrs[safe_attr_name] = Field(
                    default=None,
                    description=attr_description or safe_attr_name,
                )

            entity_class = type(entity_name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[entity_name] = entity_class

        edge_definitions: dict[str, tuple[type[EdgeModel], list[EntityEdgeSourceTarget]]] = {}
        for edge_def in ontology.get("edge_types", []):
            edge_name = (
                str(edge_def.get("name") or edge_def.get("type") or edge_def.get("label") or "").strip()
            )
            if not edge_name:
                continue

            description = str(edge_def.get("description", "")).strip() or f"{edge_name} relationship"
            attrs = {"__doc__": description, "__annotations__": {}}
            annotations = attrs["__annotations__"]
            for attr_def in edge_def.get("attributes", []):
                if isinstance(attr_def, str):
                    raw_attr_name = attr_def.strip()
                    attr_description = raw_attr_name
                else:
                    raw_attr_name = str(attr_def.get("name", "")).strip()
                    attr_description = str(attr_def.get("description", "")).strip()
                if not raw_attr_name:
                    continue
                safe_attr_name = self._safe_property_name(raw_attr_name)
                annotations[safe_attr_name] = str | None
                attrs[safe_attr_name] = Field(
                    default=None,
                    description=attr_description or safe_attr_name,
                )

            edge_class = type(self._to_edge_model_name(edge_name), (EdgeModel,), attrs)
            edge_class.__doc__ = description
            source_targets = [
                EntityEdgeSourceTarget(
                    source=str(source_target.get("source", "")).strip() or "Entity",
                    target=str(source_target.get("target", "")).strip() or "Entity",
                )
                for source_target in edge_def.get("source_targets", [])
            ]
            if source_targets:
                edge_definitions[edge_name] = (edge_class, source_targets)

        if not entity_types:
            raise ValueError("ontology must include at least one entity type")

        self.client.graph.set_ontology(
            graph_ids=[graph_id],
            entities=entity_types,
            edges=edge_definitions or None,
        )

    def add_text_batches(
        self,
        *,
        graph_id: str,
        chunks: list[str],
        batch_size: int = 3,
        progress_callback: Callable[[float, dict[str, Any]], None] | None = None,
    ) -> list[str]:
        episode_uuids: list[str] = []
        total_chunks = len(chunks)
        total_batches = (total_chunks + batch_size - 1) // batch_size

        for offset in range(0, total_chunks, batch_size):
            batch_chunks = chunks[offset : offset + batch_size]
            batch_number = (offset // batch_size) + 1
            if progress_callback is not None:
                progress_callback(
                    (offset + len(batch_chunks)) / total_chunks,
                    {
                        "current_batch": batch_number,
                        "total_batches": total_batches,
                        "processed_chunks": offset + len(batch_chunks),
                        "total_chunks": total_chunks,
                    },
                )

            batch_result = self.client.graph.add_batch(
                graph_id=graph_id,
                episodes=[EpisodeData(data=chunk, type="text") for chunk in batch_chunks],
            )
            for episode in batch_result or []:
                episode_uuid = getattr(episode, "uuid_", None) or getattr(episode, "uuid", None)
                if episode_uuid:
                    episode_uuids.append(str(episode_uuid))

            if self._send_delay_s > 0:
                time.sleep(self._send_delay_s)

        return episode_uuids

    def wait_for_episodes(
        self,
        episode_uuids: list[str],
        *,
        timeout_s: int = 600,
        progress_callback: Callable[[float, dict[str, Any]], None] | None = None,
        max_polls_per_cycle: int = 30,
    ) -> None:
        """Poll Zep episodes until all are processed.

        To avoid making O(n) API calls per cycle for large episode sets, each cycle
        polls at most ``max_polls_per_cycle`` episodes sampled from the pending set.
        """
        import random

        if not episode_uuids:
            if progress_callback is not None:
                progress_callback(1.0, {"processed_episodes": 0, "total_episodes": 0, "pending_episodes": 0})
            return

        start_time = time.monotonic()
        pending_episodes = set(episode_uuids)
        total_episodes = len(episode_uuids)

        while pending_episodes:
            # Sample a subset of pending episodes to poll per cycle to keep cycles short
            sample_size = min(max_polls_per_cycle, len(pending_episodes))
            sample = random.sample(list(pending_episodes), sample_size)
            for episode_uuid in sample:
                try:
                    episode = self.client.graph.episode.get(uuid_=episode_uuid)
                except Exception as exc:
                    logger.warning("failed to poll episode %s: %s", episode_uuid, str(exc)[:160])
                    continue
                if getattr(episode, "processed", False):
                    pending_episodes.discard(episode_uuid)

            processed = total_episodes - len(pending_episodes)
            if progress_callback is not None:
                progress_callback(
                    processed / total_episodes if total_episodes else 1.0,
                    {
                        "processed_episodes": processed,
                        "total_episodes": total_episodes,
                        "pending_episodes": len(pending_episodes),
                        "elapsed_seconds": round(time.monotonic() - start_time, 2),
                    },
                )

            if not pending_episodes:
                return

            if time.monotonic() - start_time > timeout_s:
                raise TimeoutError(
                    f"timed out waiting for Zep episodes to process: "
                    f"{processed}/{total_episodes} completed"
                )

            time.sleep(self._poll_interval_s)

    def get_graph_data(self, graph_id: str) -> dict[str, Any]:
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        node_map = {
            self._node_uuid(node): {
                "uuid": self._node_uuid(node),
                "name": getattr(node, "name", "") or "",
                "labels": list(getattr(node, "labels", None) or []),
                "summary": getattr(node, "summary", "") or "",
                "attributes": dict(getattr(node, "attributes", None) or {}),
                "created_at": self._stringify_datetime(getattr(node, "created_at", None)),
            }
            for node in nodes
        }

        edge_rows: list[dict[str, Any]] = []
        for edge in edges:
            source_uuid = str(getattr(edge, "source_node_uuid", "") or "")
            target_uuid = str(getattr(edge, "target_node_uuid", "") or "")
            episodes = getattr(edge, "episodes", None) or getattr(edge, "episode_ids", None) or []
            if not isinstance(episodes, list):
                episodes = [episodes]
            edge_rows.append(
                {
                    "uuid": str(getattr(edge, "uuid_", None) or getattr(edge, "uuid", "") or ""),
                    "name": getattr(edge, "name", "") or "",
                    "fact": getattr(edge, "fact", "") or "",
                    "fact_type": getattr(edge, "fact_type", None) or getattr(edge, "name", "") or "",
                    "source_node_uuid": source_uuid,
                    "target_node_uuid": target_uuid,
                    "source_node_name": node_map.get(source_uuid, {}).get("name", ""),
                    "target_node_name": node_map.get(target_uuid, {}).get("name", ""),
                    "attributes": dict(getattr(edge, "attributes", None) or {}),
                    "created_at": self._stringify_datetime(getattr(edge, "created_at", None)),
                    "valid_at": self._stringify_datetime(getattr(edge, "valid_at", None)),
                    "invalid_at": self._stringify_datetime(getattr(edge, "invalid_at", None)),
                    "expired_at": self._stringify_datetime(getattr(edge, "expired_at", None)),
                    "episodes": [str(item) for item in episodes if item],
                }
            )

        return {
            "graph_id": graph_id,
            "nodes": list(node_map.values()),
            "edges": edge_rows,
            "node_count": len(node_map),
            "edge_count": len(edge_rows),
        }

    def _build_client(self, *, api_key: str | None, base_url: str | None) -> Zep:
        resolved_api_key = (api_key or settings.ZEP_API_KEY).strip()
        if not resolved_api_key:
            raise ValueError("ZEP_API_KEY 未配置")

        resolved_base_url = (base_url if base_url is not None else settings.ZEP_BASE_URL).strip() or None
        return Zep(api_key=resolved_api_key, base_url=resolved_base_url)

    @staticmethod
    def _safe_property_name(raw_name: str) -> str:
        candidate = re.sub(r"[^A-Za-z0-9_]+", "_", raw_name.strip()).strip("_")
        if candidate and candidate[0].isdigit():
            candidate = f"field_{candidate}"
        if not candidate:
            return "entity_property"
        return f"entity_{candidate}" if candidate.lower() in _RESERVED_PROPERTY_NAMES else candidate

    @staticmethod
    def _to_edge_model_name(edge_name: str) -> str:
        return "".join(part.capitalize() for part in edge_name.split("_")) or "Edge"

    @staticmethod
    def _emit_progress(
        progress_callback: ProgressCallback | None,
        progress: int,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if progress_callback is not None:
            progress_callback(progress, message, detail)

    @staticmethod
    def _node_uuid(node: Any) -> str:
        return str(getattr(node, "uuid_", None) or getattr(node, "uuid", "") or "")

    @staticmethod
    def _stringify_datetime(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)
