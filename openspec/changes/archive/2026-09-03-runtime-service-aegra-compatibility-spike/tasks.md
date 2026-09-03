## 1. Spike 隔离与依赖

- [x] 1.1 创建 `apps/runtime-service/spikes/aegra/` 目录和独立依赖/版本锁定文件
- [x] 1.2 创建仅用于 Spike 的 PostgreSQL、Redis Compose 依赖和本地 uv Aegra 启动/停止脚本
- [x] 1.3 增加 `.env` 前置检查，确认 DeepSeek、豆包多模态和 Langfuse 变量存在且不会输出密钥
- [x] 1.4 记录 Aegra 源码 commit、包版本、LangGraph/SDK 版本和启动命令

## 2. Agent 入口与基础协议

- [x] 2.1 将当前 reference Agent 的 `get_agent(config)` 注册到 Spike 配置
- [x] 2.2 验证 per-Run `RunnableConfig` 传递、模型解析和 `Pregel` 返回值
- [x] 2.3 使用真实 DeepSeek 中转模型完成最小文本 Run
- [x] 2.4 使用真实豆包多模态中转模型完成最小多模态 Run
- [x] 2.5 验证错误 graph export、错误签名和模型配置被 fail-closed 拒绝

## 3. Durable、事件与 HITL

- [x] 3.1 验证 Thread/Run/Checkpoint 持久化和同 Thread 连续对话
- [x] 3.2 注入 worker 终止，验证 lease recovery 从最新 checkpoint 恢复
- [x] 3.3 验证 graceful shutdown handoff 不丢 Run、不重复终态
- [x] 3.4 验证 SSE 断线后的 Last-Event-ID replay、顺序和去重
- [x] 3.5 验证 HITL interrupt/resume、cancel 和终态事件顺序
- [ ] 3.6 验证重复 completion/延迟 worker 不覆盖已提交终态

## 4. Workspace、Backend、Subagent 与权限

- [x] 4.1 准备至少两个 Thread 的 Workspace marker 场景并验证互不可见
- [x] 4.2 验证 Backend 在多 Worker、重启和恢复后的 Thread 作用域
- [ ] 4.3 验证 Bundled Skills 和 Subagent namespace 不跨 Thread 泄漏
- [ ] 4.4 验证 Subagent 只能使用父 Agent 明确委派的工具和路径
- [x] 4.5 验证未经授权的 tenant/project/thread/model/tool policy 请求被拒绝

## 5. RuntimeContext 与 Langfuse

- [x] 5.1 实现最小 Platform Context fixture、签名校验和 server-authoritative 字段覆盖测试
- [ ] 5.2 验证 RuntimeContext 在 Aegra worker 边界可恢复且不会落入不可信 client config
- [ ] 5.3 验证 Langfuse Trace 包含 Run/Thread/Agent/model 关联字段且不泄露凭证
- [ ] 5.4 注入 Langfuse exporter 故障，验证 Run finalize 和错误语义不受阻塞

## 6. 证据与决策

- [x] 6.1 为每项检查记录命令、输入前提、结果、日志摘要和未覆盖边界
- [x] 6.2 生成 Spike 结果报告：`pass`、`fail`、`blocked` 和推荐结论
- [x] 6.3 更新 `verification.md`，记录 owner review、验证结果和文档/运维影响
- [ ] 6.4 若全部通过，另行创建生产引入 Aegra 的 OpenSpec change；否则保留当前 R6 路径
