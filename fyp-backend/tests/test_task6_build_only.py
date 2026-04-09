#!/usr/bin/env python3
"""
Task 6 graph build test using existing ontology from proj_1352462aef07.
Run: NO_PROXY=127.0.0.1,localhost python tests/test_task6_build_only.py
"""
import json
import sys
import time

import requests

BASE_API = "http://127.0.0.1:8000/api"
BASE_AUTH = "http://127.0.0.1:8000/auth"
EMAIL = "task6test@example.com"
PASSWORD = "TestPass123!"
PROJECT_ID = "proj_1352462aef07"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def login() -> str:
    r = requests.post(f"{BASE_AUTH}/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    r.raise_for_status()
    token = r.json().get("access_token")
    log(f"Logged in, token prefix: {token[:30]}...")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def build_graph(token: str, project_id: str) -> str:
    r = requests.post(f"{BASE_API}/graph/build", json={
        "project_id": project_id,
        "chunk_size": 800,
        "chunk_overlap": 80,
        "batch_size": 5,
    }, headers=auth_headers(token), timeout=15)
    if r.status_code not in (200, 201, 202):
        log(f"Build graph failed: {r.status_code} {r.text[:400]}")
        r.raise_for_status()
    data = r.json()
    task_id = data.get("task_id")
    log(f"Graph build task started: {task_id}")
    return task_id


def poll_task(token: str, task_id: str, timeout_s: int = 7200, label: str = "") -> dict:
    start = time.monotonic()
    last_progress = -1
    poll_count = 0
    while True:
        poll_count += 1
        elapsed = time.monotonic() - start
        if elapsed > timeout_s:
            raise TimeoutError(f"{label} timed out after {timeout_s}s")

        r = requests.get(f"{BASE_API}/graph/task/{task_id}", headers=auth_headers(token), timeout=10)
        if r.status_code != 200:
            time.sleep(5)
            continue

        data = r.json()
        status = data.get("status", "")
        progress = data.get("progress", 0)
        message = data.get("message", "")
        detail = data.get("progress_detail_json") or {}

        if progress != last_progress or poll_count % 6 == 0:
            log(f"[{label}] poll#{poll_count} status={status} progress={progress}% msg='{message}' {detail} elapsed={elapsed:.0f}s")
            last_progress = progress

        if status == "completed":
            log(f"[{label}] COMPLETED after {elapsed:.0f}s")
            return data
        if status == "failed":
            raise RuntimeError(f"{label} failed: {data.get('error', 'unknown')}")

        time.sleep(10)


def test_graph_data(token: str, graph_id: str) -> None:
    r = requests.get(f"{BASE_API}/graph/data/{graph_id}", headers=auth_headers(token), timeout=60)
    r.raise_for_status()
    data = r.json()
    node_count = data.get("node_count", 0)
    edge_count = data.get("edge_count", 0)
    log(f"GET /graph/data: node_count={node_count}, edge_count={edge_count}")
    if node_count > 0:
        sample = data["nodes"][0]
        log(f"  Sample node: name={sample.get('name')!r} labels={sample.get('labels')}")
    log("  PASSED")


def test_graph_entities(token: str, graph_id: str) -> None:
    r = requests.get(f"{BASE_API}/graph/entities/{graph_id}", headers=auth_headers(token), timeout=60)
    r.raise_for_status()
    data = r.json()
    log(f"GET /graph/entities: total={data.get('total_count')}, filtered={data.get('filtered_count')}, types={data.get('entity_types')}")
    log("  PASSED")


def main() -> None:
    log("=== Task 6 Graph Build Test (existing ontology) ===")
    log(f"Project: {PROJECT_ID}")

    token = login()

    log("--- Building Graph ---")
    task_id = build_graph(token, PROJECT_ID)
    result = poll_task(token, task_id, label="graph_build")
    result_json = result.get("result_json", {})
    log(f"Build result: {json.dumps(result_json, ensure_ascii=False, indent=2)}")

    graph_id = result_json.get("graph_id") or result_json.get("zep_graph_id")
    if not graph_id:
        log("ERROR: No graph_id in result")
        sys.exit(1)

    log("--- Testing GET /graph/data ---")
    test_graph_data(token, graph_id)

    log("--- Testing GET /graph/entities ---")
    test_graph_entities(token, graph_id)

    log("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
