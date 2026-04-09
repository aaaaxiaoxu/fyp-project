# FYP Project — MiroFish 迁移任务拆解与验收标准 v2

> 本文档用于承接 [FYP_MiroFish_Migration_v3.md](/Users/xuliwei/github-project/fyp-project/docs/FYP_MiroFish_Migration_v3.md)，将设计方案拆解为可执行开发任务。
> 本版本已修正任务归属不清、轮询接口缺失、工具类迁移遗漏、`interactive_ready` 写入责任不明确等问题。

---

## 一、文档目标

本清单用于指导 FYP 项目按阶段落地以下能力：

1. 文档上传与知识图谱构建
2. 基于图谱生成人设与模拟配置
3. 启动并管理多 Agent 社交模拟
4. 通过 Explorer Agent 对模拟世界进行问答与采访

要求：

- 任务必须能直接分配给开发实现
- 每个任务必须有明确输入、输出、依赖和验收标准
- 任务接口归属必须清晰，避免前后任务互相等待

---

## 二、执行约束

### 2.1 全局约束

- FastAPI 是唯一对外 API 层
- MySQL 是唯一主状态源
- `uploads/` 只存大文件和运行产物，不作为主状态真相
- 所有 `project / simulation / task / explorer_session` 均必须绑定 `user_id`

### 2.2 任务状态能力归属

- Task 3 负责通用任务状态存取能力：`Task` 表访问、`task_repo`、`task_state_writer`
- Task 5 负责 Graph 域轮询接口：`GET /api/graph/task/{task_id}`
- Task 8 负责 Simulation Prepare 域轮询接口：`GET /api/simulation/prepare/status/{task_id}`

说明：

- 通用任务状态能力和具体 HTTP endpoint 分离
- 业务 router 负责把对应任务状态暴露为 API

### 2.3 `interactive_ready` 字段责任归属

- 唯一写入方：Task 10 中的 `simulation_manager`
- 默认值：`false`
- 置为 `true` 的条件：
  - 模拟运行完成为 `completed`，且运行产物完整
  - 或模拟被正常停止为 `stopped`，且采访所需产物仍完整可用
- Task 13 只读取该字段，不负责写入

### 2.4 Sprint 建议

- Task 2 和 Task 3 必须视为同一开发单元连续交付
- Task 10 和 Task 11 必须连续联调
- Task 13 依赖 Task 6 与 Task 10 的结果，不可提前独立关闭

### 2.5 前端对齐原则

- 所有前端任务默认以 `MiroFish/frontend` 为视觉、布局和交互基线
- 只要 MiroFish 现有页面结构、面板布局、信息层级、文案组织和交互流程可直接复用，就不要重新设计一套新风格
- 前端允许的改动只应来自 FYP 的必要适配：
  - Nuxt 4 实现方式差异
  - 登录态与 `user_id` 归属
  - `project_id / task_id / simulation_id` 恢复锚点
  - FYP 新增的项目列表、项目选择等 MiroFish 原本没有的能力
- 前端不展示额外的 FYP 用户态 UI：
  - 不额外展示头像、昵称、邮箱、Profile、Sign out 等顶部账户模块
  - 若认证仍然存在，应尽量收敛为路由守卫或独立认证页，不破坏 MiroFish 页面壳
- Task 7 / Task 9 / Task 12 / Task 14 都必须明确说明所参考的 MiroFish 页面或组件
- 若中间阶段为了先打通功能而存在临时样式，必须在 Task 14 做统一收口，最终整体前端风格须与 MiroFish 保持一致

---

## 三、任务清单

## Task 1：基础配置、依赖与通用工具迁移

### 目标

建立迁移所需的运行基线，让后续服务迁移不再被环境和公共工具阻塞。

### 工作内容

- 扩展 `fyp-backend/src/settings.py`
- 增加 Zep、LLM、Upload、文件大小限制等配置
- 更新 `fyp-backend/requirements.txt`
- 引入 Zep Cloud、OpenAI SDK 兼容依赖、OASIS 相关依赖、文档解析依赖
- 迁移并整理以下通用工具：
  - `utils/llm_client.py`
  - `utils/file_parser.py`
  - `utils/zep_paging.py`
  - `utils/logger.py`
