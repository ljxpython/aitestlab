## 1. 生命周期与配置边界

- [x] 1.1 新增最小 `runtime_service.webapp:app`，通过 FastAPI/Starlette lifespan 在启动时初始化 Langfuse，在关闭时执行一次有界 flush，不添加业务路由。
- [x] 1.2 在 `langgraph.json` 和 `langgraph.demo.json` 注册同一个 `http.app`，验证配置 schema、Graph/Auth 导入和服务 `/info` introspection。
- [x] 1.3 增加禁用、显式缺失配置、单进程 client 复用、shutdown flush 成功/超时/异常的生命周期测试。

## 2. 可信 metadata 与 Service 接线

- [x] 2.1 修复 `observability/langfuse.py` 的 metadata/tag 合并：只保留 allowlist，trusted metadata 覆盖 caller 值，禁止未验证身份生成 `langfuse_user_id`。
- [x] 2.2 为 diagnostics 和 exporter 传递 `graph_id`、`run_id`、`thread_id`、`request_id`，保证未知标识使用稳定空值而不是从内容猜测。
- [x] 2.3 为 `reference_agent`、`deep_agent_demo`、`backend_demo`、`mcp_demo` 和 `workflow_demo` 统一传入已解析 Runtime 摘要；匿名/本地 workflow 只保留技术关联字段。
- [x] 2.4 增加 caller metadata 伪造 user/tenant/project、敏感字段、超长 Tool payload 和高基数 tag 的拒绝测试。

## 3. 诊断与 fail-soft

- [ ] 3.1 完善 Runtime diagnostics callback 的结构化日志字段和稳定 Counter，覆盖 Run 成功/失败/timeout/cancel、Tool error、token、duration、export error、event drop 和 flush 状态。
- [ ] 3.2 用可注入 callback/client/queue fake 覆盖 endpoint 不可达、callback 异常、队列满、flush 异常和 flush 超时，证明 exporter 故障不会阻塞 Agent。
- [x] 3.3 用真实 Graph 执行覆盖原始 Model、Tool、interrupt、cancel 和 timeout 异常，断言调用方收到原始异常而非观测异常。
- [x] 3.4 验证 diagnostics 快照和日志不包含 secret、authorization、完整 Prompt、模型响应、Tool 参数或结果；不新增第二套 Run 状态机或自定义 metrics 路由。

## 4. Graph 层级与并发证据

- [x] 4.1 用锁定版本的 `create_agent` 覆盖 Model 和 Tool observation，验证一 Graph invocation 对应一条 Trace、thread/session 映射和 metadata 隔离。
- [x] 4.2 用锁定版本的 `create_deep_agent` 或现有 Deep Agent demo 覆盖 Subagent 父子 observation、回调传播和子任务边界。
- [x] 4.3 增加并发不同 Run/Thread/Principal 的真实 Graph 测试，证明 callback、metadata、session 和 diagnostics 不串线。

## 5. 真实外部证据

- [x] 5.1 新增显式 `RUNTIME_R5=1` 的真实 Langfuse smoke 入口，从现有环境读取凭据，不打印或落盘 secret；缺配置或 endpoint 不可达时明确 skip/block。
- [x] 5.2 使用真实锁定模型和 `reference_agent`/`workflow_demo` 执行最小 Run，记录 Langfuse Trace ingestion、允许字段和 fail-soft 结果；不把 Langfuse 当作 Run 状态事实源。
- [ ] 5.3 在目标 Agent Server/容器启动路径验证 `http.app` lifespan startup、`SIGTERM` shutdown、bounded flush 和退出码；无法证明的边界保留为未完成。

## 6. 文档与验收

- [x] 6.1 更新 `16-runtime-observability-and-langfuse-design.md` 的 R5 Harness 对齐目录，逐项填写 `✅`/`❌`、实现位置、测试位置和证据命令。
- [x] 6.2 同步 `24-package-langgraph-startup-shutdown-design.md`、`28-runtime-refactor-development-plan.md`、`31-runtime-refactor-alignment-audit.md` 和 Runtime README，反映 `http.app` 生命周期及真实证据边界。
- [x] 6.3 维护本变更 `verification.md`：记录 pre-apply decision、命令输入、结果、未覆盖边界、残余风险和 docs/runbook 影响。
- [x] 6.4 执行 `uv run pytest tests/observability -q`、相关 Runtime 全量测试、R5 integration/e2e、`openspec validate "runtime-service-r5-observability-closure" --strict --no-interactive`、`git diff --check` 和 `rtk graphify update .`，将原始结果写入 verification。
