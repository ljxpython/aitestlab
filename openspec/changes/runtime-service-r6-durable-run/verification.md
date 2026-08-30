# R6 Verification

## Pre-apply review

- Status: planning only; implementation has not started.
- Owner review: pending before `/opsx:apply`.
- Scope: `apps/runtime-service` Durable Run validation; Platform API is out of scope.

## Planned checks

- Fast: `uv run pytest tests -m "not integration and not durable and not e2e"`
- Durable: `uv run pytest tests/durable -m durable`
- Agent Server integration: `uv run pytest tests/integration -m integration`
- Smoke: isolated PostgreSQL/Redis/Worker with local Delegation Token and real Agent Server.

## Evidence to record during implementation

- Locked LangGraph CLI/SDK/image versions.
- Infrastructure startup command and configuration source.
- Thread/Run/checkpoint identifiers and event cursor assertions (redacted).
- Worker restart, SIGTERM, cancel, timeout, Tool failure and reconnect results.
- Uncovered boundaries and any version-specific behavior requiring follow-up.

## Docs and runbook impact

- Update `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` with confirmed R6 results.
- Update `23-graph-thread-backend-checkpoint-lifecycle-design.md`, `24-package-langgraph-startup-shutdown-design.md`
  or `25-runtime-testing-and-cross-service-contract-design.md` only when implementation evidence changes a decision.
