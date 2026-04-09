# FYP Project — 多 Agent 社交模拟系统设计文档 v3

> 本文档替代 v2，作为后续实施的正式基线版本。  
> 核心原则：迁移 MiroFish 的核心业务逻辑，不迁移其原始 Flask + 文件状态架构。
> 当前实施前提已调整为：单租户、无用户认证模块。文中历史性出现的 `user_id`、认证和权限描述，如未专门说明，均不再作为本阶段的功能前提。

---

## 一、项目总览

基于 MiroFish 的核心能力，在 FYP 项目中实现多 Agent 社交模拟系统。  
当前按单租户模式实现四步主流程：

| Step | 名称 | 功能 |
|---|---|---|
| 1 | Graph Build | 上传文档，生成知识图谱 |
| 2 | Environment Setup | 从图谱提取实体，生成 Agent 人设与模拟配置 |
| 3 | Simulation | 通过 OASIS 引擎执行双平台社交模拟 |
| 4 | Explorer Agent | 以 ReACT 模式对模拟世界进行自由问答与 Agent 采访 |

与 MiroFish 的主要差异：

- 不做报告生成，不保留 `report_agent.py` 的分章节报告链路
- Step 4 改为 `Explorer Agent`
- 全部接口改写为 FastAPI
- 状态与任务索引统一纳入 FYP 的 MySQL 体系
- 文件系统只存产物，不再作为主状态源
- 前端页面壳、导航方式、工作区布局默认与 MiroFish 保持一致，不额外暴露头像、邮箱、Profile 一类账户 UI

---

## 二、最终架构决策

### 2.1 总体模式

采用 **原地迁移**，不采用 sidecar。

含义：

- MiroFish 的核心逻辑迁入 FYP 项目内部
- FYP 保持唯一主系统
- FastAPI 是唯一对外 API 层
- MySQL 是唯一主状态源
- `uploads/` 只保存大文件和运行产物

不采用 sidecar 的原因：

- 毕业项目需要体现自主架构整合，而不是外挂一个现成子系统
- 项目、任务、模拟和 Explorer 能力都需要纳入 FYP 主系统统一编排
- 后续前端流程、历史记录和状态恢复都要求单体一致

### 2.2 图谱方案

采用 **Zep Cloud**，废弃原 FYP 中的 Neo4j 路径。

| 对比项 | Neo4j（原 FYP） | Zep Cloud（采用） |
|---|---|---|
| 部署 | 自己运维 | 云托管，API Key 即可 |
| 图谱构建 | 自己写抽取与 Cypher | 直接从文本构图 |
| 检索 | 自己写查询层 | 自带语义搜索与 facts 能力 |
| 时序记忆 | 需自行实现 | 原生更适合模拟中的记忆更新 |
| 迁移成本 | 要重写图谱能力 | 可迁移 MiroFish 大部分图谱服务 |

结论：

- FYP 中已有的 Neo4j 配置保留为历史兼容项，但不再进入新链路
- 新功能统一围绕 Zep 设计

### 2.3 LLM 接口

保持 **OpenAI SDK 兼容接口**。

支持：

- OpenAI
- 阿里百炼
- DeepSeek
- 其他兼容 OpenAI Chat Completions 的服务

通过 `.env` 切换，不改变业务代码。

### 2.4 并发与执行模型

- FastAPI 路由层：异步
- 长任务执行：后台线程
- OASIS 模拟：子进程 `subprocess`
- 模拟交互：文件 IPC

注意：

- OASIS 模拟链路保持同步，不强行改造成 asyncio
- 长任务内部不直接依赖 FastAPI request context
- 任务进度通过专门的状态写入层更新 DB

### 2.5 状态与产物分离

采用 **混合存储**：

- 文件系统：存产物
- MySQL：存状态与索引

文件不是主状态真相。  
DB 才是项目、任务、模拟、Explorer 会话的主状态源。

---

## 三、复用边界

### 3.1 可低改动迁移的模块

