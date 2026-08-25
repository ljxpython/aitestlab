# 官方 LangGraph Runtime 升级与事件流迁移记录

## 1. 决策与范围

当前决定：不采用 Aegra 作为 runtime，保留现有 `platform-web -> platform-api -> runtime-service` 架构，升级官方 LangGraph Agent Server，并逐步引入统一流格式和事件协议。

本文件是迁移准备清单，不授权直接升级依赖、执行数据库迁移或发布生产环境。

目标分两层：

1. 升级到当时最新且已验证的官方 LangGraph Agent Server，消除当前 `langgraph-api==0.11.1` 的 EOL 风险。
2. 先稳定普通远程流，再演进到子图、工具生命周期和 HITL 的 Protocol v2 事件体验。

不做：为了迁移新增 Aegra 兼容层、直接替换平台网关、一次性重写前端聊天状态管理。

## 2. 官方范例应如何使用

官方范例质量足够好，但要按层借鉴，不能混用。

| 目标 | 官方范例 | 本项目应该借鉴什么 |
| --- | --- | --- |
| 普通远程 run 流 | [LangSmith Streaming API](https://docs.langchain.com/langsmith/streaming) | `client.runs.stream(...)`、`stream_mode`、thread/assistant 生命周期 |
| 本地统一流格式 | [LangGraph Streaming v2](https://docs.langchain.com/oss/python/langgraph/streaming#stream-output-format-v2) | `type/ns/data`，不再依赖 v1 嵌套元组 |
| 子图与 subagent | [Subgraph streaming](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#stream-subgraph-outputs) | v2 的 `ns`；需要高层投影时用 v3 `stream.subgraphs` |
| 本地 HITL | [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | 稳定 `thread_id`、持久化 checkpointer、`Command(resume=...)` |
| 远程事件协议 | [Protocol v2 Command](https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-command) 和 [Event Stream](https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-event-stream-sse) | 订阅 SSE 后以 `run.start` / `input.respond` 发送命令，使用 `since` 主动断线续传 |
| Vue 子 agent 界面 | [Deep Agents subagent streaming](https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming) | 主 agent 与子 agent 分开呈现，按 namespace/selector 延迟订阅 |

官方 Vue `useStream` 方案可以作为后续前端候选方案，但它不应成为 runtime 升级的前置条件。当前自有 gateway 和 Vue 状态层可以先保持不变。

## 3. 当前基线与已知事实

| 项目项 | 当前情况 | 风险或动作 |
| --- | --- | --- |
| Python graph | `langgraph==1.2.9` | 本地支持 `astream(version="v2")` 与 `astream_events(version="v3")` |
| Agent Server | `langgraph-api==0.11.1` | EOL，必须独立升级和验收 |
| 远程 SDK | `langgraph-sdk==0.4.2` | `client.runs.stream(...)` 支持 `version`，默认 v1 |
| 普通前端流 | `client.runs.stream(...)` | 当前 payload 已使用 `streamSubgraphs`，仍按现有 SSE 消费 |
| Protocol v2 网关 | `/threads/{thread_id}/commands`、`/threads/{thread_id}/stream/events` 已在 `platform-api` 暴露 | 尚未接入前端，且旧 Agent Server 未端到端验收 |
| 自定义 HTTP 路由 | `runtime_service/custom_routes/app.py:app` | 必须验证与新 runtime 的 route/lifespan 合并顺序 |
| 平台鉴权 | `runtime_service/auth/platform.py:platform_auth` | 必须验证 authenticate/on-access 回调签名和资源授权语义 |
| 持久化 | PostgreSQL + Redis | 升级前必须做真实数据备份与兼容性评估 |

现有文档中对 `langgraph-api` 版本存在历史残留表述；升级前不得相信文档中的版本号，应以锁文件、镜像 digest 和实际 `/info` 输出重新建立唯一基线。

## 4. 分阶段工作清单

### 阶段 0：冻结基线和确定升级目标

- [ ] 记录当前生产和本地的镜像 digest、`uv.lock`、`/info`、数据库版本、Redis 版本与环境变量清单（脱敏）。
- [ ] 选定目标 Agent Server 版本和官方基础镜像 digest；阅读该版本及跨越版本的 changelog、迁移说明和已知 breaking changes。
- [ ] 建立新 PostgreSQL 数据库和新 Redis namespace 作为升级验证环境，不复用现有生产数据。
- [ ] 明确回退策略：旧镜像、旧配置、旧数据库连接串均保持可恢复。

验收：可准确复现旧 runtime，且新验证环境没有写入生产数据。

### 阶段 1：仅升级官方 runtime

- [ ] 在独立分支升级 `langgraph-cli`、`langgraph-api`、`langgraph-sdk` 及其约束依赖，重新生成锁文件。
- [ ] 更新 Dockerfile 基础镜像和受约束安装方式，固定可追溯 digest，不使用漂移的 tag 作为生产唯一依据。
- [ ] 用新 runtime 启动 `langgraph.json`，逐一加载全部注册 graph。
- [ ] 验证 custom routes 的 `/info`、`/internal/capabilities/models`、`/internal/capabilities/tools`，并验证 FastAPI lifespan 只启动一次且顺序正确。
- [ ] 验证 `platform_auth` 的 Bearer delegation、管理 API key、线程/assistant/store 授权拒绝与允许路径。

验收：graph 注册、鉴权、custom routes、PostgreSQL checkpoint/store、Redis 依赖及健康检查全部通过；不引入前端行为变化。

### 阶段 2：锁定平台 HTTP 契约

- [ ] 将 `platform-api` gateway 的实际调用整理为 endpoint/payload/response/SSE event 的契约矩阵。
- [ ] 对普通接口至少覆盖 assistant、thread、run、history、state、cancel、batch、count、copy、cron 和 store 的现有使用面。
- [ ] 对流式接口验证 `runs.stream`、`join_stream`、断线、`stream_resumable`、`on_disconnect`、`stream_subgraphs`、HITL resume。
- [ ] 为新旧运行时运行同一组 gateway contract tests；差异必须被显式接受或修复，不能默默改前端适配。

验收：平台 API 与 Web 的既有关键路径在新 runtime 上行为一致，且所有协议差异有记录。

### 阶段 3：本地 Python 流从 v1 收敛到 v2

- [ ] 搜索所有 `graph.stream` / `graph.astream` 调用，逐个把消费者从元组解包改为 `part["type"]`、`part["ns"]`、`part["data"]`。
- [ ] 对包含 deep agent / subgraph 的 graph，测试根图、子图、token、tools、updates 和 tasks 的 `ns` 路径。
- [ ] 保持这些改动局限在本地 direct graph 调用和测试，不以此改变远程 HTTP 协议。

验收：所有本地流消费者不再依赖 v1 元组形状；每类流至少有一个断言返回 `StreamPart` 的测试。

### 阶段 4：远程普通流升级验证

- [ ] 在新 Agent Server 上验证 `client.runs.stream(..., version="v2")` 的真实 SSE 形状与 SDK 解码结果。
- [ ] 决定是否在现有 `platform-api` SDK adapter 透传 `version`；默认不改变，先通过 feature flag 或测试环境启用。
- [ ] 验证前端当前 `values`、`updates`、`tasks`、子图开关、中断与取消的渲染不回归。

验收：远程 v2 与当前前端消费兼容，或已完成最小 adapter 变更与回归测试。

### 阶段 5：Protocol v2 事件流 PoC

- [ ] 使用现有 gateway 的 `/threads/{thread_id}/commands` 与 `/threads/{thread_id}/stream/events` 建立最小端到端样例。
- [ ] 先订阅 `messages`、`updates`、`tools`、`lifecycle`、`input`、`tasks` 六类标准 channel；按 namespace 和 depth 验证子图筛选。
- [ ] 使用 `run.start` 发起 run，使用 `input.respond` 恢复 HITL；验证并行 interrupt 时按 ID 回应。
- [ ] 实现客户端主动重连：保存最后 `seq`，在请求 body 用 `since` 获取重放事件。该端点是 POST SSE，不能依赖浏览器 `EventSource` 的自动重连。
- [ ] 明确事件幂等、顺序、重复帧、取消、网络中断和授权失败的前端状态规则。

验收：一个真实 graph 能完成“发起 -> token/工具/子图事件 -> HITL 暂停 -> 恢复 -> 断线重连 -> 完成”的全链路测试。

### 阶段 6：前端产品化

- [ ] 保持现有聊天体验为默认路径，把 Protocol v2 放在独立开关或 debug/workflow 页面先落地。
- [ ] 先做 timeline/状态面板，再按需增加可折叠 subagent 卡片；不要把所有内部事件直接倾倒进聊天记录。
- [ ] 评估 `@langchain/vue` 的 `useStream`：只有确认它能适配平台认证、gateway URL、审计与现有状态模型时才引入。
- [ ] 完成可访问性、错误反馈、取消、重新连接和 HITL 审批 UI 验收。

验收：用户能理解当前运行阶段、看到可用的子图信息、完成审批和恢复，而不是只看到原始 JSON 事件。

### 阶段 7：发布与清理

- [ ] 预发布使用真实 PostgreSQL/Redis 和平台 delegation credential 进行回归。
- [ ] 定义灰度、指标、告警、日志关联字段、回退阈值与运行手册。
- [ ] 发布后确认 checkpoint、thread、run、store、事件序号和恢复行为正常。
- [ ] 仅在新路径稳定后删除旧 v1 本地消费者或临时 feature flag。

验收：有证据的生产验收、可执行回退和明确的旧路径退役记录。

## 5. 必须单独验证的高风险点

1. **认证回调**：`platform_auth.authenticate_runtime_delegation(authorization, headers)` 依赖当前注入签名。新 Agent Server 的 `Auth` 回调约定必须实际请求验证。
2. **custom routes / lifespan**：当前 HTTP app 不只是文档路由；它承载 capabilities。升级后必须检查路由保留、启动顺序和 store 可用性。
3. **持久化兼容性**：不要让新 runtime 首次启动直接连接并迁移生产 PostgreSQL。数据库 schema、checkpoint 序列化和 Redis key 语义都需要隔离测试。
4. **远程协议与本地 API 不是同一层**：本地 `astream_events(version="v3")` 的 Python 投影不会自动变成浏览器 API；远程事件应以 Protocol v2 契约实现。
5. **现有部署资产需要收敛**：Dockerfile、compose、README 和锁文件中有不同历史版本表述。升级时必须一次性让它们指向同一实际版本和运行模式。

## 6. 推荐开始点

先做阶段 0 和阶段 1 的隔离 PoC：不改前端，不启用 Protocol v2，不迁移生产数据，只回答一个问题：最新官方 Agent Server 是否能无回归地加载本项目全部 graph、平台鉴权和 custom routes。

该 PoC 通过后，普通远程流与 Protocol v2 事件流才值得继续投入。