- 建立基础目录规则：
  - `uploads/projects/`
  - `uploads/simulations/`
  - `uploads/explorer/`

### 主要输出

- 可加载的新配置项
- 可导入的通用工具模块
- 更新后的依赖清单
- 可创建的 uploads 根目录结构

### 依赖

- 无

### 验收标准

- `uvicorn src.main:app` 能正常启动
- 缺失 `ZEP_API_KEY`、`LLM_API_KEY` 等关键配置时有明确报错或启动期校验
- 新增依赖安装后，工具模块可正常导入
- `llm_client.py`、`file_parser.py`、`zep_paging.py`、`logger.py` 已进入 FYP 后端代码树

---

## Task 2：数据库模型与状态枚举落地

### 目标

把设计文档中的核心业务对象正式落到 MySQL schema 中。

### 工作内容

- 在 `models.py` 中新增：
  - `Project`
  - `ProjectFile`
  - `Simulation`
  - `Task`
  - `ExplorerSession`
- 定义状态字段、时间戳、用户归属和外键关系
- 明确关键状态枚举：
  - `projects.status`
  - `simulations.status`
  - `tasks.status`
  - `explorer_sessions.status`

### 主要输出

- 新的数据模型
- 与设计文档一致的字段定义

### 依赖

- Task 1

### 验收标准

- MySQL 中可见 `projects / project_files / simulations / tasks / explorer_sessions`
- 能成功插入并查询带 `user_id` 的 `Project`、`Simulation`、`Task`
- `Simulation.interactive_ready` 字段存在，默认值为 `false`

---

## Task 3：Repository、路径解析与任务状态适配层

### 目标

建立后端可复用的数据访问层和任务状态更新机制，支撑所有后台长任务。

### 工作内容

- 创建 `repositories/`
- 实现：
  - `project_repo.py`
  - `project_file_repo.py`
  - `simulation_repo.py`
  - `task_repo.py`
  - `explorer_session_repo.py`
- 新建 `utils/path_resolver.py`
- 新建 `adapters/task_state_writer.py`
- 定义通用任务状态能力：
  - 创建任务
  - 更新 `status / progress / message / error / result_json`
  - 按 `task_id + user_id` 查询任务

### 主要输出

- 可复用的 repo 层
- 统一路径解析能力
- worker 可调用的任务状态写入能力

### 依赖

- Task 2

### 验收标准

- repo 层可完成项目、文件、模拟、任务、会话的基础 CRUD
- `task_state_writer` 可在非 request 上下文中更新任务状态
- 通过 `task_repo` 能按 `task_id` 查询到 `progress`、`message`、`result_json`
- 明确约束：Task 3 不直接提供业务 router endpoint

---

## Task 4：项目管理与项目元信息接口

### 目标

先打通 Step 1 的项目入口，建立项目元信息和后续文档处理的归属锚点。

### 工作内容

- 新建 `src/routers/graph.py`
- 实现接口：
  - `POST /api/graph/project`
  - `GET /api/graph/project/{project_id}`
  - `GET /api/graph/projects`
  - `DELETE /api/graph/project/{project_id}`
- `POST /api/graph/project` 负责采集项目基础信息：
  - `name`
  - `simulation_requirement`
- 说明：
  - Task 4 不负责原始文件上传
  - 原始文件上传与本体生成统一由 Task 5 的 `POST /api/graph/ontology/generate` 完成

### 主要输出

- Graph 域基础 router
- 项目元信息管理

### 依赖

- Task 2
- Task 3

### 验收标准

- 登录用户可创建、查看、列出、删除自己的项目
- `POST /api/graph/project` 创建时可写入 `simulation_requirement`
- 用户不能访问或删除他人的项目

---

## Task 5：文本解析、本体生成与 Graph 任务轮询接口

### 目标

完成 Step 1 的第一段后台任务：从上传文档生成抽取文本和本体文件。

### 工作内容