以下模块以“低改动迁移”为目标，不承诺零修改。  
主要修改点通常是：配置导入、日志调用、路径常量、repo 调用替换。

| 文件 | 用途 | 迁移说明 |
|---|---|---|
| `services/ontology_generator.py` | LLM 生成本体 | 低改动迁移 |
| `services/text_processor.py` | 文本切块与预处理 | 可直接迁移 |
| `services/graph_builder.py` | Zep 建图 | 低改动迁移 |
| `services/zep_entity_reader.py` | 读取与过滤实体 | 低改动迁移 |
| `services/oasis_profile_generator.py` | 生成人设 | 低改动迁移 |
| `services/simulation_config_generator.py` | 生成模拟配置 | 低改动迁移 |
| `services/simulation_runner.py` | OASIS 运行器 | 中等改动迁移 |
| `services/simulation_manager.py` | 模拟生命周期编排 | 中等改动迁移 |
| `services/simulation_ipc.py` | 子进程 IPC | 低改动迁移 |
| `services/zep_tools.py` | 图谱检索工具 | 低改动迁移 |
| `services/zep_graph_memory_updater.py` | 模拟过程写回图谱 | 低改动迁移 |
| `scripts/run_parallel_simulation.py` | 双平台模拟脚本 | 中等改动迁移 |
| `scripts/action_logger.py` | Agent 动作日志 | 低改动迁移 |
| `utils/llm_client.py` | LLM 客户端 | 可直接迁移 |
| `utils/file_parser.py` | PDF/MD/TXT 解析 | 可直接迁移 |
| `utils/zep_paging.py` | Zep 分页工具 | 可直接迁移 |
| `utils/logger.py` | 日志工具 | 低改动迁移 |

### 3.2 必须重写或显式适配的部分

| 需要改动的部分 | 原因 | 做法 |
|---|---|---|
| Flask `Blueprint` 路由 | FYP 使用 FastAPI | 全部重写为 FastAPI router |
| `request.get_json()` / `jsonify()` / `request.files` | Flask API 风格 | 改为 Pydantic schema + FastAPI `UploadFile` |
| `ProjectManager` | 原实现以文件为主状态源 | 改为 `project_repo + project_file_repo` |
| `TaskManager` | 原实现为内存单例 | 改为 MySQL `tasks` 表 |
| `SimulationManager` 中的状态落盘 | 原实现依赖 `state.json` | 改为 DB 记录状态，文件只存产物 |
| `ReportAgent / ReportManager` | FYP 不做报告生成 | 改写为 `ExplorerAgent` |
| 单租户适配 | MiroFish 无项目体系 | FYP 增加 `project / simulation / task / explorer session` 的数据库索引与恢复锚点 |
| 前端页面 | MiroFish 是 Vue/Vite | 全部按 Nuxt 4 重写，但视觉、布局和交互默认对齐 MiroFish；能直接照抄的页面结构不重新设计 |

### 3.3 复用原则

- 业务逻辑可以迁
- prompt 可以迁
- OASIS 运行脚本可以迁
- 图谱检索工具可以迁
- 前端页面的视觉风格、布局结构和交互方式可以迁
- Flask API 不能迁
- 内存任务管理不能迁
- 文件状态管理不能迁

一句话：

> 迁核心逻辑，不迁原始架构。

补充说明：

> 前端不属于“重新发明产品”的范围。实现方式要迁到 Nuxt 4，但默认产品风格、页面结构和交互骨架应尽量保持与 MiroFish 一致，只对 FYP 的项目体系和状态恢复做必要适配。

---

## 四、存储架构

### 4.1 设计原则

- 文件系统存大对象与运行产物
- MySQL 存状态、索引与关联关系
- 文件路径通过 DB 元数据定位

### 4.2 文件系统结构

