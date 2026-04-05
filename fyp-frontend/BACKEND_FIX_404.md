# 修复 404 错误 - 缺少后端接口

## 🔴 问题

前端调用了两个后端接口，但你的后端代码中没有实现它们：

1. ❌ `POST /graph/subgraph` - 获取子图
2. ❌ `GET /graph/chunks/by-eid/{chunk_eid}` - 获取 Chunk 全文

## ✅ 解决方案

在你的后端路由文件中添加这两个接口。

### 方案 1：使用 APOC 插件（推荐）

如果你的 Neo4j 已安装 APOC 插件，使用 `BACKEND_MISSING_ENDPOINTS.py` 中的代码。

**优点**：
- 代码更简洁
- 性能更好
- 可以动态移除 Chunk.text 字段

### 方案 2：不使用 APOC（兼容性更好）

如果你的 Neo4j 没有安装 APOC，使用 `BACKEND_MISSING_ENDPOINTS_NO_APOC.py` 中的代码。

**优点**：
- 不需要额外插件
- 兼容所有 Neo4j 版本
- 手动指定 Chunk 的字段列表

## 📝 完整的后端代码

将以下代码添加到你的后端路由文件中：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver

from .neo4j_client import get_neo4j_driver
from .settings import settings
from .graph_schemas import GraphResponse, SubgraphRequest

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
    depth = max(1, min(req.depth, 3))
    limit_paths = max(1, min(req.limit_paths, 500))
    snippet_len = max(0, min(req.snippet_len, 200))

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

    // 返回节点（Chunk 只返回部分字段 + snippet）
    UNWIND allNodes AS n
    WITH
      collect(
        CASE
          WHEN n:Chunk THEN {{
            id: elementId(n),
            labels: labels(n),
            properties: {{
              chunk_id: n.chunk_id,
              book_title: n.book_title,
              chapter_id: n.chapter_id,
              start_char: n.start_char,
              end_char: n.end_char,
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
```

## 🔧 settings.py 中需要的常量

确保你的 `settings.py` 中有这些配置：

```python
class Settings(BaseSettings):
    # ... 其他配置 ...
    
    GRAPH_MAX_DEPTH: int = 3
    GRAPH_MAX_PATHS: int = 500
    GRAPH_MAX_SNIPPET_LEN: int = 200
    NEO4J_DATABASE: str = "neo4j"
```

如果没有，可以在代码中直接写死数值：
```python
depth = max(1, min(req.depth, 3))        # 最大深度 3
limit_paths = max(1, min(req.limit_paths, 500))  # 最大路径 500
snippet_len = max(0, min(req.snippet_len, 200))  # 最大片段长度 200
```

## 📊 接口说明

### 1. POST /graph/subgraph

**请求**：
```json
{
  "seed_eid": "4:a1a72633-...:838",
  "depth": 1,
  "direction": "both",
  "limit_paths": 200,
  "include_snippet": true,
  "snippet_len": 120
}
```

**响应**：
```json
{
  "nodes": [
    {
      "id": "4:...",
      "labels": ["Person"],
      "properties": {
        "name": "孙少平",
        ...
      }
    },
    {
      "id": "4:...",
      "labels": ["Chunk"],
      "properties": {
        "chunk_id": "...",
        "book_title": "平凡的世界",
        "chapter_id": "第一章",
        "snippet": "文本片段..."
      }
    }
  ],
  "edges": [
    {
      "id": "5:...",
      "type": "MENTIONED_IN",
      "source": "4:...",
      "target": "4:...",
      "properties": {}
    }
  ]
}
```

### 2. GET /graph/chunks/by-eid/{chunk_eid}

**请求**：
```
GET /graph/chunks/by-eid/4:a1a72633-...:123
```

**响应**：
```json
{
  "chunk_id": "p1_v1_ch001_0001",
  "book_title": "平凡的世界",
  "chapter_id": "第一章",
  "start_char": 0,
  "end_char": 1000,
  "text": "完整的文本内容..."
}
```

## 🚀 测试步骤

1. **添加代码到后端**
2. **重启后端服务**
3. **测试接口**：
   ```bash
   # 测试 catalog
   curl http://127.0.0.1:8000/graph/catalog
   
   # 测试 entities
   curl "http://127.0.0.1:8000/graph/entities?label=Person&limit=5&sort=score"
   
   # 测试 subgraph（需要替换 eid）
   curl -X POST http://127.0.0.1:8000/graph/subgraph \
     -H "Content-Type: application/json" \
     -d '{"seed_eid":"4:xxx:123","depth":1,"direction":"both","limit_paths":200,"include_snippet":true,"snippet_len":120}'
   ```

4. **刷新前端页面**，应该就能正常工作了！

## 🐛 常见问题

### Q1: 还是报 404？
A: 检查后端服务是否重启，路由是否正确注册

### Q2: 返回空数据？
A: 检查 Neo4j 数据库中是否有数据，elementId 是否正确

### Q3: Chunk 的 snippet 是 null？
A: 检查 Chunk 节点是否有 `text` 属性

### Q4: 性能很慢？
A: 
- 减少 `depth` 参数（1-2 即可）
- 减少 `limit_paths` 参数
- 为常用查询建立索引

---

**添加这两个接口后，前端应该就能正常工作了！** ✅

