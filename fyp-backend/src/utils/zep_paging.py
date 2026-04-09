from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from zep_cloud import InternalServerError
from zep_cloud.client import Zep
from zep_cloud.core.api_error import ApiError

from .logger import get_logger

logger = get_logger("fyp.zep_paging")

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0
_MAX_RATE_LIMIT_WAIT = 120.0  # cap retry-after to 2 min


def _fetch_page_with_retry(
    api_call: Callable[..., list[Any]],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
    **kwargs: Any,
) -> list[Any]:
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_exception: Exception | None = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            return api_call(*args, **kwargs)
        except ApiError as exc:
            if exc.status_code == 429:
                # Respect Retry-After header if present, else use exponential backoff
                retry_after_raw = (exc.headers or {}).get("retry-after") or (exc.headers or {}).get("Retry-After")
                try:
                    wait_s = min(float(retry_after_raw), _MAX_RATE_LIMIT_WAIT)
                except (TypeError, ValueError):
                    wait_s = min(delay, _MAX_RATE_LIMIT_WAIT)
                logger.warning(
                    "Zep %s rate limited (429), waiting %.0fs before retry (attempt %s/%s)",
                    page_description, wait_s, attempt + 1, max_retries,
                )
                time.sleep(wait_s)
                last_exception = exc
                continue
            last_exception = exc
            if attempt < max_retries - 1:
                logger.warning(
                    "Zep %s attempt %s failed (HTTP %s): %s, retrying in %.1fs...",
                    page_description, attempt + 1, exc.status_code, str(exc.body)[:100], delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("Zep %s failed after %s attempts: %s", page_description, max_retries, exc)
        except (ConnectionError, TimeoutError, OSError, InternalServerError) as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                logger.warning(
                    "Zep %s attempt %s failed: %s, retrying in %.1fs...",
                    page_description,
                    attempt + 1,
                    str(exc)[:100],
                    delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("Zep %s failed after %s attempts: %s", page_description, max_retries, exc)

    assert last_exception is not None
    raise last_exception


def fetch_all_nodes(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    all_nodes: list[Any] = []
    cursor: str | None = None
    page_num = 0

    while True:
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor

        page_num += 1
        batch = _fetch_page_with_retry(
            client.graph.node.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch nodes page {page_num} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break

        all_nodes.extend(batch)
        if len(all_nodes) >= max_items:
            logger.warning("Node count reached limit (%s), stopping pagination for graph %s", max_items, graph_id)
            return all_nodes[:max_items]

        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning("Node missing uuid field, stopping pagination at %s nodes", len(all_nodes))
            break

    return all_nodes


def fetch_all_edges(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    all_edges: list[Any] = []
    cursor: str | None = None
    page_num = 0

    while True:
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor

        page_num += 1
        batch = _fetch_page_with_retry(
            client.graph.edge.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch edges page {page_num} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break

        all_edges.extend(batch)
        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning("Edge missing uuid field, stopping pagination at %s edges", len(all_edges))
            break

    return all_edges