```text
uploads/
├── projects/{project_id}/
│   ├── original/
│   │   ├── xxx.pdf
│   │   ├── xxx.md
│   │   └── xxx.txt
│   ├── extracted_text.txt
│   └── ontology.json
│
├── simulations/{simulation_id}/
│   ├── profiles/
│   │   ├── reddit_profiles.json
│   │   └── twitter_profiles.csv
│   ├── simulation_config.json
│   ├── run_state.json
│   ├── env_status.json
│   ├── simulation.log
│   ├── ipc_commands/
│   ├── ipc_responses/
│   ├── twitter/
│   │   └── actions.jsonl
│   ├── reddit/
│   │   └── actions.jsonl
│   ├── twitter_simulation.db
│   └── reddit_simulation.db
│
└── explorer/{simulation_id}/
    ├── sessions/{session_id}.jsonl
    └── console/{session_id}.log
```

说明：

- `twitter_profiles.csv` 保持与 OASIS 运行链路兼容
- `run_state.json` 与 `env_status.json` 属于运行时产物，不作为主状态真相
- `twitter_simulation.db` / `reddit_simulation.db` 为 OASIS 环境数据库
- Explorer 会话日志独立于 simulation 产物

### 4.3 MySQL 负责的内容

- 项目元信息
- 上传文件索引
- 图谱状态
- 模拟状态
- 长任务状态
- Explorer 会话索引
- 错误信息
- 时间戳

---

## 五、数据库表设计

在 `models.py` 中新增：

### 5.1 Project

```python
class Project(Base):
    __tablename__ = "projects"

    id: str                      # proj_xxxx
    user_id: str                 # FK -> users.id
    name: str
    status: str                  # created | ontology_generated | graph_building | graph_completed | failed
    zep_graph_id: str | None     # Zep graph_id
    simulation_requirement: str
    ontology_path: str | None    # uploads 相对路径
    extracted_text_path: str | None
    created_at: datetime
    updated_at: datetime
```

### 5.2 ProjectFile

```python
class ProjectFile(Base):
    __tablename__ = "project_files"

    id: str
    project_id: str              # FK -> projects.id
    original_name: str
    stored_path: str             # 相对于 UPLOAD_FOLDER
    file_type: str               # pdf | md | txt
    size_bytes: int
    created_at: datetime
```

### 5.3 Simulation

```python
class Simulation(Base):
    __tablename__ = "simulations"

    id: str                      # sim_xxxx
    project_id: str              # FK -> projects.id
    user_id: str                 # FK -> users.id
    status: str                  # created | preparing | ready | running | completed | stopped | failed
    twitter_enabled: bool
    reddit_enabled: bool
    interactive_ready: bool      # 环境是否可被 Explorer / Interview 使用
    total_rounds: int | None
    current_round: int
    twitter_actions_count: int
    reddit_actions_count: int
    config_path: str | None
    profiles_dir: str | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### 5.4 Task

```python
class Task(Base):
    __tablename__ = "tasks"

    id: str                      # task_xxxx
    project_id: str | None       # FK -> projects.id
    simulation_id: str | None    # FK -> simulations.id
    user_id: str
    task_type: str               # ontology_generate | graph_build | sim_prepare | explorer_query
    status: str                  # pending | processing | completed | failed
    progress: int                # 0-100
    message: str
    result_json: JSON | None
    progress_detail_json: JSON | None
    error: str | None
    created_at: datetime
    updated_at: datetime
```

### 5.5 ExplorerSession

```python
class ExplorerSession(Base):
    __tablename__ = "explorer_sessions"

    id: str
    simulation_id: str           # FK -> simulations.id
    user_id: str                 # FK -> users.id
    title: str
    status: str                  # active | closed | failed
    log_path: str | None
    created_at: datetime
    updated_at: datetime
