## ADDED Requirements

### Requirement: Aegra 替换必须以可复现证据为门槛

评估 SHALL 在隔离环境使用固定版本的 Aegra、LangGraph、PostgreSQL、Redis、真实模型和
Langfuse，逐项记录命令、输入、结果和未覆盖边界。任何 `skip` 或 `blocked` 不得计为通过。

#### Scenario: 完整证据矩阵通过
- **WHEN** Durable、事件、权限、DeepAgent、RuntimeContext 和观测所有硬门槛均有可复现 `pass`
- **THEN** 评估状态可标记为 `ready_for_cutover`，并允许创建独立生产切换变更

#### Scenario: 任一硬门槛缺失
- **WHEN** 任一实验为 `fail`、`blocked` 或仅有本地近似证据
- **THEN** 评估状态保持 `not_ready`，不得修改正式 R6 部署

### Requirement: Durable、事件和终态语义必须通过真实服务验收

评估 SHALL 验证 Thread/Run/Checkpoint、Lease Recovery、graceful shutdown、HITL、cancel、
SSE 多帧 replay、事件顺序、去重和延迟 Worker 重复 completion。终态只能提交一次且不可被
迟到 Worker 覆盖。

#### Scenario: Worker 故障和优雅退出
- **WHEN** Worker 在 checkpoint 后崩溃或收到 SIGTERM
- **THEN** 新 Worker 从最新 checkpoint 接管，Run 只产生一个终态

#### Scenario: SSE 断线重连
- **WHEN** 客户端在事件序列 N 后断开并带 `since=N` 重连
- **THEN** 服务端只按递增顺序发送 N 之后的事件，不重复计数

### Requirement: DeepAgent 能力和 RuntimeContext 必须保持隔离

评估 SHALL 证明不同 Thread、Worker 和 Subagent 之间的 Workspace、Backend、Skills、工具、
路径和 namespace 不泄漏；Platform 签发的 RuntimeContext SHALL 在 Worker 边界可恢复，客户端
不得覆盖身份、租户、项目、Thread、模型或工具策略。

#### Scenario: 跨 Worker 恢复不泄漏状态
- **WHEN** 同一 Thread 在不同 Worker 上恢复 DeepAgent Run
- **THEN** 只能读取该 Thread 的 Workspace/Backend 状态，其他 Thread 的文件和 Subagent namespace 不可见

#### Scenario: 未授权 Context 请求
- **WHEN** 客户端提交未签名或越权的 protected 字段
- **THEN** 请求被拒绝并且不触发模型、工具或外部副作用

### Requirement: 观测故障不得影响 Runtime 终态

评估 SHALL 验证 Aegra OTEL/Langfuse Trace 能关联 Platform Run ID、Runtime Run ID、Thread、
Agent 和模型且不泄露凭证；Exporter 不可达、队列满或 flush 超时不得改变 Run 结果。

#### Scenario: Trace 可关联且脱敏
- **WHEN** 真实模型 Run 成功完成
- **THEN** Langfuse Trace 包含允许的关联字段，不包含 token、密钥或完整 Prompt/Response

#### Scenario: Exporter 故障
- **WHEN** Langfuse endpoint 返回错误或不可达
- **THEN** Run 仍按原语义 finalize，日志/指标记录观测故障

### Requirement: 生产切换必须具备回滚和边界清单

评估 SHALL 输出部署拓扑、依赖版本、数据库/Checkpoint 兼容性、健康检查、优雅退出、回滚
开关和未覆盖边界。生产切换不得与本评估 change 混在一起。

#### Scenario: 评估通过后创建切换变更
- **WHEN** readiness 状态为 `ready_for_cutover`
- **THEN** 新建独立 OpenSpec 变更，明确迁移、灰度、回滚和 Platform API 契约

#### Scenario: 评估未通过
- **WHEN** readiness 状态为 `not_ready`
- **THEN** 保留 R6 正式路径，只记录缺口和后续补验证任务
