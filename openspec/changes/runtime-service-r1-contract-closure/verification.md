# Verification

- Status: `Chain verified on local Agent Server`
- Disposition: `Accepted with Platform/Durable boundary`
- Pre-apply review: `Approved`
- Owner review: 用户已明确同意按本 change 开始实现；本记录对应本轮实现授权。

## Scope

- Locus：`apps/runtime-service`
- Chain：Agent Server Auth -> `reference_agent` -> RuntimeContext -> Resolver -> Model/Tool boundary
- Band：B3 Governed
- Authority loaded：`AGENTS.md`、`docs/standards/01-ai-execution-system.md`、`apps/runtime-service/docs/knowledge/14-runtime-contracts-and-resolution-design.md`、现有 `openspec/specs/runtime-contracts/spec.md`、`openspec/specs/runtime-agent-service-integration/spec.md`。

## Pre-apply Review

- Proposal/specs/design/tasks：已审阅并按本 change 实现
- Approval or waiver：用户明确授权实现
- Apply decision：`Approved`

## Evidence Plan

### Local

- `uv run pytest tests/runtime -q`
- `uv run pytest tests/middlewares/test_runtime_middleware.py tests/services/reference_agent/test_agent.py tests/services/reference_agent/test_middleware_order.py -q`
- `uv run python -m compileall -q src tests scripts`
- `git diff --check`

输入：无外部服务的合同 fixture、恶意 claims、边界数值、Context hash 变体和权限/工具组合。

结果：R1 聚焦集合 `54 passed`；覆盖五类 frozen Runtime 类型、Context/hash/snapshot、JWT
scope/context_hash、Resolver 三方 Tool 权限交集、Middleware server user facts、reference
agent fail-closed 和配置 Auth path/OpenAPI Bearer 声明。

### Shortest chain

- 启动当前锁定版本支持的 Agent Server/Auth 配置。
- 使用专用 local Delegation JWT，通过 `Authorization` 调用 `reference_agent`。
- 验证 Auth 产出的 user facts、`runtime.server_info.user`、RuntimeContext、Resolver、模型/工具边界的一致性。

输入：专用 local secret、短 TTL token、合法/过期/篡改 token、合法/未知/身份型 Context。

结果：`uv run pytest tests/integration/test_agent_server_auth.py -q`：`1 passed`；在显式启用
真实模型后 `RUNTIME_E2E=1 uv run pytest tests/integration/test_agent_server_auth.py -q`：
`2 passed`。锁定的 `langgraph dev` 中匿名 `/threads` 为 `401`，无效 Bearer 为 `401`，合法
Delegation JWT 创建 Thread 为 `200`；第二条测试带 `context={"temperature": 0}` 真实调用
DeepSeek 并收到 `e2e-ok`，证明 Auth -> RuntimeContext -> Resolver -> Model 链路成立。

若 Agent Server entitlement、Auth 入口或依赖版本不支持该链路：记录具体命令、HTTP 状态或异常，状态为 `blocked`/`not-executed`，不能用 skip 作为通过证据。

### Formal / human

- Owner review：已确认本 change 的 claim 结构、Actor permission-to-tool 映射和 Auth user facts
  字段边界；Platform 签发链仍不在本 change。
- 真实 Agent Server/Docker 证据：不纳入本 change 的本地 pass；依赖外部 entitlement 时单独记录阻塞。

## Uncovered Boundaries

- Platform Gateway 尚未实现，本 change 使用 local signer fixture，不证明 Platform 签发链。
- R2 Workflow Interrupt/Resume、R3/R4/R5 和 R6 Durable 不在本 change 范围。
- `assistant_id`/`thread_id` scope 的最终来源需由 Agent Server execution info 和实际 Gateway payload 确认。
- Platform Gateway 的正式签发链、生产部署和 R6 Durable PostgreSQL/Redis/Worker 恢复仍未验证；
  本 change 的 shortest-chain 使用 local Agent Server 和 `.env` 中的受控 DeepSeek 配置。

## Docs / Runbook Impact

- 需要更新 `apps/runtime-service/docs/knowledge/14-runtime-contracts-and-resolution-design.md`、`28-runtime-refactor-development-plan.md`、`31-runtime-refactor-alignment-audit.md` 的证据矩阵。
- 若 `langgraph.json` Auth 注册改变启动/部署命令，需同步 runtime-service deploy README；否则记录无需额外 runbook 变更。
- 本轮 `langgraph.json`/`langgraph.demo.json` 仅增加 Auth OpenAPI Bearer 声明，不改变启动命令；
  部署 README 无额外命令变更。