- 迁移并接入：
  - `text_processor.py`
  - `ontology_generator.py`
- 调用 Task 1 迁移的 `file_parser.py`
- 实现接口：
  - `POST /api/graph/ontology/generate`
  - `GET /api/graph/task/{task_id}`
- 后台任务负责：
  - 接收 `project_id` 和上传文件
  - 保存原始文件到 `uploads/projects/{project_id}/original/`
  - 写入 `ProjectFile` 索引记录
  - 解析文档
  - 生成 `extracted_text.txt`
  - 生成 `ontology.json`
  - 持续更新 `tasks.progress`

### 主要输出

- 文档解析与本体生成能力
- Graph 域任务轮询接口
- Graph 域文件上传落盘能力

### 依赖

- Task 1
- Task 3
- Task 4

### 验收标准

- `POST /api/graph/ontology/generate` 返回 `task_id`
- `POST /api/graph/ontology/generate` 可接收 PDF / MD / TXT 并绑定到指定 `project_id`
- `GET /api/graph/task/{task_id}` 返回 200，且只能查询当前用户任务
- 轮询过程中 `progress` 能从 0 逐步推进到 100
- 原始文件已落到 `uploads/projects/{project_id}/original/`
- `project_files` 表存在对应文件索引
- 成功后生成：
  - `uploads/projects/{project_id}/extracted_text.txt`
  - `uploads/projects/{project_id}/ontology.json`
- 任务失败时 `tasks.status = failed` 且 `error` 有内容

---

## Task 6：Zep 图谱构建与图谱查询接口

### 目标

完成 Step 1 的第二段后台任务：把本体和文本送入 Zep 构建图谱，并向前端暴露查询接口。

### 工作内容

- 迁移并接入：
  - `graph_builder.py`
  - `zep_paging.py`
- 实现接口：
  - `POST /api/graph/build`
  - `GET /api/graph/data/{graph_id}`
  - `GET /api/graph/entities/{graph_id}`
- 图谱构建完成后写回：
  - `projects.zep_graph_id`
  - `projects.status`

### 主要输出

- Zep 图谱构建能力
- 图谱查询能力

### 依赖

- Task 1
- Task 3
- Task 5

### 验收标准

- `POST /api/graph/build` 可启动图谱构建任务
- 构建成功后 `projects.zep_graph_id` 已写入 DB
- `GET /api/graph/data/{graph_id}` 返回节点与边
- `GET /api/graph/entities/{graph_id}` 返回实体列表
- 非项目所属用户无法读取对应图谱数据

---

## Task 7：Step 1 前端页面与图谱可视化

### 目标

让用户可从前端完成文档上传、本体生成、图谱构建和图谱浏览。

### 工作内容

- 新建或改造 Nuxt 页面
- 以前端结构对齐 MiroFish Step 1 为默认方案，优先复刻其 `graph / split / workbench` 布局、Graph Panel、Step 卡片区和 System Logs 区
- 参考来源至少包括：
  - `MiroFish/frontend/src/views/MainView.vue`
  - `MiroFish/frontend/src/components/Step1GraphBuild.vue`
  - `MiroFish/frontend/src/components/GraphPanel.vue`
- 接入文件上传
- 接入本体任务轮询
- 接入图谱构建任务轮询
- 使用 `cytoscape` 实现图谱可视化
- 在不破坏 MiroFish 原有布局风格的前提下，补入 FYP 所需的项目列表、项目选择和项目详情
- FYP 新增的项目入口应以内嵌的任务模块或工作台卡片承载，不应替换成新的顶部账户栏或用户信息区
- 不允许为 Task 7 单独设计一套脱离 MiroFish 的全新视觉风格

### 主要输出

- Step 1 完整前端流程
- 与 MiroFish Step 1 基本一致的前端风格与交互骨架

### 依赖

- Task 4
- Task 5
- Task 6

### 验收标准

