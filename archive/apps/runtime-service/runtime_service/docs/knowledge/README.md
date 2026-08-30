# runtime_service Knowledge

这里存放 `runtime_service` 相关的学习型资料，重点回答“官方推荐怎么用”和“本仓库应该怎么落地”。

推荐阅读顺序：

1. `01-langgraph-context-vs-config.md`
2. `02-create-agent-params.md`
3. `03-sdk-and-curl-passing-context-and-config.md`
4. `04-runtime-contract-v1.md`（历史方案；新契约以 14 号文档为准）
5. `05-runtime-contract-open-questions.md`
6. `06-runtime-blueprint-pseudocode.md`（历史伪代码；新实现以 14 号文档为准）
7. `07-langgraph-ecosystem-repository-research.md`
8. `09-langgraph-runtime-upgrade-and-event-migration.md`
9. `10-production-agent-platform-roadmap.md`
10. `11-agent-service-directory-architecture.md`（Draft：多 Agent 服务目录、部署入口与代码规范）
11. `12-runtime-context-and-local-debug-architecture.md`（Draft：身份、运行时配置决议与 Agent 独立调试）
12. `13-runtime-service-target-code-layout.md`（Draft：目标物理目录与 Legacy 处置）
13. `14-runtime-contracts-and-resolution-design.md`（Draft：Runtime Contracts、Policy snapshot 与纯函数决议）
14. `15-runtime-middleware-lifecycle-and-failure-semantics.md`（Draft：公共 Middleware 生命周期、顺序与失败语义）
15. `16-runtime-observability-and-langfuse-design.md`（Draft：公共可观测职责、Langfuse Trace 与数据安全）
16. `17-platform-observability-query-and-admin-console-design.md`（Draft：平台侧 Run 查询、事实源聚合与 Admin Console）
17. `18-open-swe-to-runtime-event-and-run-explorer-design.md`（Draft：Open SWE 借鉴边界、平台事件契约与 Run Explorer 适配）
18. `19-runtime-tool-capability-mcp-and-side-effect-design.md`（Draft：Tool 显式装配、Capability Policy、MCP 与副作用隔离）
19. `20-runtime-backend-workspace-skills-and-subagents-design.md`（Draft：Backend、Workspace、Skills 与 Subagents 接入）
20. `21-agent-release-versioning-rollout-rollback-and-run-binding-design.md`（延期 Draft：Agent、Graph、Prompt、Tool Policy 版本与发布治理）
21. `22-platform-runtime-contract-design.md`（Draft：Platform API / Runtime Service JSON、错误、事件、幂等和权限契约）
22. `23-graph-thread-backend-checkpoint-lifecycle-design.md`（Draft：Graph、Thread、Backend 与 Checkpoint 生命周期）
23. `24-package-langgraph-startup-shutdown-design.md`（Draft：Package、langgraph.json、启动与优雅退出）
24. `25-runtime-testing-and-cross-service-contract-design.md`（Draft：Runtime 测试目录、测试分层与跨服务契约测试）
25. `26-runtime-custom-routes-and-model-config-design.md`（Draft：Custom Route、模型配置归属与 Runtime 独立调试）
26. `27-platform-runtime-integration-phased-design.md`（Draft：Platform 持久化、配置快照与 Runtime 分阶段整合）
27. `08-streaming-protocols-and-future-events.md`（历史协议对照；与 09 冲突时以 09 为准）

阅读目标：

- 搞清楚 `RuntimeContext`、`config`、`configurable`、`env` 的职责边界
- 搞清楚 `create_agent(...)` 常见参数到底干什么
- 搞清楚通过 LangGraph SDK / HTTP API 怎么把 `context` 和 `config` 传进去
- 搞清楚后续重构要收敛到的正式运行时契约
- 搞清楚还有哪些未决问题不能直接拍脑袋改代码
- 了解早期标准重构蓝图及其被 14 号文档取代的原因
- 了解优秀 LangGraph 产品如何处理生产运行、显式工作流、动态工具和评测
- 搞清楚本地流格式、远程 SSE 协议，以及子图和 HITL 的演进路径
- 搞清楚官方 runtime 升级、普通流和 Protocol v2 事件流的分阶段迁移工作
- 搞清楚生产级 Agent 平台的架构结论、演进阶段和逐项讨论顺序
- 搞清楚多 Agent 平台的部署入口、服务组合根、Subagents、依赖方向和代码规范
- 搞清楚可信身份、Assistant/Run Context、配置决议、运行快照和本地调试的目标边界
- 搞清楚新 Runtime Service 的物理目录、代码归属、依赖方向和 Legacy 最终处置
- 搞清楚五类 Runtime 契约、Assistant/Run 合并、Policy snapshot、Tool 授权和配置 hash
- 搞清楚公共 Middleware 的生命周期、执行顺序、失败语义和 Open SWE 能力取舍
- 搞清楚 Langfuse、Durable Run、Protocol v2 SSE、Audit 和服务日志之间的职责边界
- 搞清楚平台侧如何聚合 Run、事件、Audit、Operation 与 Langfuse 摘要，以及 Workspace/Admin 的权限边界
- 搞清楚为什么 Runtime 不建设 Tool Registry，以及 Tool、MCP、Policy 和副作用如何在 Agent 组合根落地
- 搞清楚 Backend 分级、Thread Workspace、只读 Skills 和 Subagent 显式缩权如何在 Service 中接入
- 搞清楚 Agent Release、Graph/Prompt/Tool Policy 版本、灰度、回滚和进行中 Run Snapshot 如何绑定
- 搞清楚 Platform API 与 Runtime Service 的 JSON 命令、错误信封、事件顺序、幂等键和权限边界
- 搞清楚 Open SWE 的 Durable Run 默认值如何由 Platform Gateway 统一应用
- 搞清楚静态/动态 Graph、Thread Backend、Checkpoint、恢复和资源清理的生命周期边界
- 搞清楚 Package、langgraph.json、Agent Server 启动、容器部署和优雅退出的边界
- 搞清楚 Runtime 测试目录、Unit/Composition/Integration/Durable/E2E 分层和跨服务契约 fixtures
- 搞清楚为什么本次不建设 Custom Route，以及 Platform 模型配置如何透传给 Runtime 执行
- 搞清楚为什么先独立完成 Runtime，再由 Platform 补配置持久化、快照、Token 和 Gateway 整合

阅读完成后，再回头看这些活代码会更顺：

- `runtime_service/agents/assistant_agent/graph.py`
- `runtime_service/agents/research_agent/graph.py`
- `runtime_service/services/test_case_service/graph.py`

如果你要看“当前现行标准”，先回到：

- `docs/standards/01-harness-overview.md`
- `docs/standards/02-architecture.md`
- `docs/standards/03-agent-development-playbook.md`
- `docs/standards/08-middleware-development-playbook.md`
