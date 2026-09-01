# R6 Verification

## Pre-apply review

- Status: implementation in progress; code and test harness are present.
- Owner review: completed before `/opsx:apply`.
- Scope: `apps/runtime-service` Durable Run validation; Platform API is out of scope.

## Planned checks

- Fast: `uv run pytest tests -m "not integration and not durable and not e2e"`
- Durable: `uv run pytest tests/durable -m durable`
- Agent Server integration: `uv run pytest tests/integration -m integration`
- Smoke: isolated PostgreSQL/Redis/Worker with local Delegation Token and real Agent Server.

## Evidence to record during implementation

- Locked local versions: `langgraph==1.2.11`, `langgraph-cli[inmem]==0.4.31`,
  `langgraph-sdk==0.4.3`; Docker base image is pinned to
  `langchain/langgraph-api:3.13@sha256:61ad2a5beb30020eecf05a5a8108bcaba7ed44cbebb570e565611e760f1e4a40`
  and reports `langgraph-api==0.13.2`.
- Infrastructure startup command and configuration source.
- Thread/Run/checkpoint identifiers and event cursor assertions (redacted).
- Worker restart, SIGTERM, cancel, timeout, Tool failure and reconnect results.
- Uncovered boundaries and any version-specific behavior requiring follow-up.

## Current execution results

- `uv run pytest tests -m "not integration and not durable and not e2e" -q`: **51 passed**.
- `uv run pytest tests/durable -m durable -q`: **9 skipped** because no
  `RUNTIME_DURABLE_URL` was configured.
- The skipped tests are not R6 acceptance evidence. They only confirm that the
  durable test gate is explicit when the required Agent Server is unavailable.
- `uv run python -m compileall -q src tests scripts`: **passed**.
- `uv lock --check`: **passed**.
- `docker compose config`: **passed**; PostgreSQL and Redis became healthy.
- Protocol smoke against local `langgraph dev` (`langgraph-api==0.13.0`): sync Thread/Run/Stream
  and checkpoint test **passed** after adapting to the locked SDK contract (`thread_id` must be a UUID,
  `if_exists="raise"`, and selected stream modes close without an explicit `end` event).
- Real Agent Server startup with the pinned Docker image: **blocked by account entitlement**.
  `LANGSMITH_API_KEY` was supplied to the container, but
  `https://api.smith.langchain.com/auth?langgraph-api=true` returned `403`; the container then
  exited with the official message requiring a LangGraph Cloud-accessible API key for local
  testing or `LANGGRAPH_CLOUD_LICENSE_KEY` for production. The ordinary LangSmith API endpoint
  returned `200`, so this is not a missing-variable failure. No Docker Durable Run result is
  claimed from this attempt.
- Local `langgraph dev` (`api_variant=local_dev`) started without a License Key and
  `GET /info` returned `200`. This confirms the OSS/in-memory development path does not require
  a LangGraph License, but it does not provide the PostgreSQL/Redis Durable Run evidence required
  by R6.

## Docs and runbook impact

- Update `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` with confirmed R6 results.
- Update `23-graph-thread-backend-checkpoint-lifecycle-design.md`, `24-package-langgraph-startup-shutdown-design.md`
  or `25-runtime-testing-and-cross-service-contract-design.md` only when implementation evidence changes a decision.
