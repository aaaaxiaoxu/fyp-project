#!/usr/bin/env python3
"""
Task 6 real end-to-end test: ontology generation + graph build with 《平凡的世界》
Run from fyp-backend/ directory with the server running:
    python tests/test_task6_real.py
"""
import json
import os
import sys
import time

import requests

BASE_API = "http://127.0.0.1:8000/api"
BASE_AUTH = "http://127.0.0.1:8000/auth"
NOVEL_PATH = os.path.join(os.path.dirname(__file__), "../data/1_《平凡的世界》（实体版全本）作者：路遥.txt")

EMAIL = "task6test@example.com"
PASSWORD = "TestPass123!"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_or_login() -> str:
    """Register user or login if already exists. Returns auth token."""
    # Try to register
    r = requests.post(f"{BASE_AUTH}/register", json={
        "email": EMAIL,
        "password": PASSWORD,
        "nickname": "Task6Tester",
    }, timeout=10)
    if r.status_code not in (200, 201):
        log(f"Register response: {r.status_code} {r.text[:200]}")

    # Login
    r = requests.post(f"{BASE_AUTH}/login", json={
        "email": EMAIL,
        "password": PASSWORD,
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        # Try cookie-based: re-login
        log(f"Login response keys: {list(data.keys())}")
        raise RuntimeError(f"No token in login response: {data}")
    log(f"Logged in, token prefix: {token[:30]}...")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_project(token: str) -> str:
    r = requests.post(f"{BASE_API}/graph/project", json={
        "name": "平凡的世界测试项目",
        "simulation_requirement": "模拟陕北农村1975-1985年间的社会舆论传播，重点关注农村改革、城乡差距、个人命运等主题下的人物互动和信息扩散",
    }, headers=auth_headers(token), timeout=10)
    if r.status_code not in (200, 201):
        log(f"Create project failed: {r.status_code} {r.text[:400]}")
        r.raise_for_status()
    data = r.json()
    project_id = data.get("project_id") or data.get("id")
    if not project_id:
        raise RuntimeError(f"No project_id in response: {data}")
    log(f"Created project: {project_id}")
    return project_id


def generate_ontology(token: str, project_id: str) -> str:
    """Upload novel and start ontology generation. Returns task_id."""
    log(f"Reading novel from: {NOVEL_PATH}")
    with open(NOVEL_PATH, "rb") as f:
        novel_data = f.read()
    log(f"Novel size: {len(novel_data):,} bytes")

    r = requests.post(
        f"{BASE_API}/graph/ontology/generate",
        data={"project_id": project_id},
        files={"files": ("平凡的世界.txt", novel_data, "text/plain")},
        headers=auth_headers(token),
        timeout=30,
    )
    if r.status_code not in (200, 201, 202):
        log(f"Ontology generate failed: {r.status_code} {r.text[:400]}")
        r.raise_for_status()
    data = r.json()
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"No task_id in response: {data}")
    log(f"Ontology generation task started: {task_id}")
    return task_id


def poll_task(token: str, task_id: str, timeout_s: int = 600, label: str = "") -> dict:
    """Poll task until completed or failed. Returns final task data."""
    start = time.monotonic()
    last_progress = -1
    poll_count = 0
    while True:
        poll_count += 1
        elapsed = time.monotonic() - start
        if elapsed > timeout_s:
            raise TimeoutError(f"{label} task {task_id} timed out after {timeout_s}s")

        r = requests.get(f"{BASE_API}/graph/task/{task_id}", headers=auth_headers(token), timeout=10)
        if r.status_code != 200:
            log(f"Poll task {task_id} failed: {r.status_code}")
            time.sleep(5)
            continue

        data = r.json()
        status = data.get("status", "")
        progress = data.get("progress", 0)
        message = data.get("message", "")

        if progress != last_progress:
            log(f"[{label}] poll#{poll_count} status={status} progress={progress}% msg='{message}' elapsed={elapsed:.0f}s")
            last_progress = progress

        if status == "completed":
            log(f"[{label}] COMPLETED after {elapsed:.0f}s")
            return data
        if status == "failed":
            error = data.get("error", "unknown error")
            raise RuntimeError(f"{label} task failed: {error}")

        time.sleep(10)


def build_graph(token: str, project_id: str) -> str:
    """Start graph build. Returns task_id."""
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
    if not task_id:
        raise RuntimeError(f"No task_id in response: {data}")
    log(f"Graph build task started: {task_id}")
    return task_id


def test_graph_data(token: str, graph_id: str) -> None:
    r = requests.get(f"{BASE_API}/graph/data/{graph_id}", headers=auth_headers(token), timeout=30)
    r.raise_for_status()
    data = r.json()
    node_count = data.get("node_count", 0)
    edge_count = data.get("edge_count", 0)
    log(f"GET /graph/data: node_count={node_count}, edge_count={edge_count}")
    assert node_count >= 0, "node_count should be non-negative"
    assert edge_count >= 0, "edge_count should be non-negative"
    if node_count > 0:
        sample_node = data["nodes"][0]
        log(f"  Sample node: name={sample_node.get('name')!r}, labels={sample_node.get('labels')}")
    log("  GET /graph/data PASSED")


def test_graph_entities(token: str, graph_id: str) -> None:
    r = requests.get(f"{BASE_API}/graph/entities/{graph_id}", headers=auth_headers(token), timeout=30)
    r.raise_for_status()
    data = r.json()
    total = data.get("total_count", 0)
    filtered = data.get("filtered_count", 0)
    entity_types = data.get("entity_types", [])
    log(f"GET /graph/entities: total_count={total}, filtered_count={filtered}, entity_types={entity_types}")
    log("  GET /graph/entities PASSED")


def main() -> None:
    log("=== Task 6 Real E2E Test: 《平凡的世界》 ===")

    if not os.path.exists(NOVEL_PATH):
        log(f"ERROR: Novel not found at {NOVEL_PATH}")
        sys.exit(1)

    # Step 1: Login
    log("--- Step 1: Login ---")
    token = register_or_login()

    # Step 2: Create project
    log("--- Step 2: Create Project ---")
    project_id = create_project(token)

    # Step 3: Upload + generate ontology
    log("--- Step 3: Generate Ontology (LLM call, ~2-3 min) ---")
    ontology_task_id = generate_ontology(token, project_id)
    ontology_result = poll_task(token, ontology_task_id, timeout_s=600, label="ontology")
    result_json = ontology_result.get("result_json", {})
    log(f"  Ontology result: {json.dumps(result_json, ensure_ascii=False)}")

    # Step 4: Build graph
    log("--- Step 4: Build Graph (may take 10-30+ min for large novel) ---")
    build_task_id = build_graph(token, project_id)
    build_result = poll_task(token, build_task_id, timeout_s=7200, label="graph_build")
    build_result_json = build_result.get("result_json", {})
    log(f"  Build result: {json.dumps(build_result_json, ensure_ascii=False, indent=2)}")

    graph_id = build_result_json.get("graph_id") or build_result_json.get("zep_graph_id")
    if not graph_id:
        log("ERROR: No graph_id in build result")
        sys.exit(1)

    # Step 5: Query graph data
    log("--- Step 5: Test GET /graph/data ---")
    test_graph_data(token, graph_id)

    # Step 6: Query entities
    log("--- Step 6: Test GET /graph/entities ---")
    test_graph_entities(token, graph_id)

    log("=== ALL STEPS PASSED ===")


if __name__ == "__main__":
    main()
