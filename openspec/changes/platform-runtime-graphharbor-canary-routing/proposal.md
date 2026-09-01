## Why

当前 `platform-api` 的 `runtime_gateway` 只使用一个 `langgraph_upstream_url`，无法在旧
Agent Server 与 GraphHarbor 之间做可审计的灰度切换。直接改 URL 会让正在运行的 Run
丢失原执行面，也无法在故障时只停止新流量。GraphHarbor 要成为正式替代品，控制面必须
先拥有稳定的路由选择和 Run 路由归属。

本变更属于 `platform-api` 的 B3 Governed 跨边界变更，链路为
`platform-web -> platform-api runtime_gateway -> legacy/GraphHarbor upstream`；需要与
GraphHarbor 的 `graphharbor-runtime-service-cutover` change 对齐。

## What Changes

- 增加 legacy 与 GraphHarbor 两个 runtime upstream 配置，并保留当前 legacy 默认流量。
- 增加按 Agent、tenant、project 或稳定百分比选择新 Run 路由的受控策略。
- 在 `runtime_runs` durable record 中保存 `runtime_route`，后续查询、stream、command、
  join、cancel 和 delete 始终使用创建时的 upstream。
- 增加 `0% -> 1% -> 10% -> 50% -> 100%` 的配置校验、审计和回滚语义。
- 回滚只停止新 Run 分配到 GraphHarbor，不删除或重写已有 Run、Event、Checkpoint。
- 增加 platform-api 与 GraphHarbor delegation JWT audience/config 的启动检查。
- 增加 migration、路由幂等、回滚、故障和跨服务契约测试，并更新运行手册。

## Capabilities

### New Capabilities

- `runtime-route-cutover`：定义 legacy/GraphHarbor upstream 的灰度选择、Run 路由归属、
  回滚和审计契约。

### Modified Capabilities

- `chat-interaction-runtime`：正式聊天的 gateway 请求必须遵循 durable Run 的固定路由，
  不能因配置变化把已有运行切换到另一 upstream。

## Impact

- 代码：`apps/platform-api/app/core/config.py`、`app/modules/runtime_gateway/`、
  `app/modules/platform_config/` 和相关 adapter。
- 数据：platform-api `runtime_runs` 增加非空 `runtime_route`，旧记录使用 `legacy` 回填。
- API：平台配置 snapshot/feature flag 增加 runtime route 状态；现有 runtime gateway
  对外路径保持不变。
- 运维：需要一次前向兼容 migration、双 upstream 部署、路由指标和回滚 runbook。
- 不修改 GraphHarbor 核心执行逻辑，不改变默认生产流量，不删除 legacy runtime。
