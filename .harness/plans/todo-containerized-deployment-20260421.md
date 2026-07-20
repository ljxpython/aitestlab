# TODO — Containerized Deployment Delivery Checklist

> Status: Archived. Delivery is implemented; use `deploy/README.md` and the current
> runbook for operation and verification.

- Date: 2026-04-21
- Related PRD: `.harness/plans/prd-containerized-deployment-20260421.md`
- Related Test Spec: `.harness/plans/test-spec-containerized-deployment-20260421.md`
- Status: delivery-ready with optional-knowledge caveats

## 1. Scope Lock
- [x] Confirm this work is B3.
- [x] Confirm outputs for this phase are research / clarification / PRD / Test Spec only.
- [x] Confirm `runtime-service` does not require `LANGGRAPH_CLOUD_LICENSE_KEY`.
- [x] Confirm Supabase OAuth is out of scope for v1.
- [x] Confirm `interaction-data-service` v1 is DB-backed in compose.
- [x] Confirm LightRAG / RAG is an external dependency in v1.
- [x] Confirm runtime private knowledge MCP should read defaults from env.

## 2. Real Inputs
- [x] Collect repo-shaped runtime model config for:
  - `apps/runtime-service/runtime_service/.env`
  - `apps/runtime-service/runtime_service/conf/settings.local.yaml`
- [x] Keep current local/demo `PLATFORM_API_V2_JWT_ACCESS_SECRET`.
- [x] Keep current local/demo `PLATFORM_API_V2_JWT_REFRESH_SECRET`.
- [x] Keep current bootstrap admin `admin / admin123456`.
- [x] Collect optional platform-facing RAG HTTP URL.
- [x] Collect optional runtime-facing knowledge MCP SSE URL.
- [ ] Collect optional public ingress port/domain if not default.

## 3. Runtime-Service Single-App Delivery
- [x] Decide final runtime image build path.
- [x] Decide whether to check in a generated Dockerfile or only compose build instructions.
- [x] Use a repo-managed Dockerfile under `apps/runtime-service/deploy/`.
- [x] Do not require end users to install LangGraph CLI as a deployment prerequisite.
- [x] Define runtime deploy env template.
- [x] Map runtime service-private knowledge MCP env defaults into deploy config.
- [x] Freeze runtime private knowledge MCP env names:
  - `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
  - `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
  - `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
  - `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`
- [x] Define runtime Redis and Postgres service names and ports.
- [x] Define runtime health checks.
- [x] Define rebuild/update procedure for runtime-only deployment.
- [x] Verify single-app `runtime-service` on latest official image with the updated usable `LANGSMITH_API_KEY`.

## 4. Full-Stack Compose Without Nginx
- [x] Define root compose file location.
- [x] Define `runtime-service` service.
- [x] Define runtime Redis service.
- [x] Define runtime Postgres service.
- [x] Define `interaction-data-service` service with DB enabled.
- [x] Define interaction DB service or shared Postgres strategy.
- [x] Use one shared Postgres instance across `runtime-service`, `platform-api-v2`, and `interaction-data-service`.
- [x] Define `platform-api-v2` service.
- [x] Define `platform-api-v2-worker` service.
- [x] Define `platform-web-vue` service.
- [x] Define optional external RAG HTTP env wiring.
- [x] Define optional runtime knowledge MCP SSE env wiring.
- [x] Use the finalized `TEST_CASE_V2_*` env names for runtime private knowledge MCP wiring.
- [x] Define canonical host ports.
- [x] Verify full-stack no-nginx stack reaches healthy `interaction-data-service`, `platform-api-v2`, `platform-api-v2-worker`, and `platform-web-vue`.

## 5. Full-Stack Compose With Nginx
- [x] Define Nginx service.
- [x] Define Nginx config file location.
- [x] Define `/` routing to `platform-web-vue`.
- [x] Define `/api/` routing to `platform-api-v2`.
- [x] Define `/_system/` routing to `platform-api-v2`.
- [x] Confirm `runtime-service` is internal-only by default.
- [x] Define ingress-specific health checks.
- [x] Verify full-stack nginx stack serves `/`, `/_system/probes/ready`, and routes `/api/*` to `platform-api-v2`.

## 6. Data and Dependency Decisions
- [x] Decide whether `interaction-data-service` gets dedicated Postgres or shared stack Postgres.
- [x] Decide whether `platform-api-v2` and `interaction-data-service` may share one Postgres instance with different databases/schemas, or must be split.
- [x] Freeze exact per-service DSN/database naming on the shared Postgres instance.
- [x] Shared Postgres default database names:
  - `runtime_service`
  - `platform_api_v2`
  - `interaction_data_service`
- [x] Decide runtime Redis usage details for the demo-style runtime lane.
- [x] Decide artifact/storage volume mounts for:
  - `interaction-data-service` document assets
  - shared Postgres data

## 7. Update and Rollout Runbook
- [x] Document rebuild flow when Dockerfile/app code changes.
- [x] Document recreate flow when only env/config changes.
- [x] Document API + worker coordinated restart flow.
- [x] Document DB-related update flow.
- [x] Document Nginx-only reload/recreate flow.
- [ ] Document rollback flow.

## 8. Docs Delivery
- [x] Add root container deployment guide.
- [x] Add runtime-service single-app deployment guide.
- [x] Update `docs/env-matrix.md`.
- [x] Update `docs/deployment-guide.md`.
- [x] Add container update/rebuild runbook.
- [x] Update app READMEs only after implementation is verified.
- [x] Document finalized `TEST_CASE_V2_*` env ownership in deployment docs.

## 9. Verification Readiness
- [x] Define `docker compose config` commands for all deployment surfaces.
- [x] Define runtime-only smoke commands.
- [x] Define full-stack no-nginx smoke commands.
- [x] Define full-stack nginx smoke commands.
- [x] Define optional RAG HTTP verification path.
- [x] Define optional runtime knowledge MCP verification path.
- [x] Verify current reference `LANGSMITH_API_KEY` against `/auth?langgraph-api=true`.
- [x] Confirm the reference key currently returns `403 Forbidden` on the official LangGraph auth check.
- [x] Verify `TEST_CASE_V2_*` env fallback is active in `test_case_service_v2`.
- [x] Verify current optional RAG HTTP URL is not container-reachable as configured (`127.0.0.1`).
- [x] Verify current optional MCP URL is not container-reachable as configured (`0.0.0.0`).
- [x] Verify `host.docker.internal:9621` is container-reachable from `platform-api-v2`.
- [x] Verify `host.docker.internal:8621/sse` is container-reachable from `runtime-service`.

## 10. Entry Criteria
- [ ] Required runtime model config is available.
- [x] Optional RAG endpoints are either provided or explicitly deferred.
- [x] Deployment file locations are frozen.
- [x] Env ownership by app is frozen.
- [x] Runbook coverage is defined.

## 11. Delivery Notes
- [x] Baseline container delivery is functional without optional knowledge dependencies.
- [x] Optional knowledge dependencies require container-reachable addresses.
- [x] Replace `127.0.0.1:9621` with a container-reachable RAG HTTP address.
- [x] Replace `0.0.0.0:8621` with a container-reachable MCP SSE address.