```

---

## 六、Repository / Service 分层

### 6.1 目录结构

```text
src/
├── adapters/
│   └── task_state_writer.py
│
├── repositories/
│   ├── project_repo.py
│   ├── project_file_repo.py
│   ├── simulation_repo.py
│   ├── task_repo.py
│   └── explorer_session_repo.py
│
├── utils/
│   └── path_resolver.py
│
├── services/
│   ├── ontology_generator.py
│   ├── text_processor.py
│   ├── graph_builder.py
│   ├── zep_entity_reader.py
│   ├── oasis_profile_generator.py
│   ├── simulation_config_generator.py
│   ├── simulation_manager.py
│   ├── simulation_runner.py
│   ├── simulation_ipc.py
│   ├── zep_tools.py
│   ├── zep_graph_memory_updater.py
│   └── explorer_agent.py
```

### 6.2 替换规则

MiroFish 原来的：

- `ProjectManager`
- `TaskManager`
- `ReportManager`

在 FYP 中分别替换为：

- `project_repo`
- `task_repo`
- `simulation_repo`
- `explorer_session_repo`

### 6.3 关键适配原则

- service 内部的核心逻辑尽量不改
- service 不直接理解 MySQL schema
- repo 负责 DB 访问
- `src/utils/path_resolver.py` 负责把 `project_id` / `simulation_id` 映射为文件路径

### 6.4 长任务状态更新策略

由于 FYP 当前主要使用 async SQLAlchemy，而图谱构建 / 模拟准备 / Explorer 推理会运行在线程或子进程中，因此状态写入采用专门适配层：

- 路由层：异步
- worker 层：同步
- `src/adapters/task_state_writer.py`：专门负责从 worker 更新 DB 任务状态

约束：

- 不在核心 service 内部直接 `await repo.xxx()`
- 由外层 orchestration 注入 `progress_callback`
- `progress_callback` 内部再调用状态写入适配层

这样可以避免把异步 repo 逻辑污染到同步 service 中。

---

## 七、FastAPI 路由结构

### 7.1 路由目录

```text
src/routers/
├── graph.py
├── simulation.py
└── explorer.py
```

### 7.2 `main.py` 注册

```python
app.include_router(graph_router,      prefix="/api/graph")
app.include_router(simulation_router, prefix="/api/simulation")
app.include_router(explorer_router,   prefix="/api/explorer")
```

### 7.3 Graph 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/graph/project` | 创建项目并写入项目元信息 |
| GET | `/api/graph/project/{project_id}` | 查询项目详情 |
| GET | `/api/graph/projects` | 查询项目列表 |
| DELETE | `/api/graph/project/{project_id}` | 删除项目 |
| POST | `/api/graph/ontology/generate` | 向已有项目上传文件并生成本体，返回 `task_id` |
| GET | `/api/graph/task/{task_id}` | 查询任务进度 |
| POST | `/api/graph/build` | 构建 Zep 图谱，返回 `task_id` |
| GET | `/api/graph/data/{graph_id}` | 获取图谱节点与边 |
| GET | `/api/graph/entities/{graph_id}` | 获取图谱实体列表 |

说明：

- `POST /api/graph/project` 的请求体至少包含：
  - `name`
  - `simulation_requirement`
- `POST /api/graph/ontology/generate` 的请求体包含：
  - `project_id`
  - 原始文档文件列表
- 因此项目创建与文件上传为两个连续步骤：
  - 先创建项目元信息
  - 再上传文件并触发本体生成

### 7.4 Simulation 路由

#### Step 2

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/simulation/prepare/{project_id}` | 生成人设与模拟配置，返回 `task_id` |
| GET | `/api/simulation/prepare/status/{task_id}` | 查询 prepare 进度 |
| GET | `/api/simulation/{simulation_id}/config` | 查看模拟配置 |
| GET | `/api/simulation/{simulation_id}/profiles` | 查看 Agent 人设列表 |

#### Step 3

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/simulation/start/{simulation_id}` | 启动模拟 |
| GET | `/api/simulation/status/{simulation_id}` | 查询实时状态与最近动作 |
| POST | `/api/simulation/stop/{simulation_id}` | 停止模拟 |
| GET | `/api/simulation/actions/{simulation_id}` | 获取完整动作日志 |

