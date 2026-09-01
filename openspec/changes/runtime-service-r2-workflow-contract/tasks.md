## 1. Contract And Auth Boundary

- [x] 1.1 owner 审核并批准 Workflow 纳入 R2，以及 `get_agent({})` 缺少 Auth 时 fail-closed 的合同
- [x] 1.2 在实现前确认 local test adapter 的显式输入和生产配置隔离，不从空 `RunnableConfig` 补身份
- [x] 1.3 修正 R2 对齐矩阵和 README，使其不再把归档的空配置默认成功写成当前要求

## 2. Workflow Implementation

- [x] 2.1 在 `workflow_demo` Service 内扩展 Typed StateGraph，增加两条可判定、可观察的条件路径
- [x] 2.2 增加服务端声明的 Interrupt 和同一 Thread 的 Resume 路径，保持 `graphs/` 只做稳定导出
- [x] 2.3 为 R2 本地测试接入最小 in-memory checkpointer，不引入公共 Workflow Builder 或生产 Durable 声明
- [x] 2.4 确认静态 Graph 重复加载的 nodes、edges、state schema 一致，入口加载无外部 I/O

## 3. Tests And Evidence

- [x] 3.1 新增 `tests/services/workflow_demo/test_agent.py`，覆盖两条条件分支、Interrupt、Resume 和非法 Resume
- [x] 3.2 用节点计数或等价事件断言 Resume 不重复执行已完成节点
- [x] 3.3 修正 `reference_agent` 生命周期测试，删除对不存在 `_STATIC_AGENT` 的无效控制，覆盖空配置拒绝和显式 local adapter
- [x] 3.4 增加 `langgraph.demo.json` 下 `workflow_demo` 的 Agent Server introspection/执行链测试

## 4. Documentation And Verification

- [x] 4.1 补齐 `workflow_demo/README.md` 的状态、分支、恢复、生命周期和验证命令
- [x] 4.2 运行定向单测、完整本地非 Durable 测试和 Agent Server demo chain，并记录真实输入与结果
- [x] 4.3 更新 `verification.md`，记录 pre-apply review、命令、证据、未覆盖的 R6 Durable 边界和最终 disposition
- [x] 4.4 owner 接受后将 delta spec sync 到 `openspec/specs/runtime-agent-service-integration/spec.md`
