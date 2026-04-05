# 故障排查指南

## 问题：POST /graph/subgraph 返回 400 Bad Request

### 可能的原因

#### 1. 后端 Neo4j 数据库问题

**检查步骤**：
```bash
# 检查后端服务是否正常运行
curl http://127.0.0.1:8000/docs

# 测试搜索 API（已确认工作正常）
curl "http://127.0.0.1:8000/graph/search/person?q=孙少平&limit=20"

# 测试子图 API
curl -X POST "http://127.0.0.1:8000/graph/subgraph" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_gid": "Person:838",
    "depth": 1,
    "direction": "both",
    "limit_paths": 200,
    "include_snippet": true,
    "snippet_len": 120
  }'
```

**可能的错误**：
- Neo4j 数据库未启动
- Neo4j 中没有数据
- seed_gid 格式不正确
- Neo4j 连接配置错误

#### 2. seed_gid 格式问题

**检查**：
- 确保 gid 格式为 `Person:<id>` 或 `Chunk:<chunk_id>`
- 确保 Person 的 id 是整数
- 确保 Chunk 的 chunk_id 存在

**在浏览器控制台查看**：
```javascript
// 现在已经添加了调试日志
// 打开浏览器控制台（F12）查看 "请求子图参数:" 的输出
```

#### 3. 后端 API 参数校验

**检查后端日志**，看是否有详细的错误信息。

### 临时解决方案

#### 方案 1：使用演示页面

访问演示页面，使用模拟数据测试功能：
```
http://localhost:3000/graph-demo
```

这个页面不需要后端，可以确认前端功能是否正常。

#### 方案 2：检查后端数据库

确保 Neo4j 数据库中有数据：
```cypher
// 检查 Person 节点
MATCH (p:Person) RETURN p LIMIT 5

// 检查 Chunk 节点
MATCH (c:Chunk) RETURN c LIMIT 5

// 检查关系
MATCH (p:Person)-[r]-(n) RETURN p, r, n LIMIT 10
```

### 已改进的错误提示

现在前端会显示更详细的错误信息：
- 浏览器控制台会打印请求参数
- 浏览器控制台会打印后端返回的错误详情
- alert 会显示具体的错误消息（而不是通用的"请检查后端连接"）

### 调试步骤

1. **打开浏览器开发者工具**（F12）
2. **切换到 Console 标签**
3. **尝试搜索人物**
4. **点击搜索结果**
5. **查看控制台输出**：
   - "请求子图参数:" - 查看发送的参数
   - "加载子图失败:" - 查看错误信息
   - "错误详情:" - 查看后端返回的详细错误

### 常见错误及解决方法

#### 错误 1：Invalid gid format
```
原因：seed_gid 格式不正确
解决：确保格式为 "Person:123" 或 "Chunk:abc"
```

#### 错误 2：seed_gid label must be Person or Chunk
```
原因：gid 的 label 部分不是 Person 或 Chunk
解决：检查搜索结果返回的 gid 格式
```

#### 错误 3：Person gid must be Person:<int>
```
原因：Person 的 id 不是整数
解决：确保数据库中 Person 节点的 id 是整数类型
```

#### 错误 4：Chunk not found / Person not found
```
原因：数据库中没有对应的节点
解决：检查 Neo4j 数据库是否有数据
```

#### 错误 5：Connection refused / Network error
```
原因：后端服务未启动或地址错误
解决：
1. 确认后端服务运行在 http://127.0.0.1:8000
2. 检查 nuxt.config.ts 中的 NUXT_PUBLIC_API_BASE 配置
```

### 检查清单

- [ ] 后端服务正常运行（访问 http://127.0.0.1:8000/docs）
- [ ] Neo4j 数据库已启动
- [ ] Neo4j 中有 Person 和 Chunk 节点
- [ ] 搜索 API 返回正确的 gid 格式
- [ ] 浏览器控制台显示详细错误信息
- [ ] 后端日志显示请求详情

### 获取帮助

如果以上步骤都无法解决问题，请提供：

1. **浏览器控制台的完整输出**
2. **后端服务的日志**
3. **Neo4j 数据库的基本信息**：
   ```cypher
   MATCH (n) RETURN DISTINCT labels(n), count(n)
   ```
4. **curl 测试的结果**

### 验证后端可用性

创建一个测试脚本验证后端：

```bash
#!/bin/bash

echo "Testing backend..."

echo "\n1. Testing /docs endpoint:"
curl -s http://127.0.0.1:8000/docs > /dev/null && echo "✅ Backend is running" || echo "❌ Backend is not running"

echo "\n2. Testing search API:"
curl -s "http://127.0.0.1:8000/graph/search/person?q=test&limit=5" && echo "\n✅ Search API works" || echo "\n❌ Search API failed"

echo "\n3. Testing subgraph API:"
curl -s -X POST "http://127.0.0.1:8000/graph/subgraph" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_gid": "Person:1",
    "depth": 1,
    "direction": "both",
    "limit_paths": 200,
    "include_snippet": true,
    "snippet_len": 120
  }' && echo "\n✅ Subgraph API works" || echo "\n❌ Subgraph API failed"
```

### 更新日志

**2024-12-19**：
- ✅ 添加详细的错误日志输出
- ✅ 使用 useApiFetch 确保正确携带 credentials
- ✅ 在控制台打印请求参数
- ✅ 显示后端返回的详细错误信息

