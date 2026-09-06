# 本地三阶段交付计划

> 旧的 fake proxy、Secret emulator、execution reference 和测试 JWKS 阶段已废弃。L1/L2/L3 只验证本地
> 五进程链、七字段模型配置、凭据脱敏和 Run/SSE 恢复，不模拟已废弃的生产架构。

- 文档类型：Harness Supporting Project Record
- 状态：`L1 partial; L2 local-complete; L3 partial`
- 项目 owner：用户
- OpenSpec：[`redesign-platform-runtime-integration`](../../openspec/changes/redesign-platform-runtime-integration/)
- 详细实施文档：[`Runtime 侧三阶段计划`](../../apps/runtime-service/docs/knowledge/platform-runtime-integration/07-local-three-stage-delivery-plan.md)
- 更新时间：2026-09-04

## 1. 目标

在本机依次完成三个层级：

1. **L1 本地合同闭环**：验证 Agent/Thread/Run、Context/hash、幂等、HITL、SSE/cancel、权限和脱敏。
2. **L2 本地最短链**：启动本机 PostgreSQL、临时本地 Redis、GraphHarbor API/Worker、Runtime、Platform API/Web；owner 已授权使用 Git ignored `.env` 的真实模型跑通进程链，不启动 Docker daemon。
3. **L3 本地安全和恢复**：验证重启、SSE/HITL/cancel、并发冲突、禁用模型、错误 key、解密失败和日志脱敏。

这三个阶段完成后，结论是“本地闭环完成”，不是“生产已上线”。生产 Secret Store、身份治理和代理能力不属于本 change。

## 2. 阶段出口

| 阶段 | 出口证据 | 当前状态 |
| --- | --- | --- |
| L1 | Platform API/Runtime/Web 合同测试和拒绝分支证据；GATE-13 outbox/reconciliation | `partial` |
| L2 | `scripts/local-stack.sh` 管理的完整进程链、owner 授权 `.env` 模型 Run 与流式读取证据 | `local-complete` |
| L3 | 重启、SSE/HITL/cancel、并发和安全 negative 矩阵 | `partial` |

## 3. 每个功能点必须记录的四件事

| 记录项 | 写入位置 |
| --- | --- |
| 概念和用户可观察行为 | 本计划和 Runtime 侧详细计划 |
| 代码落点 | 功能点表中的具体文件/模块 |
| 验证命令和断言 | OpenSpec `verification.md` |
| 是否完成 | 本计划的阶段表 + OpenSpec `tasks.md` |

不能只勾任务，不写证据；不能把 fake 或 skip 写成真实链通过。

## 4. 当前已知基线

- Runtime profile validator 已实现并有定向测试；
- 当前不建设 `execution_model_id` resolver、统一模型代理或 Secret Store；
- Platform API durable run coordinator 已有同 key 幂等、active Run 冲突、HITL interrupt 和显式 cancel 语义单测；
- SSE join-stream 合同已固定为断开不取消：`cancel_on_disconnect=true` 在 Platform API upstream 前拒绝，默认显式传 `false`；
- Protocol v2 `run.start` 已在 Platform Gateway 内完成 server-side promotion：消费 `config.configurable.platform_runtime`，调用标准 Runs create 并将最终选项放入顶层 `context`；GraphHarbor Protocol v2 handler 未被扩展；对应 Platform API 合同测试已通过；
- 现有 Platform Worker 执行目录刷新、Assistant 同步、导出和知识扫描/清理；它尚未消费 `runtime.durable_run`，因此 GATE-13 的 Run outbox/reconciliation 仍未实施；

### GraphHarbor 修改边界复核（2026-09-04）

GraphHarbor 是通用 LangGraph-compatible Agent Server，只负责标准 Thread/Run/Checkpoint/Event、Worker
调度和 REST/SSE/Protocol 兼容性，不承载 Platform 的 Project、Agent、Policy、模型目录、Secret 或治理
记录。Platform 私有的 `run.start` 扩展字段必须由 Gateway 消费并转换为标准 Runs API 参数，不能直接塞进
GraphHarbor Protocol v2 handler。

本轮曾尝试透传 `durability`、`stream_resumable`、`on_disconnect`，复核后确认这扩大了通用协议而非修复
通用兼容性，已精确撤回；当前 GraphHarbor 仓库不因本 change 的业务需求修改。只有 Compatibility Profile
证明存在真正通用缺口时，才允许在 GraphHarbor 通用层提交最小 patch，并单独记录版本与契约测试。
- Platform Web LangGraph client、Stream actions 相关单测已通过；
- L2 已确认 Runtime 配置并完成 GraphHarbor forward-only migration；五个应用进程已启动，真实 local-compat 最短链已创建 Run、读取 Protocol v2/标准 Runs SSE cursor 并显式取消。
- L3 已完成幂等冲突、active Run 冲突、跨 project 资源隐藏、disabled 模型 Gateway 拒绝、SSE 断开后 Run 可读，以及 API/Worker 分别重启恢复和 `since` 游标重连检查；真实 HITL、完整浏览器 E2E 与 owner UAT 仍待完成。

## 5. 实施纪律

按 `L1 -> L2 -> L3` 顺序推进。每个阶段完成后先更新文档和 `verification.md`，再进入下一阶段。本次 L2 的真实 `.env` 模型调用是 owner 授权的 local-compat smoke；生产部署不属于当前 change。

暂不实施：Langfuse/OTLP、生产 canary、性能 SLO、自动回滚、Sandbox/远程 MCP、Run Explorer、生产 Secret Store/身份治理和无真实 fixture 的 legacy 清理。
