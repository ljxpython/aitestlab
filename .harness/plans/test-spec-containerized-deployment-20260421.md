# Test Spec — Containerized Deployment for AITestLab

> Status: Archived. This is historical planning evidence, not a current test entry.

- Date: 2026-04-21
- Related PRD: `.harness/plans/prd-containerized-deployment-20260421.md`
- Source context: `.harness/context/containerized-deployment-20260421T131133Z.md`

## 1. Planning assertions
- The work remains B3 until PRD/Test Spec and real-input gates are satisfied.
- The plan covers exactly three deployment surfaces:
  - `runtime-service` single-app
  - full stack without Nginx
  - full stack with Nginx
- The plan does not silently change canonical local deployment policy.

## 2. Runtime-service lane assertions
- The implementation must explicitly label the runtime lane as one of:
  - validated demo-style primary lane
  - fallback lane
- The primary lane does not require `LANGSMITH_API_KEY` or `LANGGRAPH_CLOUD_LICENSE_KEY`.
- Redis is required.
- Postgres is required.
- Runtime deployment docs must clearly state which config file is used:
  - `runtime_service/langgraph.json`
  - or `runtime_service/langgraph_auth.json`
- Runtime deployment docs must clearly state that v1 follows the current deployed graph registration set unless later narrowed deliberately.
- Runtime private knowledge MCP defaults must be readable from env-backed deployment config, not only ad hoc runnable configurable injection.
- Runtime private knowledge MCP env names are fixed as:
  - `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
  - `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
  - `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
  - `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`
- Runtime image build must be driven by a repo-managed Dockerfile, not by requiring end users to install LangGraph CLI locally.

## 3. Full-stack no-Nginx assertions
- Compose topology contains:
  - `runtime-service`
  - runtime Redis
  - runtime Postgres
  - `interaction-data-service`
  - `platform-api-v2`
  - `platform-api-v2-worker`
  - `platform-web-vue`
- Host ports match the canonical local service story unless intentionally documented otherwise.
- `platform-api-v2` talks to `runtime-service` over internal network DNS, not host loopback URLs.
- `platform-api-v2-worker` is included and uses the same queue/storage contract as the API service.
- `interaction-data-service` runs with DB enabled in the v1 stack.
- The v1 stack uses one shared Postgres instance across `runtime-service`, `platform-api-v2`, and `interaction-data-service`.
- Default per-service database names on the shared Postgres instance are:
  - `runtime_service`
  - `platform_api_v2`
  - `interaction_data_service`
- Optional external RAG HTTP URL is supported without being required for baseline startup.
- Optional external runtime knowledge MCP SSE URL is supported without being required for baseline startup.

## 4. Full-stack Nginx assertions
- Nginx is the only default public entrypoint.
- Route contract is explicit and documented.
- Default route surface does not expose raw `runtime-service` externally unless explicitly chosen.
- `platform-web-vue` remains served as the user-facing platform host.

## 5. Real-input assertions
- Required user-owned inputs are listed in repo shape, not only as loose variable names.
- Missing required inputs fail fast with a clear message that identifies:
  - missing file location
  - missing field names
  - blocked service
- Real secrets are never hardcoded into docs or committed defaults.
- Optional external dependency inputs are documented separately from hard blockers.

## 6. Expected future automated verification

### Compose validation
- `docker build -f apps/runtime-service/deploy/Dockerfile apps/runtime-service`
- `docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml config`
- `docker compose -f deploy/docker-compose.stack.yml config`
- `docker compose -f deploy/docker-compose.stack.nginx.yml config`

### Runtime-service smoke
- `docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml up -d`
- wait for dependency health checks
- hit the documented runtime health endpoint
- confirm graph registry is reachable by the documented runtime API surface
- if runtime knowledge MCP env defaults are configured:
  - confirm `TEST_CASE_V2_*` values resolve from env into service-private runtime config defaults

### Full-stack no-Nginx smoke
- `docker compose -f deploy/docker-compose.stack.yml up -d`
- verify:
  - `runtime-service` health endpoint
  - `interaction-data-service` `/_service/health`
  - `platform-api-v2` `/_system/probes/ready`
  - `platform-web-vue` root page
  - `interaction-data-service` DB-backed endpoints are not returning `503 database_not_enabled`
- if bootstrap admin is enabled:
  - verify login flow succeeds with the documented account
- if RAG HTTP URL is configured:
  - verify platform knowledge path can reach upstream dependency

### Full-stack Nginx smoke
- `docker compose -f deploy/docker-compose.stack.nginx.yml up -d`
- verify:
  - ingress root serves the platform UI
  - proxied platform API routes succeed through Nginx
  - health endpoints are reachable as documented through ingress or internal checks

## 7. Expected future manual verification
- Open the platform UI.
- Log in with bootstrap or configured account.
- Confirm platform API can read runtime-dependent pages without direct browser calls to internal-only services.
- Confirm worker-dependent control-plane readiness is green.
- If runtime direct exposure is intentionally enabled, confirm it is only at the documented path.

## 8. Regression / contract assertions
- Containerization must not create a new direct `platform-web-vue -> interaction-data-service` path.
- Containerization must not merge control-plane and runtime-plane responsibilities.
- Containerization docs must preserve the distinction between:
  - current local default bring-up
  - new containerized deployment surfaces

## 9. Completion evidence required before implementation can be declared done
- Compose files exist and render with `docker compose config`.
- Runtime-service Dockerfile exists in the repo and builds locally.
- Required env templates exist.
- Runtime-service lane is runnable with real user inputs.
- Full-stack no-Nginx lane is runnable.
- Full-stack Nginx lane is runnable.
- Rebuild / recreate / rollback runbook exists.
- Documentation explains:
  - which lane is for what
  - what real inputs are required
  - which external dependencies are optional
  - what is still local-only or demo-only
  - which finalized `TEST_CASE_V2_*` env names own runtime private knowledge MCP defaults
