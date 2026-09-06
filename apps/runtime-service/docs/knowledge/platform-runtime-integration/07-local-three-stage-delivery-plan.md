# 本地三阶段实施与验收计划

## 1. 阶段

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| L1 | 配置模型管理合同、脱敏和拒绝语义 | 部分完成 |
| L2 | Platform API -> GraphHarbor -> Worker -> Runtime 的本机链路 | 已完成（本机） |
| L3 | 本机重启、SSE/HITL/cancel 和安全负面场景 | 部分完成 |

PostgreSQL、Redis 使用本机实例；不启动 Docker daemon。真实模型只使用
`apps/runtime-service/.env` 中已有、经 owner 授权的 local-compat 配置，不打印响应、URL、token 或 key。

## 2. L1 功能点

| 功能点 | 代码落点 | 验证 | 状态 |
| --- | --- | --- | --- |
| 七字段模型 DTO | `platform-api/runtime_catalog` | 合法/非法请求测试 | 已实现；定向回归通过 |
| API key write-only | model HTTP/repository | GET/list 无明文 | 已实现；定向回归通过 |
| 服务端加密 | `app/modules/runtime_catalog/application/credentials.py` | master key 缺失或解密失败 fail closed | 已实现；定向回归通过 |
| enabled 门禁 | model service + Run launch | disabled 在 Gateway 侧拒绝、不会调用 Provider | 本机真实链返回 403；模型状态已恢复 |
| GraphHarbor 边界 | gateway adapter | payload 不含 key | 本机 L2 真实链通过；不记录 credential 或响应内容 |

## 3. L2 最短真实链

启动五个应用进程：`runtime-api`、`runtime-worker`、`platform-api`、`platform-worker`、`platform-web`。
PostgreSQL 和 Redis 是外部本机基础设施，不计入五个应用进程。

```bash
rtk bash scripts/local-stack.sh start
rtk bash scripts/local-stack.sh status
uv run --project "apps/platform-api" --frozen python "scripts/local_stack_l2_runtime_smoke.py"
```

验证只记录 HTTP 状态、事件 cursor、终态和错误类别，不记录模型响应或敏感配置。L2 证明本机链路，不证明
生产 Secret Store、生产 proxy、revision 或 JWKS（旧方案均已 `Superseded/Rejected`）。

2026-09-04 本机证据：五个应用进程均健康；Protocol v2 的 Run、snapshot 和 event stream 返回 200，
event stream 有 cursor；标准 Runs stream 返回 200 且有 cursor；显式 cancel 返回 200，终态为
`interrupted`。固定非敏感 prompt 使用 owner 已授权的 local-compat `.env` 模型；未输出模型响应、URL、token
或 API key。

## 4. L3 本地安全和恢复

逐项验证 API/Worker 重启、SSE 重连、HITL respond、显式 cancel、同 Thread active Run 冲突、跨 project
拒绝、未知模型、禁用模型、错误 key、解密失败和日志脱敏。每项填写：功能点、代码落点、命令、结果、未
覆盖边界。没有证据就保持 `not-executed`。

已验证子项：同 key 不同 digest 为 409、同 Thread active Run 为 409、跨 project 读取为资源隐藏 404、
禁用模型在 Gateway 返回 403、SSE 订阅结束后 Run 仍可读取并由显式 cancel 终止；通过
`scripts/local-stack.sh restart-one` 分别重启 GraphHarbor API 和 Worker 后，同一 Thread/Run 可读取且恢复
stream 有 cursor；SSE 使用 `since` 重连后返回更高 cursor 且不重复最后游标。尚未验证：真实 HITL 图的
`input.respond` 和浏览器端完整 Chat E2E。

## 5. 完成条件

L1 只有模型管理和安全测试通过才完成；L2 只有五进程本机链路通过才完成；L3 还需重启、浏览器和 owner
UAT。任何未来生产级凭据托管或身份需求另立 change，不在本地阶段恢复已废弃的代理契约。
