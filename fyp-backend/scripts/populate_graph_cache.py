#!/usr/bin/env python3
"""
One-time script: fetch graph data from Zep and write graph_data.json cache.

Usage:
  python scripts/populate_graph_cache.py --project-id proj_xxx --graph-id fyp_xxx
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from zep_cloud.client import Zep
from zep_cloud.core.api_error import ApiError

from src.settings import settings
from src.utils.path_resolver import ensure_parent_directory, project_graph_data_path

DEFAULT_PAGE_SIZE = 100
DEFAULT_DELAY_SECONDS = 14.0
DEFAULT_RESET_WAIT_SECONDS = 65.0


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill graph_data.json cache from Zep.")
    parser.add_argument("--project-id", required=True, help="Project ID, for example proj_1352462aef07")
    parser.add_argument("--graph-id", required=True, help="Zep graph ID, for example fyp_5fc4082728864627")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Zep page size")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Delay between successful page requests",
    )
    parser.add_argument(
        "--reset-wait-seconds",
        type=float,
        default=DEFAULT_RESET_WAIT_SECONDS,
        help="Fallback wait when Zep returns 429 without a useful Retry-After",
    )
    return parser.parse_args()


def build_client() -> Zep:
    api_key = settings.ZEP_API_KEY.strip()
    if not api_key:
        raise RuntimeError("ZEP_API_KEY is not configured")

    base_url = settings.ZEP_BASE_URL.strip() or None
    return Zep(api_key=api_key, base_url=base_url)


def fetch_page_with_wait(
    api_call,
    graph_id: str,
    *,
    page_description: str,
    reset_wait_seconds: float,
    **kwargs: Any,
) -> list[Any]:
    while True:
        try:
            return api_call(graph_id, **kwargs)
        except ApiError as exc:
            if exc.status_code != 429:
                raise

            retry_after_raw = (exc.headers or {}).get("retry-after") or (exc.headers or {}).get("Retry-After")
            try:
                wait_seconds = max(float(retry_after_raw), 1.0)
            except (TypeError, ValueError):
                wait_seconds = reset_wait_seconds

            log(f"  Zep rate limited on {page_description}; waiting {int(wait_seconds)}s")
            time.sleep(wait_seconds)


def fetch_all_nodes_slow(
    client: Zep,
    graph_id: str,
    *,
    page_size: int,
    delay_seconds: float,
    reset_wait_seconds: float,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    cursor: str | None = None
    page = 0

    while True:
        page += 1
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor:
            kwargs["uuid_cursor"] = cursor

        log(f"  Fetching nodes page {page}...")
        batch = fetch_page_with_wait(
            client.graph.node.get_by_graph_id,
            graph_id,
            page_description=f"nodes page {page}",
            reset_wait_seconds=reset_wait_seconds,
            **kwargs,
        )

        if not batch:
            break

        for node in batch:
            nodes.append(
                {
                    "uuid": str(getattr(node, "uuid_", None) or getattr(node, "uuid", "") or ""),
                    "name": getattr(node, "name", "") or "",
                    "labels": list(getattr(node, "labels", None) or []),
                    "summary": getattr(node, "summary", "") or "",
                    "attributes": dict(getattr(node, "attributes", None) or {}),
                    "created_at": str(getattr(node, "created_at", None)) if getattr(node, "created_at", None) else None,
                }
            )

        log(f"  Got {len(batch)} nodes, total: {len(nodes)}")

        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if not cursor:
            break

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return nodes


def fetch_all_edges_slow(
    client: Zep,
    graph_id: str,
    *,
    page_size: int,
    delay_seconds: float,
    reset_wait_seconds: float,
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    cursor: str | None = None
    page = 0

    while True:
        page += 1
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor:
            kwargs["uuid_cursor"] = cursor

        log(f"  Fetching edges page {page}...")
        batch = fetch_page_with_wait(
            client.graph.edge.get_by_graph_id,
            graph_id,
            page_description=f"edges page {page}",
            reset_wait_seconds=reset_wait_seconds,
            **kwargs,
        )

        if not batch:
            break

        for edge in batch:
            episodes = getattr(edge, "episodes", None) or getattr(edge, "episode_ids", None) or []
            if not isinstance(episodes, list):
                episodes = [episodes]

            edges.append(
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

        log(f"  Got {len(batch)} edges, total: {len(edges)}")

        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if not cursor:
            break

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return edges


def main() -> None:
    args = parse_args()

    log(f"Populating graph cache for project={args.project_id}, graph={args.graph_id}")
    client = build_client()

    log("=== Fetching nodes ===")
    nodes = fetch_all_nodes_slow(
        client,
        args.graph_id,
        page_size=args.page_size,
        delay_seconds=args.delay_seconds,
        reset_wait_seconds=args.reset_wait_seconds,
    )

    if args.delay_seconds > 0:
        log(f"Sleeping {int(args.delay_seconds)}s before edges...")
        time.sleep(args.delay_seconds)

    log("=== Fetching edges ===")
    edges = fetch_all_edges_slow(
        client,
        args.graph_id,
        page_size=args.page_size,
        delay_seconds=args.delay_seconds,
        reset_wait_seconds=args.reset_wait_seconds,
    )

    node_map = {node["uuid"]: node for node in nodes}
    for edge in edges:
        edge["source_node_name"] = node_map.get(edge["source_node_uuid"], {}).get("name", "")
        edge["target_node_name"] = node_map.get(edge["target_node_uuid"], {}).get("name", "")

    graph_data = {
        "graph_id": args.graph_id,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }

    cache_path = project_graph_data_path(args.project_id)
    ensure_parent_directory(cache_path)
    cache_path.write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"Saved cache to {cache_path}")
    log(f"Summary: {len(nodes)} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
