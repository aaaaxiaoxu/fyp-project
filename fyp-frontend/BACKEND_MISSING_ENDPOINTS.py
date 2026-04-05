# 添加到你的后端路由文件中

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver

from .neo4j_client import get_neo4j_driver
from .settings import settings
from .graph_schemas import (
    GraphResponse,
    GraphNode,
    GraphEdge,
    SubgraphRequest,
)

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.post("/subgraph", response_model=GraphResponse)
async def get_subgraph(
    req: SubgraphRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> GraphResponse:
    """
    获取子图：从种子节点出发，展开指定深度的关系
    """
    # 验证 eid
    if not req.seed_eid or ":" not in req.seed_eid:
        raise HTTPException(status_code=400, detail="seed_eid must be a valid Neo4j elementId")

    # 验证参数范围
    depth = max(1, min(req.depth, settings.GRAPH_MAX_DEPTH))
    limit_paths = max(1, min(req.limit_paths, settings.GRAPH_MAX_PATHS))
    snippet_len = max(0, min(req.snippet_len, settings.GRAPH_MAX_SNIPPET_LEN))

    # 构建方向模式
    if req.direction == "out":
        pattern = f"(seed)-[*1..{depth}]->(m)"
    elif req.direction == "in":
        pattern = f"(seed)<-[*1..{depth}]-(m)"
    else:  # both
        pattern = f"(seed)-[*1..{depth}]-(m)"

    # Cypher 查询
    cypher = f"""
    MATCH (seed)
    WHERE elementId(seed) = $seed_eid
    MATCH p={pattern}
    WITH p LIMIT $limit_paths
    WITH collect(p) AS paths

    // 提取所有节点
    UNWIND paths AS path
    UNWIND nodes(path) AS node
    WITH collect(DISTINCT node) AS allNodes, paths

    // 提取所有关系
    UNWIND paths AS path2
    UNWIND relationships(path2) AS rel
    WITH allNodes, collect(DISTINCT rel) AS allRels

    // 返回节点（Chunk 不返回 text，只返回 snippet）
    UNWIND allNodes AS n
    WITH
      collect(
        CASE
          WHEN n:Chunk THEN {{
            id: elementId(n),
            labels: labels(n),
            properties: apoc.map.removeKeys(properties(n), ['text']) + {{
              snippet: CASE
                WHEN $include_snippet AND n.text IS NOT NULL AND $snippet_len > 0
                  THEN substring(n.text, 0, $snippet_len)
                ELSE NULL
              END
            }}
          }}
          ELSE {{
            id: elementId(n),
            labels: labels(n),
            properties: properties(n)
          }}
        END
      ) AS nodes_out,
      allRels

    // 返回边
    UNWIND allRels AS r
    WITH nodes_out,
      collect(
        {{
          id: elementId(r),
          type: type(r),
          source: elementId(startNode(r)),
          target: elementId(endNode(r)),
          properties: properties(r)
        }}
      ) AS edges_out

    RETURN nodes_out AS nodes, edges_out AS edges
    """

    params = {
        "seed_eid": req.seed_eid,
        "limit_paths": limit_paths,
        "include_snippet": req.include_snippet,
        "snippet_len": snippet_len,
    }

    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.run(cypher, **params)
        record = await result.single()

    if record is None:
        # 如果种子节点不存在或没有关系
        return GraphResponse(nodes=[], edges=[])

    return GraphResponse(
        nodes=record["nodes"],
        edges=record["edges"]
    )


@router.get("/chunks/by-eid/{chunk_eid}")
async def get_chunk_by_eid(
    chunk_eid: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> dict:
    """
    获取 Chunk 全文（包含 text 字段）
    """
    if not chunk_eid or ":" not in chunk_eid:
        raise HTTPException(status_code=400, detail="chunk_eid must be a valid Neo4j elementId")

    cypher = """
    MATCH (c:Chunk)
    WHERE elementId(c) = $chunk_eid
    RETURN {
      chunk_id: c.chunk_id,
      book_title: c.book_title,
      chapter_id: c.chapter_id,
      start_char: c.start_char,
      end_char: c.end_char,
      text: c.text
    } AS chunk
    """

    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.run(cypher, chunk_eid=chunk_eid)
        record = await result.single()

    if record is None or record.get("chunk") is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return record["chunk"]

