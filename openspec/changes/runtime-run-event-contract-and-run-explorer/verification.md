Status: Complete

Disposition: Deferred

Pre-apply review: Waived (not a current delivery gate)

Owner / approval: 2026-09-05；不 sync，按 GraphHarbor 事实源另立 change。

## Verification Plan

### Local / Minimal

- `uv run pytest apps/platform-api/tests -k "runtime_gateway or runtime_run"`
- SQLAlchemy 模型和事件仓储的幂等、并发 sequence、cursor 与敏感字段测试

### Shortest Chain

- Platform API Runtime Gateway HTTP 测试：Run 列表、详情、事件分页、权限拒绝和外部源部分失败
- `platform-web` 类型检查与构建，验证 Run Explorer 响应契约

### Formal / Human

- Owner review proposal、specs、design、tasks 后，在本文件记录 `Approved` 或明确 waiver
- 数据库迁移在临时数据库执行升级、回滚和重复执行检查
- 断线 SSE 重连、历史/实时去重和 break-glass Audit 需要人工验收

## Results

尚未实施，暂无结果。

## Uncovered Boundaries / Residual Risk

- Runtime 细节事件入口的最终传输方式尚未实现；首期可只实现 Platform API 生命周期事件
- Prometheus/Loki/OTel 生产部署、告警阈值和跨区域顺序不在本 change 范围
- Langfuse Trace 摘要字段和安全跳转方式需要锁定具体部署配置

## Docs / Runbook Impact

- 17 号架构文档已描述目标边界；实现后需要补充最终 API 字段和迁移运行手册