### 7.5 Explorer 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/explorer/ask` | 向 Explorer Agent 提问，SSE 流式返回 |
| POST | `/api/explorer/interview/{agent_id}` | 采访指定 Agent |
| GET | `/api/explorer/history/{simulation_id}` | 获取该模拟的问答历史 |

说明：

- Explorer 的稳定标识使用 `agent_id`，不使用 `agent_name`
- `agent_id` 对应 OASIS profiles 中的 `user_id` 整数字段，由 simulation prepare 阶段生成并写入 profile 产物文件
- 前端不强制展示原始 `Thought`
- 对前端暴露 `tool_call` / `tool_result` / `answer_chunk` / `final_answer` 更合适
- 每次 `ask` / `interview` 都要将问答轮次追加写入 `uploads/explorer/{simulation_id}/sessions/{session_id}.jsonl`
- `ExplorerSession` 表负责保存会话索引，JSONL 文件负责保存具体轮次内容

---

## 八、Explorer Agent 设计

### 8.1 目标

Explorer Agent 代替原 MiroFish 的报告生成 Agent，提供：

- 对模拟世界自由问答
- 图谱事实检索
- 采访模拟中的 Agent
- 会话式探索

### 8.2 复用基础

从 `report_agent.py` 中提取：

- 工具定义方式
- ReACT 循环框架
- 工具调用解析
- Zep 工具执行逻辑

移除：

- 报告大纲规划
- 章节生成
- Markdown 章节持久化

### 8.3 工具集

Explorer Agent 初期保留以下工具：

- `insight_forge`
- `panorama_search`
- `quick_search`
- `interview_agents`

### 8.4 SSE 输出事件建议

建议后端 SSE 输出以下 event 类型：

- `status`
- `tool_call`
- `tool_result`
- `answer_chunk`
- `final_answer`
- `error`

不建议把原始 chain-of-thought 作为前端正式输出的一部分。  
若需要调试，可单独保存在 Explorer session 日志中。

---

## 九、分阶段 MVP

### MVP-0：基础设施

目标：搭好迁移骨架。

- `settings.py` 增加 Zep / LLM / Upload 配置
- `requirements.txt` 增加 Zep / OpenAI / OASIS 依赖
- `models.py` 新增 `Project / ProjectFile / Simulation / Task / ExplorerSession`
- 创建 `repositories/`
- 迁移 `utils/llm_client.py`、`file_parser.py`、`zep_paging.py`、`logger.py`
- 定义 uploads 路径规则

### MVP-1：Step 1 Graph Build

目标：前端可上传文档并完成图谱构建。

- 迁移 `ontology_generator.py`、`text_processor.py`、`graph_builder.py`
- 重写 `graph.py` FastAPI router
- 前端实现：
  - 文件上传
  - 本体进度轮询
  - 图谱构建进度轮询
  - 图谱可视化

图谱可视化建议：

- 优先使用项目已安装的 `cytoscape`
- 若后续需要高定制动画，再引入 D3

### MVP-2：Step 2 Environment Setup

目标：前端可看到实体、人设和模拟配置。

- 迁移 `zep_entity_reader.py`
- 迁移 `oasis_profile_generator.py`
- 迁移 `simulation_config_generator.py`
- 重写 `simulation.py` 的 prepare 相关接口
- 前端实现：
  - Agent 人设卡片
  - 模拟配置预览

### MVP-3：Step 3 Simulation

目标：前端可启动模拟并实时看到 Agent 动作流。

- 迁移 `simulation_runner.py`
- 迁移 `simulation_manager.py`
- 迁移 `simulation_ipc.py`
- 迁移 `zep_graph_memory_updater.py`
- 迁移 `run_parallel_simulation.py`
- 迁移 `action_logger.py`
- 重写模拟启动、状态查询、停止接口
- 前端实现双平台动作流与进度展示

### MVP-4：Step 4 Explorer Agent

目标：前端可对模拟世界提问，并采访 Agent。

