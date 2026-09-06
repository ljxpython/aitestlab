## 0. 已废弃的模型代理 P0 外部生产门禁

以下任务随旧方案一起废弃，不再等待输入、不再实施，也不计入当前完成门禁。

本节只约束真实 staging/production 模型代理和 Provider smoke。它不阻塞本地三阶段轨道：
`L1 本地合同闭环 -> L2 本地最短链 -> L3 本地生产形状模拟`。本地轨道的功能点、代码落点、验证命令
和状态见 `apps/runtime-service/docs/knowledge/platform-runtime-integration/07-local-three-stage-delivery-plan.md`。

- [x] 0.1-0.7 旧模型代理门禁整体废弃；历史证据保留在 `verification.md` 仅供追溯

## 1. 冻结决策与现状基线

- [x] 1.1 由 owner 决定 Agent/Thread 绑定、Context transport、执行事实源、Gateway allowlist、模型配置交付、Auth profile、Run consistency、历史 Thread 和重叠 change 处置；已确认 Agent 命名/执行键、Tools 前端删除与 ChatDebugPage 删除，并记录到 `design.md` 与 `verification.md`
- [x] 1.2 锁定 Platform Web SDK、Protocol、Platform API、GraphHarbor 和 Runtime package 版本，形成 Compatibility Profile 清单；见 `09-compatibility-profile.md`
- [x] 1.3 为当前正式 Chat、Gateway endpoint caller 和仍需支持的历史 Thread 数据建立 characterization fixtures；见 `apps/platform-api/tests/fixtures/runtime_integration_characterization.json`
- [x] 1.4 根据已批准矩阵标记旧文档和 active OpenSpec 的 disposition，但在替代证据完成前不删除业务代码或数据
- [x] 1.5 按推荐基线逐项记录 owner 结论；`Proposed` 不得当作 apply contract，未冻结的 gate 不得进入 apply

## 2. 验证 GraphHarbor Compatibility Profile

- [x] 2.1 用真实 GraphHarbor API、Worker、PostgreSQL 和 Redis 验证 Thread create/search/get、State 与 History
- [x] 2.2 验证 Protocol v2 `run.start`、`input.respond`、`/commands`、`/stream/events`、SSE 重连和 cancel 契约
- [x] 2.3 验证标准 Runs API 将 `context`、durability、resumable、multitask 和 stream 选项完整传到 Worker 与 Runtime
- [ ] 2.4 验证缺失、无效及 scope/hash 不匹配的 delegation 在所属边界 fail closed：Platform-owned 请求在 upstream 前拒绝；GraphHarbor/Runtime 不调度到 Worker、Provider 或 Tool；标准 Runs 的 hash mismatch 是否已有 Run 记录如实记录，不伪装为 GraphHarbor 持久化前拒绝
- [x] 2.5 验证 GraphHarbor API 与 Worker 分别重启后，同一 Thread、Run、Checkpoint 和 Event 可恢复
- [x] 2.6 只在 GraphHarbor 通用协议层修复 Profile 发现的问题，并发布锁定版本供 Platform 使用

## 3. 收敛 Platform API 领域与数据

- [x] 3.1 将 Platform Assistant 历史模块迁移为 Agent 目录，使用 `(project_id, agent_key)` 和 `agent_key = graph_id`，停止 upstream Assistant mutation
- [x] 3.2 实现七字段模型元数据和启停管理；API key 只写不读，服务端加密，验证连接配置不进入浏览器、Run、GraphHarbor、日志或审计详情
- [x] 3.3 实现已接受的 Runtime Policy 与 Agent defaults、per-run model preferences 的 deny-first Context 决议；浏览器不得提交 Tools，Runtime 内部保留 `tools` 三态，未知字段和越权输入 fail closed
- [x] 3.4 为最小 Run governance ledger 增加 Agent key、Graph、Policy revision、Context snapshot/hash、幂等与审计关联的 forward-only migration
- [x] 3.5 在最终 Context 和目标确定后签发 operation-scoped delegation，分别限制 read 与 run-create scope
- [ ] 3.6 完成旧 Assistant 映射和 Run 数据审计、回填、重复执行及失败恢复测试；owner 已确认并完成旧 `graph_id=assistant` Agent/profile 删除，但旧列删除、完整迁移审计和失败恢复证据仍未完成
- [x] 3.7 实现 Project-first、首次 Run 绑定 `agent_key`、不可切换和并发冲突保护，覆盖 `AgentThreadMismatch`

## 4. 收敛 Platform Runtime Gateway

- [x] 4.1 建立唯一 `LaunchRuntimeRun` application use case，并让所有公开 Run create 入口经由该用例
- [x] 4.2 按 owner 批准结果实现 Protocol v2 Context transport；Gateway 只向 GraphHarbor 发送标准 Agent Server 字段
- [x] 4.3 将 Gateway 收缩为产品所需 endpoint allowlist；删除未治理的 Assistant mutation surface，Cron、Batch、Store 和 System surface 未另立 capability 前不得公开
- [x] 4.4 在 Thread、Run、State、History、SSE 和 cancel 边界执行可信 project ownership 与最小权限校验，不以 metadata 作为唯一依据
- [x] 4.5 统一成功 envelope、SSE、取消和 401/403/404/409/422/502 错误映射，并确保日志不包含 token、Context、message 或 provider secret
- [x] 4.6 为 allowlist、Context/hash、delegation、幂等、跨 project denial 和 upstream 无副作用补齐 Platform API 测试
- [x] 4.7 为 Run intent/outbox、Idempotency-Key、upstream timeout 和 reconciliation 补齐不重复创建及最终收敛测试

## 5. 重构 Platform Web Chat

