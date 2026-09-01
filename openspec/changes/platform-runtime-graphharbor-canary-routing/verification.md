# Verification

## Pre-apply review

- Status: `Pending`
- Disposition: `Pending acceptance`
- Pre-apply review: `Pending`
- Owner approval: 未提供；在 owner 审阅 proposal、specs、design、tasks 前不得应用代码或 migration。

## Scope

- Locus：`apps/platform-api`
- Chain：`platform-api runtime_gateway -> legacy/GraphHarbor upstream`
- Band：B3 Governed
- Related change：GraphHarbor `graphharbor-runtime-service-cutover`
- Authority loaded：`AGENTS.md`、`docs/standards/01-ai-execution-system.md`、
  `docs/standards/permission-standard.md`、`docs/standards/audit-standard.md`、
  `docs/standards/runtime-gateway-interface-standard.md`

## Evidence plan

### Local

- `uv run pytest apps/platform-api/tests/test_runtime_delegation.py -q`
- route-policy、repository、migration 和 idempotency unit tests
- `uv run ruff check apps/platform-api/app apps/platform-api/tests`
- `git diff --check`

### Shortest chain

- platform-api 在 `0%` 下调用当前 legacy upstream，验证现有 gateway 行为不变。
- 使用受控 GraphHarbor endpoint，在 `1%` 或 allowlist project 下创建 Run，验证 delegation
  JWT、route record 和所有后续操作使用同一 upstream。
- 关闭 GraphHarbor route 后创建新 Run，确认回到 legacy，已有 GraphHarbor Run 不变。

### Formal / human

- 双 upstream、独立 PostgreSQL migration、备份恢复、性能和回滚演练。
- owner 审阅 route ownership、数据迁移、权限、审计和生产维护窗口。

## Current local results

- `uv run python -m unittest discover -s tests -p "test_runtime_delegation.py" -v`：`9 tests` passed。
- `uv run python -m unittest discover -s tests -p "test_runtime_gateway*.py" -v`：`19 tests` passed。
- `uv run python -m compileall -q app tests`：passed。
- `openspec validate platform-runtime-graphharbor-canary-routing --type change --strict`：passed。
- 当前结果只证明现有 delegation/gateway contract 未被破坏；因为 route policy、`runtime_route`
  和 migration 尚未实现，不能作为本变更的 shortest-chain 或 formal acceptance。

## Uncovered boundaries

- 当前尚未实现 `runtime_route` 字段、百分比选择或跨 upstream client 解析。
- GraphHarbor 的 RuntimePolicy、DeepAgent、MCP、跨网络 SSE 和外部 provider 门槛由关联 change 验收。
- 未获得生产数据库、真实 JWT secret、模型/MCP 凭据或正式网络环境授权。

## Docs / runbook impact

- 更新 platform-api runtime gateway interface、配置、migration 和 rollback runbook。
- 与 GraphHarbor `docs/production-runbook.md` 对齐 delegation audience；内部 RuntimeContext
  audience 不得复用为 platform delegation audience。