- 迁移 `zep_tools.py`
- 新建 `explorer_agent.py`
- 新建 `explorer.py` router
- 前端实现：
  - Explorer 对话界面
  - SSE 流式显示
  - Agent 采访入口
  - 会话历史展示

---

## 十、验收标准

### MVP-0 验收

- `uvicorn src.main:app` 能正常启动
- `GET /api/graph/projects` 返回 200
- MySQL 中可见新增的 `projects / project_files / simulations / tasks / explorer_sessions`

### MVP-1 验收

- 能上传 PDF / MD / TXT
- `POST /api/graph/ontology/generate` 返回 `task_id`
- 轮询任务可看到进度从 0 到 100
- `uploads/projects/{id}/ontology.json` 存在且结构合法
- `POST /api/graph/build` 完成后 `projects.zep_graph_id` 已写入 DB
- `GET /api/graph/data/{graph_id}` 返回节点与边

### MVP-2 验收

- `POST /api/simulation/prepare/{project_id}` 可触发任务
- 任务完成后存在：
  - `uploads/simulations/{id}/profiles/reddit_profiles.json`
  - `uploads/simulations/{id}/profiles/twitter_profiles.csv`
  - `uploads/simulations/{id}/simulation_config.json`
- `GET /api/simulation/{simulation_id}/config` 返回完整配置

### MVP-3 验收

- `POST /api/simulation/start/{id}` 后，`simulations.status = running`
- `GET /api/simulation/status/{id}` 可返回：
  - `current_round`
  - `twitter_actions_count`
  - `reddit_actions_count`
  - `recent_actions`
- 模拟完成后：
  - `uploads/simulations/{id}/twitter/actions.jsonl` 有内容
  - `uploads/simulations/{id}/reddit/actions.jsonl` 有内容
- `simulations.status` 最终变为 `completed` 或 `stopped`
- `interactive_ready = true` 时可执行采访

### MVP-4 验收

- `POST /api/explorer/ask` 能返回 SSE 流
- SSE 中至少能看到：
  - `tool_call`
  - `tool_result`
  - `answer_chunk`
  - `final_answer`
- `POST /api/explorer/interview/{agent_id}` 能让指定 Agent 以人设身份作答
- Explorer 回答内容能够引用 Zep 图谱中的真实 facts

---

## 十一、技术栈汇总

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | MySQL + SQLAlchemy + asyncmy |
| 图谱 | Zep Cloud |
| LLM | OpenAI SDK 兼容接口 |
| 多 Agent 模拟 | camel-ai + camel-oasis |
| 文档解析 | PyMuPDF + 原生文本读取 |
| 前端 | Nuxt 4 + Vuetify |
| 图谱可视化 | Cytoscape（优先） |

---

## 十二、依赖清单

建议新增：

```txt
zep-cloud>=3.13.0
openai>=1.30.0
camel-ai>=0.2.78
camel-oasis>=0.2.5
PyMuPDF>=1.24.0
charset-normalizer>=3.0.0
chardet>=5.0.0
```

---

## 十三、环境变量

```env
# Zep Cloud
ZEP_API_KEY=your_zep_api_key

# LLM
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# 文件存储
UPLOAD_FOLDER=./uploads
MAX_FILE_SIZE_MB=50
```

---

## 十四、实施备注

1. v3 的核心修正是：不再声称“零修改复用”
2. 文件系统产物结构与 OASIS 运行链路保持兼容
3. Twitter profile 文件格式修正为 CSV
4. 任务表新增 `simulation_id`
5. Explorer 接口以 `agent_id` 为稳定标识
6. 前端流式交互默认不展示原始 chain-of-thought
7. 前端版本基线采用 `Nuxt 4`，与当前 `fyp-frontend` 的 `nuxt@^4.2.2` 保持一致

---

## 十五、一句话总纲

> FYP 的目标不是复制 MiroFish 的完整工程，而是把它最有价值的“图谱构建 + 多 Agent 社交模拟 + 图谱检索问答”能力内化进自己的 FastAPI + MySQL + Nuxt 体系中。