- [x] 5.1 将正式 Chat 的 SDK client 固定到同源 `/api/langgraph`，统一 Platform auth 与 project scope，不识别 GraphHarbor
- [x] 5.2 只发送获准的模型和生成参数，删除 `system_prompt`、`enable_tools`、Tools 选择和非法身份/project 字段
- [x] 5.3 让官方 SDK controller 成为当前 Thread 的 messages、tools、interrupt、loading、error 和 lifecycle 唯一可写 owner
- [x] 5.4 将 Thread list/search/selection 与 active stream 分离，并验证快速切换、草稿恢复和历史 Thread 重开不串写
- [ ] 5.5 服务端已验证 submit、HITL respond、active 冲突和 cancel 合同；浏览器 submit/respond/retry/cancel、history/branch、响应式和基本可访问性仍未完整覆盖
- [ ] 5.6 删除 `ChatDebugPage`、Tools 管理入口以及在 characterization 和 SDK 替代测试成立后确认无用的 legacy payload、Run fallback 和重复 runtime 状态机
- [x] 5.7 将产品 UI/API 的 Assistant 命名迁移为 Agent，SDK `assistantId` 只接收 `agent_key`，不得保留第二个可选执行 ID

## 6. 实现 Platform 模型管理

- [x] 6.1 实现模型列表、录入、编辑、启停页面，复用现有控制面页面与 service 模式
- [x] 6.2 实现七字段校验、服务端加密和 API key write-only；GET/list 只返回 `credential_configured`
- [x] 6.3 验证未授权管理、无效配置、disabled 模型、解密失败和连接失败均 fail closed，且 API key 不出现在响应、Run、GraphHarbor 或日志

## 7. 完成真实链验收

- [x] 7.1 运行 Platform Web 与 Platform API 的 lint、typecheck、unit、component、HTTP、migration 和 security tests，并将结果写入 `verification.md`
- [x] 7.2 用 owner 明确授权、`RUNTIME_E2E=1` 的 Git ignored `.env` 真实模型验证 `platform-api -> GraphHarbor API -> Redis -> Worker -> runtime-service -> PostgreSQL` 最短真实链；只使用固定非敏感 prompt，不宣称生产模型代理、Secret Store 或 execution reference 已完成
- [x] 7.3 使用本机 `.env` 中已授权真实模型完成固定非敏感 prompt smoke；不宣称生产代理、Secret Store 或 execution reference 已完成
- [ ] 7.4 已完成 Playwright 登录、项目切换、Agent/Graphs/Chat 页面和 console 无错误验收；浏览器真实 send/stream/reopen/interrupt/respond/cancel/cross-project 全链仍未完成
- [x] 7.5 重启 GraphHarbor API 与 Worker，验证 durable resume、SSE 重连及事件不重复应用
- [ ] 7.6 由 owner 完成 Platform 页面 UAT，并在 `verification.md` 记录接受或拒绝结论

## 8. 清理与文档生命周期

- [x] 8.1 更新 Platform Web/API current standards、architecture、契约图、配置和必要 runbook，使其只描述新链
- [ ] 8.2 按批准矩阵一次性删除已被替代的代码，并归档已解除权威的旧知识文档和 delivery checklist
- [ ] 8.3 对重叠 active OpenSpec 分别记录 Accepted、Rejected 或 Abandoned，再按是否接受其 delta spec 决定 sync/archive
- [x] 8.4 维护 `verification.md` 的 pre-apply review、命令、输入、结果、未覆盖边界、deferred 项和 disposition
- [ ] 8.5 通过文档检查、OpenSpec strict validate 和静态 diff 检查；accepted delta specs 同步后再 archive 本 change

## 9. 模型目录与前端信息架构简化

- [x] 9.1 删除 `RUNTIME_MODEL_PROFILE` 的启动校验、local-compat 静态目录分支、`.env` 注释、测试和 runbook 引用；无 profile 时五个本地服务仍可启动（启动 validator 不再读取 profile；示例配置已移除）
- [x] 9.2 删除 `RUNTIME_E2E` 的测试门禁判断，按 integration/chain 与 provider 测试目录或 pytest marker 重分类；真实 Provider 缺凭据时不得降级 fake（README 与测试命令已改为 marker）
- [ ] 9.3 让 Platform 模型目录的 provider、base_url、protocol、model 和加密 API Key 真正进入 Runtime resolver；浏览器、Run、GraphHarbor、日志和审计不得泄漏 API Key（短期签名 opaque reference + Platform 内部解密端点已实现；定向测试通过，但本机真实“录入模型后 Run”尚未完成）
- [x] 9.4 将 Models 提升为独立产品入口；Agent 页面承担 Agent 绑定、启停和默认模型覆盖；Graph 保留内部 catalog，不作为普通用户主入口（一级 `/workspace/models`，旧 runtime 路由兼容保留）
- [x] 9.5 将 Runtime Policy 的模型启停和项目默认控制并入 Models，将 Agent 相关控制并入 Agent；保留后端 deny-first 校验，移除普通用户独立 Policy 页面（Models 现加载项目策略并提供默认模型操作；旧策略路由仅兼容保留）
- [x] 9.6 更新前端路由、导航、文案、兼容重定向和旧入口处置，补齐 typecheck、component、HTTP 和 Playwright 页面验证（typecheck 通过；完整浏览器交互仍见 5.5/7.4）
- [x] 9.7 更新专项 README、实施状态、服务 README、leaf 文档和 `verification.md`，记录删除项、模型执行链、证据和未覆盖边界
- [x] 9.8 将 `workflow_demo` 从确定性回显改为 Runtime 真实模型 `create_agent`，保留外层条件路由/HITL，并补齐多轮与本机 Provider 证据
