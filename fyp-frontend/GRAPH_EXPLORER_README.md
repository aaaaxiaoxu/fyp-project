# Graph Explorer 页面说明

## 📋 页面概述

`/graph-explorer` 是一个功能完整的知识图谱浏览器，UI 风格类似 Neo4j，提供了更丰富的交互功能。

## 🎯 页面布局

### 三栏布局
```
┌─────────────┬──────────────────────┬────────────┐
│   左侧栏    │     中间画布          │  右侧栏    │
│  实体目录   │   Cytoscape 图谱     │  节点详情  │
│             │                      │            │
│ - 统计      │  - 工具栏            │ - 属性     │
│ - Tab切换   │  - 图谱可视化        │ - Evidence │
│ - 搜索      │  - 空状态提示        │ - 展开按钮 │
│ - 排序      │                      │            │
│ - 列表      │                      │            │
│ - 加载更多  │                      │            │
└─────────────┴──────────────────────┴────────────┘
```

## ✨ 主要功能

### 1. 左侧栏 - 实体目录

#### 统计信息
- 显示 Person 和 Event 总数
- 调用 `GET /graph/catalog` 接口

#### Tab 切换
- **人物** (Person)
- **事件** (Event)

#### 搜索功能
- 实时搜索（300ms 防抖）
- 支持模糊匹配

#### 排序选项
- 按评分 (score)
- 按名称 (name)
- 按首次出现 (first_seen)

#### 实体列表
- 显示实体名称、评分、首次出现章节
- 点击加载对应子图
- 高亮当前选中实体

#### 加载更多
- 每次加载 50 条
- 滚动或点击按钮加载
- 自动检测是否还有更多数据

### 2. 中间画布 - Cytoscape 图谱

#### 工具栏
- 🎯 **适应画布** - 自动调整视图显示所有节点
- 🎯 **居中** - 将图谱居中显示
- 🔄 **重置** - 清空画布
- 🔍 **放大/缩小** - 缩放控制
- 📊 **统计信息** - 显示当前节点和边数量

