# Runtime Service 开发文档

这里是新 Runtime Service 的项目级文档入口。新代码位于
`apps/runtime-service/src/runtime_service/`，本目录只保留绿色重构真正需要的设计和实施资料。

R0-R5 已有局部实现和归档验证记录，但尚未全部满足生产链路设计；R6 Durable Run 的
GraphHarbor Durable Core 已在隔离 PostgreSQL/Redis 环境取得部分真实证据，但生产切换仍未就绪。
逐文档对齐结果见
`knowledge/31-runtime-refactor-alignment-audit.md`。实现代码和测试以应用根 README、
`tests/runtime/` 和 `tests/services/` 为准；R0-R6 不修改 Platform API。

## 阅读顺序

1. `knowledge/10-production-agent-platform-roadmap.md`：总路线图和阶段依赖
2. `knowledge/28-runtime-refactor-development-plan.md`：R0～R6、P1 开发计划和验收门槛
3. `knowledge/13-runtime-service-target-code-layout.md`：目标物理目录和依赖方向
4. `knowledge/14-runtime-contracts-and-resolution-design.md`：Contracts、Resolver、Modeling
5. `knowledge/11-agent-service-directory-architecture.md`：Agent Service 组合根和代码规范
6. `knowledge/15-runtime-middleware-lifecycle-and-failure-semantics.md`：Middleware 生命周期和失败语义
7. `knowledge/23-graph-thread-backend-checkpoint-lifecycle-design.md`：Graph、Thread、Backend、Checkpoint
8. `knowledge/24-package-langgraph-startup-shutdown-design.md`：Package、langgraph.json、启动和退出
9. `knowledge/25-runtime-testing-and-cross-service-contract-design.md`：测试分层和跨服务契约测试
10. `knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md`：Tool、MCP 和副作用隔离
11. `knowledge/20-runtime-backend-workspace-skills-and-subagents-design.md`：Backend、Workspace、Skills、Subagents
12. `knowledge/16-runtime-observability-and-langfuse-design.md`：Trace、日志、指标和脱敏
13. `knowledge/18-open-swe-to-runtime-event-and-run-explorer-design.md`：Open SWE 借鉴和事件投影
14. `knowledge/26-runtime-custom-routes-and-model-config-design.md`：不建设 Custom Route 的模型配置边界
15. `knowledge/22-platform-runtime-contract-design.md`：Platform 整合阶段的 JSON、Token、事件和幂等契约
16. `knowledge/27-platform-runtime-integration-phased-design.md`：Runtime 与 Platform 分阶段整合
17. `knowledge/31-runtime-refactor-alignment-audit.md`：设计、源码、测试和真实证据对齐审计

R4 Demo 快速入口：`src/runtime_service/services/demo/deep_agent_services/demo/README.md`、
`src/runtime_service/services/demo/mcp_services/demo/README.md`、
`src/runtime_service/services/demo/backend_services/demo/README.md`。

## 文档边界

- `knowledge/` 下的文档服务于新 Runtime 绿色重构，不是旧代码迁移指南。
- 旧 `runtime_service/docs/` 只作为历史参考，不从新代码导入或复制。
- 旧契约、旧数据、旧 Graph、旧 HTTP 路由不进入新实现；不做双读、双写或兼容 Adapter。
- 21 号版本治理文档暂不复制，它是延期的未来议题；17 号 Admin Console 文档属于后续平台建设。
