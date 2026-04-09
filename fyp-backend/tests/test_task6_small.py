#!/usr/bin/env python3
"""
Task 6 E2E test using first ~40K chars of 《平凡的世界》.
Run: NO_PROXY=127.0.0.1,localhost python tests/test_task6_small.py
"""
import json
import sys
import time

import requests

BASE_API = "http://127.0.0.1:8000/api"
BASE_AUTH = "http://127.0.0.1:8000/auth"
NOVEL_PATH = "data/1_《平凡的世界》（实体版全本）作者：路遥.txt"
EMAIL = "task6small@example.com"
PASSWORD = "TestPass123!"
MAX_CHARS = 40000  # use first chapter only for speed


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_or_login() -> str:
    requests.post(f"{BASE_AUTH}/register", json={
        "email": EMAIL, "password": PASSWORD, "nickname": "SmallTest",
    }, timeout=10)

    r = requests.post(f"{BASE_AUTH}/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    if r.status_code == 403 and "not verified" in r.text:
        # auto-verify via direct DB or show instructions
        log("ERROR: Email not verified. Run this in MySQL:")
        log(f"  UPDATE users SET is_verified=1 WHERE email='{EMAIL}';")
        sys.exit(1)
    r.raise_for_status()
    token = r.json().get("access_token")
    log(f"Logged in as {EMAIL}")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def poll_task(token: str, task_id: str, timeout_s: int = 600, label: str = "") -> dict:
    start = time.monotonic()
    last_progress = -1
    poll_n = 0
    while True:
        poll_n += 1
        elapsed = time.monotonic() - start
        if elapsed > timeout_s:
            raise TimeoutError(f"{label} timed out")
        r = requests.get(f"{BASE_API}/graph/task/{task_id}", headers=auth_headers(token), timeout=10)
        if r.status_code != 200:
            time.sleep(5)
            continue
        data = r.json()
        status, progress, message = data.get("status"), data.get("progress", 0), data.get("message", "")
        detail = data.get("progress_detail_json") or {}
        if progress != last_progress or poll_n % 6 == 0:
            log(f"[{label}] poll#{poll_n} {status} {progress}% '{message}' {detail} {elapsed:.0f}s")
            last_progress = progress
        if status == "completed":
            log(f"[{label}] DONE in {elapsed:.0f}s")
            return data
        if status == "failed":
            raise RuntimeError(f"{label} failed: {data.get('error')}")
        time.sleep(10)


def main() -> None:
    log("=== Task 6 Small E2E Test (first 40K chars of 《平凡的世界》) ===")

    # Read excerpt
    with open(NOVEL_PATH, encoding="utf-8") as f:
        full_text = f.read()
    excerpt = full_text[:MAX_CHARS]
    log(f"Novel excerpt: {len(excerpt):,} chars")

    token = register_or_login()

    # Create project
    r = requests.post(f"{BASE_API}/graph/project", json={
        "name": "平凡的世界-小测试",
        "simulation_requirement": "模拟陕北农村1975-1985年间的社会舆论传播，重点关注孙少平、孙少安等人物的社交网络和舆论影响",
    }, headers=auth_headers(token), timeout=10)
    r.raise_for_status()
    project_id = r.json().get("project_id") or r.json().get("id")
    log(f"Created project: {project_id}")

    # Upload excerpt + generate ontology
    log("--- Generating ontology (LLM call ~2min) ---")
    r = requests.post(
        f"{BASE_API}/graph/ontology/generate",
        data={"project_id": project_id},
        files={"files": ("平凡的世界_excerpt.txt", excerpt.encode("utf-8"), "text/plain")},
        headers=auth_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    ontology_task_id = r.json().get("task_id")
    log(f"Ontology task: {ontology_task_id}")
    ontology_result = poll_task(token, ontology_task_id, timeout_s=600, label="ontology")
    log(f"Ontology: {json.dumps(ontology_result.get('result_json', {}), ensure_ascii=False)}")

    # Build graph
    log("--- Building graph (~5-15 min for 40K chars) ---")
    r = requests.post(f"{BASE_API}/graph/build", json={
        "project_id": project_id,
        "chunk_size": 800,
        "chunk_overlap": 80,
        "batch_size": 5,
    }, headers=auth_headers(token), timeout=15)
    r.raise_for_status()
    build_task_id = r.json().get("task_id")
    log(f"Build task: {build_task_id}")
    build_result = poll_task(token, build_task_id, timeout_s=3600, label="graph_build")
    result_json = build_result.get("result_json", {})
    log(f"Build result:\n{json.dumps(result_json, ensure_ascii=False, indent=2)}")

    graph_id = result_json.get("graph_id") or result_json.get("zep_graph_id")
    assert graph_id, f"No graph_id in result: {result_json}"

    # Test GET /graph/data
    log("--- GET /graph/data ---")
    r = requests.get(f"{BASE_API}/graph/data/{graph_id}", headers=auth_headers(token), timeout=60)
    r.raise_for_status()
    gd = r.json()
    log(f"  nodes={gd['node_count']}, edges={gd['edge_count']}")
    if gd["node_count"] > 0:
        n = gd["nodes"][0]
        log(f"  sample node: name={n.get('name')!r} labels={n.get('labels')}")
    log("  PASSED")

    # Test GET /graph/entities
    log("--- GET /graph/entities ---")
    r = requests.get(f"{BASE_API}/graph/entities/{graph_id}", headers=auth_headers(token), timeout=60)
    r.raise_for_status()
    ge = r.json()
    log(f"  total={ge['total_count']} filtered={ge['filtered_count']} types={ge['entity_types']}")
    log("  PASSED")

    log("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