#### 节点样式
| 类型 | 颜色 | 形状 |
|------|------|------|
| Person | 红色 (#FF6B6B) | 圆形 |
| Event | 橙色 (#FFA500) | 菱形 |
| Chunk | 青色 (#4ECDC4) | 圆角矩形 |

#### 节点标签优先级
1. `properties.name` - 名称
2. `properties.title` - 标题
3. `labels[0] + eid 末段` - 类型+ID

#### 交互操作
- **单击节点** → 显示右侧详情面板
- **双击节点** → 确认后展开（合并到当前图谱）
- **拖拽节点** → 调整位置
- **鼠标滚轮** → 缩放
- **拖拽空白** → 平移画布

#### 布局算法
- 使用 COSE (Compound Spring Embedder)
- 自动计算最优布局
- 平滑动画过渡

### 3. 右侧栏 - 节点详情

#### 节点信息
- **标签** - 显示节点类型（Person/Event/Chunk）
- **属性** - 折叠面板显示所有属性

#### Evidence 列表
- 显示与节点相关的文本证据
- 每个 evidence 显示：
  - 章节 ID
  - 文本片段（snippet）
- 点击 evidence → 打开弹窗显示完整文本

#### 操作按钮
- **展开此节点** - 以当前节点为中心加载子图（合并模式）

### 4. Chunk 全文弹窗

- 模态对话框显示
- 显示书名、章节
- 完整文本内容
- 可滚动查看

## 🔌 API 接口

### 1. GET /graph/catalog
获取统计信息
```json
Response: {
  "person_count": 123,
  "event_count": 45
}
```

### 2. GET /graph/entities
获取实体列表
```
Params:
  - label: Person | Event
  - q: 搜索关键词（可选）
  - sort: score | name | first_seen
  - limit: 50
  - offset: 0

Response: {
  "items": [{
    "eid": "<elementId>",
    "label": "Person",
    "name": "孙少平",
    "score": 123,
    "first_seen_chapter": "第一章"
  }]
}
```

### 3. POST /graph/subgraph
获取子图
```json
Request: {
  "seed_eid": "<elementId>",
  "depth": 1,
  "direction": "both",
  "limit_paths": 200,
  "include_snippet": true
}

Response: {
  "nodes": [{
    "id": "<elementId>",
    "labels": ["Person"],
    "properties": {...}
  }],
  "edges": [{
    "id": "<edgeId>",
    "type": "KNOWS",
    "source": "<sourceId>",
    "target": "<targetId>",
    "properties": {...}
  }]
}
```

### 4. GET /graph/node/by-eid/{eid}
获取节点详情
```json
Response: {
  "eid": "<elementId>",
  "labels": ["Person"],
  "properties": {...}
}
```

### 5. GET /graph/evidence?eid={eid}&limit=100&snippet_len=120
获取证据列表
```json
Response: {
  "items": [{
    "chunk_eid": "<chunkEid>",
    "chunk_id": "...",
    "chapter_id": "第一章",
    "start_char": 0,
    "end_char": 100,
    "snippet": "..."
  }]
}
```

### 6. GET /graph/chunks/by-eid/{chunk_eid}
获取 Chunk 全文
```json
Response: {
  "chunk_id": "...",
  "book_title": "平凡的世界",
  "chapter_id": "第一章",
  "text": "完整文本..."
}
```

## 🎨 代码架构

### Composables 设计

#### 1. useCatalog()
```typescript
返回: {
  catalog: Ref<Catalog | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  fetchCatalog: () => Promise<void>
}
```

#### 2. useEntityList()
```typescript
返回: {
  entities: Ref<Entity[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  hasMore: Ref<boolean>
  fetchEntities: (label, query, sort, reset) => Promise<void>
  loadMore: (label, query, sort) => Promise<void>
}
```

#### 3. useGraph(container)
```typescript
返回: {
  cy: Ref<Core | null>
  nodes: Ref<GraphNode[]>
  edges: Ref<GraphEdge[]>
  selectedNode: Ref<string | null>
  loading: Ref<boolean>
  initCytoscape: () => Promise<void>
  fetchSubgraph: (seedEid, merge) => Promise<void>
  fit: () => void
  center: () => void
  reset: () => void
  zoomIn: () => void
  zoomOut: () => void
}
```

#### 4. useNodeDetail()
```typescript
返回: {
  detail: Ref<NodeDetail | null>
  evidence: Ref<Evidence[]>
  loadingDetail: Ref<boolean>
  loadingEvidence: Ref<boolean>
  error: Ref<string | null>
  loadNodeAndEvidence: (eid) => Promise<void>
}
```

## 🔄 工作流程

### 典型使用流程

1. **进入页面**
   ```
   加载统计信息 (catalog)
   ↓
   加载实体列表 (entities - Person)
   ↓
   初始化 Cytoscape
   ```

2. **搜索实体**
   ```
   输入搜索关键词
   ↓
   防抖 300ms
   ↓
   重新获取实体列表
   ```

3. **加载图谱**
   ```
   点击实体
   ↓
   调用 POST /graph/subgraph
   ↓
   渲染节点和边
   ↓
   自动布局 + 适应画布
   ```

4. **查看详情**
   ```
   单击节点
   ↓
   并行请求：
   - GET /graph/node/by-eid/{eid}
   - GET /graph/evidence?eid={eid}
   ↓
   显示右侧面板
   ```

5. **展开节点**
   ```
   双击节点 或 点击"展开"按钮
   ↓
   用户确认
   ↓
   调用 POST /graph/subgraph (merge=true)
   ↓
   合并新节点和边到现有图谱
   ```

6. **查看全文**
   ```
   点击 evidence 项
   ↓
   GET /graph/chunks/by-eid/{chunk_eid}
   ↓
   弹窗显示完整文本
   ```

## 🎯 与简单版本的区别

| 功能 | graph.vue (简单版) | graph-explorer.vue (完整版) |
|------|-------------------|---------------------------|
| 实体列表 | 只有搜索 | 目录 + 搜索 + 排序 + 分页 |
| 统计信息 | 无 | 有 (catalog) |
| Tab 切换 | 无 | Person / Event |
| 图谱模式 | 单次加载 | 支持合并模式 |
| Evidence | 无 | 完整的 evidence 列表 |
| 节点详情 | 简单 | 完整 (属性 + evidence) |
| Chunk 查看 | 嵌入式 | 弹窗模式 |
| UI 风格 | Vuetify 为主 | Neo4j 风格 |

## 🚀 访问方式

### URL
```
http://localhost:3000/graph-explorer
```

### 导航
- 首页 "Build Graph" 按钮 → graph-explorer
- 导航栏 "Graph Explorer" → graph-explorer
- 导航栏 "Graph (Simple)" → graph（简单版）

## 📱 响应式设计

- **桌面端** (md+)：三栏布局，左右侧栏固定
- **移动端** (<md)：左侧栏可收起，右侧栏临时显示

## ⚡ 性能优化

1. **搜索防抖** - 300ms 延迟，减少 API 调用
2. **分页加载** - 每次 50 条，按需加载
3. **图谱合并** - 避免重复加载相同节点
4. **懒加载** - Cytoscape 按需初始化
5. **错误处理** - 所有 API 调用都有 try/catch

## 🐛 错误处理

- API 调用失败 → console.error + alert 提示
- 加载状态 → Loading 指示器
- 空状态 → 友好的空状态提示
- 网络错误 → 详细错误信息

## 🎨 UI 主题

- **主题色**: 深色 (Dark)
- **背景**: 黑色渐变
- **强调色**: 紫色、蓝色
- **节点色**: 红/橙/青
- **字体**: Material Design Icons

## 📝 代码特点

- ✅ TypeScript 类型安全
- ✅ Composables 模块化
- ✅ 响应式状态管理
- ✅ 清晰的代码结构
- ✅ 完整的错误处理
- ✅ 良好的用户体验

---

**现在可以访问 `/graph-explorer` 开始使用了！** 🚀