- 用户可在前端上传 PDF / MD / TXT
- 用户可看到本体生成任务的实时进度
- 用户可发起图谱构建并看到完成状态
- 图谱页面可展示节点与边
- 刷新页面后项目状态和图谱仍可恢复显示
- 页面主布局、视觉风格和交互分区应与 MiroFish Step 1 基本一致，而不是另起一套产品 UI

---

## Task 8：Environment Prepare 后端与 Prepare 任务轮询接口

### 目标

完成 Step 2 后端：从图谱中提取实体，生成 Agent 人设和模拟配置。

### 工作内容

- 迁移并接入：
  - `zep_entity_reader.py`
  - `oasis_profile_generator.py`
  - `simulation_config_generator.py`
- 实现接口：
  - `POST /api/simulation/prepare/{project_id}`
  - `GET /api/simulation/prepare/status/{task_id}`
  - `GET /api/simulation/{simulation_id}/config`
- 生成以下产物：
  - `profiles/reddit_profiles.json`
  - `profiles/twitter_profiles.csv`
  - `simulation_config.json`
- Prepare 任务过程中持续写入任务进度
- 完成后创建 `Simulation` 记录并回填 `simulation_id`

### 主要输出

- Step 2 后端能力
- Prepare 域任务轮询接口

### 依赖

- Task 3
- Task 6

### 验收标准

- `POST /api/simulation/prepare/{project_id}` 返回 `task_id`
- `GET /api/simulation/prepare/status/{task_id}` 返回 200，且只能查询当前用户任务
- 轮询过程中 `progress` 能从 0 逐步推进到 100
- 任务完成后存在：
  - `uploads/simulations/{simulation_id}/profiles/reddit_profiles.json`
  - `uploads/simulations/{simulation_id}/profiles/twitter_profiles.csv`
  - `uploads/simulations/{simulation_id}/simulation_config.json`
- `GET /api/simulation/{simulation_id}/config` 返回完整配置
- 任务完成后 `tasks.result_json` 中可拿到 `simulation_id`

---

## Task 9：Step 2 前端展示

### 目标

让用户在前端查看实体、人设和模拟配置，确认模拟准备结果。

### 工作内容

- 展示 prepare 进度
- 展示 Agent 人设卡片
- 展示平台开关、轮次、配置摘要
- 标出稳定 `agent_id`
- 以前端结构对齐 MiroFish Step 2 为默认方案，优先复刻其信息编排、卡片样式和导航关系
- 仅对 FYP 的字段名、接口返回结构和恢复锚点做必要适配，不重新设计新页面风格

### 主要输出

- Step 2 前端确认页面
- 与 MiroFish Step 2 保持一致的前端风格延续

### 依赖

- Task 8

### 验收标准

- 用户能看到 prepare 任务进度
- 用户能看到完整 Agent 列表与主要人设字段
- 用户能查看 `simulation_config.json` 的关键配置
- 页面可基于 `simulation_id` 恢复结果展示
- 页面风格、信息层级和交互路径应延续 MiroFish Step 2，而不是切换成另一套设计体系

---

## Task 10：模拟启动编排、运行器迁移与 `interactive_ready` 写入

### 目标

完成 Step 3 的核心运行能力，使模拟能够被正式启动并推进。

### 工作内容

- 迁移并接入：
  - `simulation_runner.py`
  - `simulation_manager.py`
  - `simulation_ipc.py`
  - `run_parallel_simulation.py`
  - `action_logger.py`
  - `zep_graph_memory_updater.py`
- 实现接口：
  - `POST /api/simulation/start/{simulation_id}`
- 负责：
  - 启动 OASIS 子进程
  - 驱动双平台模拟
  - 回写 `simulations.status`
  - 更新轮次和动作计数
  - 根据产物完整性写入 `interactive_ready`
  - 直接通过 DB 更新验证运行态字段，无需依赖 Task 11 的查询接口

### 主要输出

- 模拟启动能力
- 子进程编排能力
- `interactive_ready` 唯一写入逻辑

### 依赖

- Task 8

### 验收标准

- `POST /api/simulation/start/{simulation_id}` 返回 200 或已接受执行状态
- 调用后 `simulations.status` 进入 `running`
- 模拟过程中 `current_round`、动作计数可持续更新
  - 该项可直接通过 DB 查询验证，不依赖 Task 11 的 `GET /api/simulation/status/{simulation_id}`
- 运行结束后：
  - 若正常完成，`simulations.status = completed`
  - 若用户正常停止，`simulations.status = stopped`
  - 若异常退出，`simulations.status = failed`
- `interactive_ready` 仅由该任务写入
- 当模拟完成或可恢复停止且产物完整时，`interactive_ready = true`

---

## Task 11：模拟状态、动作流与停止接口

### 目标

把 Step 3 的运行态信息对前端开放出来，支持查看状态、动作日志和主动停止。

### 工作内容

- 实现接口：
  - `GET /api/simulation/status/{simulation_id}`
  - `GET /api/simulation/actions/{simulation_id}`
  - `POST /api/simulation/stop/{simulation_id}`
- 聚合最近动作
- 输出当前轮次、动作统计和错误信息
- 读取 `twitter/actions.jsonl`、`reddit/actions.jsonl`

### 主要输出

- 模拟查询接口
- 动作流接口
- 停止接口

### 依赖

- Task 10

### 验收标准

- `GET /api/simulation/status/{simulation_id}` 返回：
  - `current_round`
  - `twitter_actions_count`
  - `reddit_actions_count`
  - `recent_actions`
  - `interactive_ready`
- `GET /api/simulation/actions/{simulation_id}` 可返回完整动作日志
- `POST /api/simulation/stop/{simulation_id}` 可停止正在运行的模拟
- 运行后存在：
  - `uploads/simulations/{simulation_id}/twitter/actions.jsonl`
  - `uploads/simulations/{simulation_id}/reddit/actions.jsonl`

---

## Task 12：Step 3 前端模拟控制台

### 目标

让用户可在前端启动、查看和停止模拟，并实时浏览双平台动作流。

### 工作内容

- 增加模拟启动按钮
- 轮询状态接口
- 展示 Twitter / Reddit 双平台动作流
- 展示轮次、动作统计、运行状态
- 接入停止按钮
- 以前端结构对齐 MiroFish Step 3 为默认方案，优先复刻其控制台布局、动作流呈现和状态区组织方式
- 仅对 FYP 的任务状态接口、字段结构和入口路由做必要适配，不重新设计新控制台风格

### 主要输出

- Step 3 前端控制台
- 与 MiroFish Step 3 保持一致的前端控制台样式

### 依赖

- Task 10
- Task 11

### 验收标准

- 用户可从前端启动模拟
- 前端可实时展示轮次和最新动作
- 用户可停止模拟，页面状态同步更新
- `interactive_ready = true` 时前端展示进入 Explorer 的入口
- 页面整体视觉、动作流组织和控制区布局应与 MiroFish Step 3 一致

---

## Task 13：Explorer Agent 后端

### 目标

完成 Step 4 后端，让系统可以基于图谱和模拟结果进行问答与采访。

### 工作内容

- 迁移 `zep_tools.py`
- 新建 `services/explorer_agent.py`
- 新建 `routers/explorer.py`
- 实现接口：
  - `POST /api/explorer/ask`
  - `POST /api/explorer/interview/{agent_id}`
  - `GET /api/explorer/history/{simulation_id}`
- 建立和维护 `ExplorerSession`：
  - 创建或复用会话索引记录
  - 更新 `log_path`
  - 更新 `updated_at`
- 每次 `ask` / `interview` 都要把问答轮次 append 到：
  - `uploads/explorer/{simulation_id}/sessions/{session_id}.jsonl`
- 必要时写入调试日志到：
  - `uploads/explorer/{simulation_id}/console/{session_id}.log`
- 实现 SSE 事件流：
  - `status`
  - `tool_call`
  - `tool_result`
  - `answer_chunk`
  - `final_answer`
  - `error`
- 读取 `interactive_ready` 作为采访前置条件

### 主要输出

- Explorer Agent 后端能力
- SSE 流式接口
- 会话历史接口
- Session log 落盘能力

### 依赖

- Task 6
- Task 10
- Task 11

### 验收标准

- `POST /api/explorer/ask` 能返回 SSE 流
- SSE 至少包含：
  - `tool_call`
  - `tool_result`
  - `answer_chunk`
  - `final_answer`
- `POST /api/explorer/interview/{agent_id}` 在 `interactive_ready = true` 时可正常作答
- `interactive_ready = false` 时接口返回明确拒绝信息
- `GET /api/explorer/history/{simulation_id}` 可返回该用户的会话历史
- 每次 `ask` / `interview` 后，对应 `session_id` 的 `.jsonl` 日志文件有新增轮次记录
- `ExplorerSession.log_path` 已写入并可定位到对应 session 文件
- 回答内容可引用 Zep 图谱 facts，而不是仅生成泛化答案

---

## Task 14：Step 4 前端、端到端联调与权限收口

### 目标

把 Step 4 真正接到产品流里，并完成全链路联调、失败态和权限校验。

### 工作内容

- 实现 Explorer 对话页
- 接入 SSE 流式显示
- 增加 Agent 采访入口
- 增加历史会话展示
- 以前端结构对齐 MiroFish 后续交互页面为默认方案，统一沿用其整体品牌、布局语言、面板样式和交互节奏
- 对 Task 7 / Task 9 / Task 12 期间因功能接线产生的临时样式做统一收口，确保最终不是“局部像 MiroFish、局部像另一套系统”
- 做端到端联调：
  - 上传文档
  - 构图
  - prepare
  - start simulation
  - Explorer ask / interview
- 收口鉴权和归属校验

### 主要输出

- Step 4 前端页面
- 端到端可演示的完整链路
- 最终统一为 MiroFish 风格的整套前端

### 依赖

- Task 7
- Task 9
- Task 12
- Task 13

### 验收标准

- 登录用户可以从文档上传一路走到 Explorer 问答
- 前端可以显示流式回答和工具调用过程
- 不同用户之间无法访问彼此的项目、模拟和 Explorer 历史
- 任一阶段失败时，前后端都能看到明确错误信息
- 至少完成一条真实端到端演示链路
- Task 7 / Task 9 / Task 12 / Task 14 最终页面在整体视觉、布局和交互上应统一对齐 MiroFish，仅保留 FYP 必要的业务适配差异

---

## 四、推荐交付顺序

### 第一阶段：基础设施

- Task 1
- Task 2
- Task 3

### 第二阶段：Step 1 Graph Build

- Task 4
- Task 5
- Task 6
- Task 7

### 第三阶段：Step 2 Environment Setup

- Task 8
- Task 9

### 第四阶段：Step 3 Simulation

- Task 10
- Task 11
- Task 12

### 第五阶段：Step 4 Explorer Agent

- Task 13
- Task 14

---

## 五、关键依赖关系

1. Task 5 依赖 Task 3 的任务状态能力，但 `GET /api/graph/task/{task_id}` 由 Task 5 自己实现。
2. Task 8 依赖 Task 3 的任务状态能力，但 `GET /api/simulation/prepare/status/{task_id}` 由 Task 8 自己实现。
3. Task 10 负责 `POST /api/simulation/start/{simulation_id}`，Task 11 不负责 start。
4. Task 10 是 `interactive_ready` 的唯一写入方，Task 13 只读取。
5. Task 13 必须依赖 Task 6 的图谱 facts 和 Task 10 的模拟产物。

---

## 六、最终执行建议

- 不要把“迁移 service”理解为“复制原项目文件”，必须同步完成 FYP 的 repo、router、用户归属和状态落库适配。
- 任何后台长任务都必须能在 DB 中看到进度和错误信息，不能只写日志文件。
- 前端每个阶段都要以 `task_id` 或 `simulation_id` 作为恢复锚点，避免刷新后状态丢失。

---

## 七、一句话总结

> 本版任务清单的核心修正是：把通用状态能力、业务轮询接口、启动接口、工具迁移和 `interactive_ready` 写入责任全部明确到具体任务，确保每个阶段都能独立开发、独立验收、连续联调。
