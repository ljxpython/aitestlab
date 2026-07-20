# PRD — Containerized Deployment for AITestLab

> Status: Archived. Current deployment behavior lives in `deploy/README.md`.
> Historical names such as `platform-web-vue` and `platform-api-v2` are retained
> only to preserve the original decision record.

- Date: 2026-04-21
- Mode: B3 research / clarification / PRD only
- Source context: `.harness/context/containerized-deployment-20260421T131133Z.md`

## Problem
当前仓库有清晰的本地脚本和逐服务启动口径，但没有面向“用户直接把项目跑起来”的正式容器化交付面。需求同时覆盖：

1. 一个整仓 Docker Compose 方案，不带 Nginx。
2. 一个整仓 Docker Compose 方案，带 Nginx 单入口。
3. 一个 `apps/runtime-service` 单应用 Docker 部署方案。

该需求已经超出单 leaf 本地改动，触及正式交付物、跨应用依赖编排、真实环境变量与用户密钥输入，因此必须按 B3 先收敛方案、列清真实输入，再进入实现。

## Decision
本次需求收敛为一个三交付面方案：

1. `runtime-service` 单应用容器化：
   - 主推荐方案基于当前已验证过的 demo 路线。
   - 该方案以 Redis + Postgres 为必备配套。
   - 该方案默认沿用当前 `runtime_service/langgraph.json` 已部署的 graph 集。
   - 该方案不要求 `LANGSMITH_API_KEY` 与 `LANGGRAPH_CLOUD_LICENSE_KEY`。

2. 整仓 Compose（不带 Nginx）：
   - 作为“开发/内网联调友好”的多端口方案。
   - 暴露 canonical app ports：
     - `platform-web-vue`: `3000`
     - `platform-api-v2`: `2142`
     - `runtime-service`: `8123`
     - `interaction-data-service`: `8081`

3. 整仓 Compose（带 Nginx）：
   - 作为“单入口/更接近交付”的方案。
   - Nginx 负责统一入口与反向代理。
   - v1 默认只公开平台入口，不把 `runtime-service` 直连 API 暴露为默认公网路径。
   - LightRAG / RAG 作为外部依赖，不纳入首版 compose。

## Goal
- 让用户以容器方式快速使用当前正式主链项目。
- 保持当前主链职责边界不被容器层破坏。
- 在正式实现前把交付物、依赖拓扑、真实输入、验证路径收敛清楚。
- 把“配置归属”“外部依赖归属”“更新重建流程”“文档补齐清单”一起收敛。

## Scope
- 定义 `runtime-service` 单应用容器化目标形态。
- 定义两个整仓 Compose 交付面：
  - 无 Nginx
  - 有 Nginx
- 定义未来应新增的部署文件、env 模板、脚本与文档位置。
- 定义 required real inputs 和 optional external inputs。
- 定义实现阶段必须验证的启动、健康检查、最短链 smoke 与更新重建 runbook。

## Not-do list
- 本轮不实现任何 Dockerfile、compose、Nginx 配置或脚本。
- 本轮不修改 `docs/local-deployment-contract.yaml` 的 canonical default-local 语义。
- 本轮不把 `runtime-web` 纳入 v1 正式容器化主线。
- 本轮不发明新的跨服务业务 contract。
- 本轮不把 `platform-web-vue` 直连 `interaction-data-service`。
- 本轮不把 `platform-api-v2` 和 `runtime-service` 合并成一个容器/应用。
- 本轮不把 LightRAG / RAG 服务编排进首版 compose。

## Locus / Layer
- Repo-level / process / deployment planning
- Primary leaf:
  - `apps/runtime-service`
- Supporting leaves:
  - `apps/platform-api-v2`
  - `apps/platform-web-vue`
  - `apps/interaction-data-service`

## Chain map
- Formal chain:
  - `platform-web-vue -> platform-api-v2 -> runtime-service`
  - `platform-api-v2 -> interaction-data-service`
  - `runtime-service -> interaction-data-service`
- External dependency chain:
  - `platform-api-v2 -> LightRAG HTTP`
  - `runtime-service -> knowledge MCP SSE`
- Optional non-v1 debug path:
  - `runtime-web -> runtime-service`

## Responsibility boundary / ownership split
- `runtime-service`
  - owns LangGraph runtime, graph registration, runtime auth mode, model config, custom routes.
  - owns service-private knowledge MCP default mapping.
- `platform-api-v2`
  - owns control-plane gateway, JWT/auth, operations worker, upstream runtime integration.
  - owns platform-facing RAG HTTP URL config.
- `interaction-data-service`
  - owns result-domain storage and HTTP contract.
  - v1 compose runs DB-backed.
- `platform-web-vue`
  - owns platform UI, API origin config, no direct result-domain ownership.
- Nginx variant
  - owns ingress/routing only; it does not absorb business logic.
- LightRAG / RAG
  - remains an external dependency in v1, not a stack-owned service.

## Standards loaded
- `AGENTS.md`
- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`
- `docs/local-deployment-contract.yaml`
- `docs/deployment-guide.md`
- `docs/env-matrix.md`
- `docs/ai-deployment-assistant-instruction.md`
- `apps/runtime-service/README.md`
- `apps/runtime-service/runtime_service/docs/standards/01-harness-overview.md`
- `apps/runtime-service/runtime_service/docs/standards/02-architecture.md`
- `apps/runtime-service/runtime_service/tests/harness/README.md`
- `apps/runtime-service/runtime_service/docs/01-auth-and-sdk-validation.md`
- `apps/runtime-service/runtime_service/services/test_case_service_v2/README.md`
- `apps/platform-api-v2/README.md`
- `apps/platform-api-v2/docs/delivery/runbook.md`
- `apps/interaction-data-service/README.md`

## Research synthesis

### 1. Why this is B3
- Cross-leaf deployment orchestration is required.
- Formal artifacts are explicitly requested.
- Real user-owned secrets/configs are mandatory for a truthful rollout.
- The work must also define operational update/rebuild guidance and docs delivery obligations.

### 2. Runtime-service deployment reality
`runtime-service` is currently documented and validated around `langgraph dev`, app-local `.env`, and app-local `conf/settings.yaml`. For this repo, planning has now converged on:

- do not gate the plan on `LANGSMITH_API_KEY`
- do not gate the plan on `LANGGRAPH_CLOUD_LICENSE_KEY`
- use the already-validated demo deployment shape as the primary implementation reference
- keep Redis + Postgres in the runtime deployment topology

Official LangGraph deployment docs remain informative, but they are no longer the primary gating contract for this repo’s v1 containerization path.

### 3. Full-stack compose reality
The repo’s canonical local chain is already clear. The missing piece is container packaging.

Important operational fact:
- `platform-api-v2` in multi-container mode should not stay on `SQLite + db_polling` as the long-term compose default.
- API and worker as separate containers are better aligned with:
  - Postgres
  - `redis_list`

So the full-stack compose default should converge to:
- one Postgres service
- one Redis service
- one `runtime-service`
- one `interaction-data-service`
- one `platform-api-v2`
- one `platform-api-v2-worker`
- one `platform-web-vue`
- plus optional ingress Nginx in the Nginx variant

Additional confirmed rules:
- `interaction-data-service` v1 will run with DB enabled inside compose.
- LightRAG / RAG remains an external dependency in v1.
- `runtime-service`、`platform-api-v2`、`interaction-data-service` 共用一个 Postgres 实例。
- The stack should accept two optional external addresses:
  - platform-facing RAG HTTP URL
  - runtime-facing knowledge MCP SSE URL

### 4. Graph scope risk for runtime-service
`apps/runtime-service/README.md` explicitly documents blocking-IO sensitivity for at least:
- `research_demo`
- `deepagent_demo`
- `test_case_agent`

At the planning level, the current decision is to follow the currently deployed graph registration set rather than narrowing now. This remains a delivery risk to be verified during implementation, not a planning blocker.

### 5. Knowledge dependency configuration reality
- `platform-api-v2` already has a clear config surface for upstream knowledge HTTP in its settings model.
- `runtime-service` public MCP registry is only for shared/local MCP servers; private knowledge MCP for `test_case_service_v2` is currently service-private and config-driven.
- Therefore, v1 containerization should not move private knowledge MCP into the global MCP registry.
- Instead, it should add env-backed defaults for service-private runtime config.
- Planned env names for runtime private knowledge MCP:
  - `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
  - `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
  - `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
  - `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`
- Planned env ownership:
  - `apps/runtime-service/deploy/.env.runtime-service.example`
  - `deploy/.env.stack.example`

## Chosen architecture

### A. Single-app runtime-service lane
Primary recommendation:
- build around the repo’s validated demo-style runtime topology
- runtime container + Redis + Postgres
- default config source:
  - `runtime_service/langgraph.json`
- optional auth profile:
  - `runtime_service/langgraph_auth.json`

Planned future artifact shape:
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/.env.runtime-service.example`
- `apps/runtime-service/deploy/README.md`
- one repo-managed runtime image build path

Build-path decision:
- Use a repo-managed Dockerfile under `apps/runtime-service/deploy/`.
- The Dockerfile may initially be derived from `langgraph dockerfile`, but the generated result should be checked into the repo and maintained as a first-class deployment artifact.
- End users should be able to run `docker compose build` / `docker compose up -d` without needing to install LangGraph CLI locally as a deployment prerequisite.
- Runtime private knowledge MCP defaults should be supplied by deployment env files, using the finalized `TEST_CASE_V2_*` env names, and then mapped into service-private runtime config defaults.

### B. Full-stack compose without Nginx
Planned future artifact shape:
- `deploy/docker-compose.stack.yml`
- `deploy/.env.stack.example`
- `deploy/README.md`

Service set:
- `langgraph-postgres`
- `langgraph-redis`
- `runtime-service`
- `interaction-data-service`
- `platform-api-v2`
- `platform-api-v2-worker`
- `platform-web-vue`

Networking rule:
- internal service-to-service DNS only
- direct host port exposure for canonical dev ports

Queue/storage defaults:
- `runtime-service`: compose-managed Postgres + Redis
- `platform-api-v2`: compose-managed Postgres + `redis_list`
- `interaction-data-service`: v1 runs with `INTERACTION_DB_ENABLED=true` and a compose-managed `DATABASE_URL`
- Postgres strategy: one shared Postgres instance for the stack, with service-specific DSN/database separation as the default implementation direction
- Default database naming on the shared Postgres instance:
  - `runtime_service`
  - `platform_api_v2`
  - `interaction_data_service`
- `platform-api-v2`: supports optional external RAG HTTP URL
- `runtime-service`: supports optional external knowledge MCP SSE URL

### C. Full-stack compose with Nginx
Planned future artifact shape:
- `deploy/docker-compose.stack.nginx.yml`
- `deploy/nginx/default.conf`

Ingress rule:
- Nginx is the only default public entrypoint.
- v1 route plan:
  - `/` -> `platform-web-vue`
  - `/api/` -> `platform-api-v2`
  - `/_system/` -> `platform-api-v2`
- `runtime-service` remains internal by default.
- If a direct runtime debug route is required later, expose it explicitly as a separate decision, not as a silent default.

## Alternatives

### Chosen
Three-surface plan:
- demo-style `runtime-service`
- full stack without Nginx
- full stack with Nginx

### Rejected
Use only one giant compose and skip single-app runtime-service packaging.

Reason:
- does not satisfy explicit requirement
- makes runtime-service independently reusable only through the full control-plane stack

### Rejected
Keep `platform-api-v2` on `SQLite + db_polling` inside the composed multi-container stack.

Reason:
- worker/API split is cleaner and more truthful with Postgres + Redis
- avoids fragile shared-volume/local-file semantics as the default compose story

### Rejected
Expose `runtime-service` publicly by default in the Nginx stack.

Reason:
- default product surface is platform entry, not raw runtime debug surface
- smaller external surface is safer and easier to explain

### Rejected
Bundle LightRAG / RAG into the first compose stack.

Reason:
- user explicitly chose external dependency mode
- reduces v1 stack complexity
- keeps repo containerization focused on owned services first

## I/O contract

### Input
Required before truthful implementation:
- repo-shaped runtime model config
- platform JWT secrets
- optional external knowledge dependency endpoints

### Output
Implementation phase must eventually produce:
- app-level runtime deployment assets
- root-level full-stack compose assets
- nginx config for ingress variant
- env templates
- deployment docs
- rebuild / recreate / rollback runbook
- checklist-style delivery docs

### Failure semantics
- Missing runtime model config blocks `runtime-service` truthfully starting.
- Missing JWT secrets blocks non-demo `platform-api-v2` deployment.
- Missing optional RAG endpoints does not block baseline stack startup, but blocks knowledge-dependent flows.

## Required real inputs from the user

Reply once with the real inputs below. These are the inputs that materially affect implementation shape.

### Mandatory
1. Runtime model config in repo shape
   - Please provide one repo-shaped config patch for:
     - `apps/runtime-service/runtime_service/.env`
     - `apps/runtime-service/runtime_service/conf/settings.local.yaml`
   - Minimum truthful shape:

```text
# apps/runtime-service/runtime_service/.env
APP_ENV=<test|production|...>
MODEL_ID=

# apps/runtime-service/runtime_service/conf/settings.local.yaml
default:
  default_model_id: <your_reasoning_model_id>
  models:
    <your_reasoning_model_id>:
      alias: <optional_display_name>
      model_provider: <provider>
      model: <model_name>
      base_url: <provider_base_url>
      api_key: <your_api_key>
```

2. Runtime multimodal expectation
   - If the deployed stack must support current multimodal/default parser flows, provide the additional model block for the multimodal model too.

3. Platform API secrets
   - Provide real values or confirm temporary local-only defaults are acceptable for first implementation:
     - `PLATFORM_API_V2_JWT_ACCESS_SECRET`
     - `PLATFORM_API_V2_JWT_REFRESH_SECRET`

4. Bootstrap admin policy
   - Choose one:
     - keep temporary local-only `admin / admin123456`
     - provide replacement bootstrap username/password
     - disable bootstrap admin for the intended target environment

### Optional but likely useful
- platform-facing RAG HTTP URL
  - target owner: `platform-api-v2`
  - future env home: `apps/platform-api-v2/.env`
- runtime-facing knowledge MCP SSE URL
  - target owner: `runtime-service` service-private config
  - future env home:
    - `apps/runtime-service/deploy/.env.runtime-service.example`
    - `deploy/.env.stack.example`
  - planned env name: `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
- exact public port/domain for Nginx ingress if not default `80`

## Planned implementation phases

### Phase 1
`runtime-service` single-app deployment
- align repo deployment assets to the validated demo lane
- add repo-managed Dockerfile for runtime-service image build
- add env-based defaults for service-private knowledge MCP config using:
  - `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
  - `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
  - `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
  - `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`
- produce runtime deploy docs/assets

### Phase 2
full-stack compose without Nginx
- add missing app Dockerfiles where needed
- wire inter-service env defaults
- wire optional external RAG HTTP URL and knowledge MCP SSE URL
- get minimal health checks green

### Phase 3
full-stack compose with Nginx
- add ingress config
- validate single-entry UX and proxy routes

### Phase 4
operations and update runbook
- define rebuild / recreate / rollout steps for changed services
- define config-only restart steps
- define DB-affecting update steps
- define rollback path

## Verification plan
- artifact lint:
  - all compose files pass `docker compose config`
- runtime-service single-app smoke:
  - container startup
  - Redis/Postgres dependency health
  - runtime health endpoint success
- full stack no-nginx smoke:
  - web root reachable
  - platform API health ready
  - runtime health reachable
  - interaction-data-service health reachable
  - worker readiness healthy
  - interaction-data-service DB-backed flows reachable
- full stack nginx smoke:
  - single entrypoint serves UI
  - `/api/*` and `/_system/*` route correctly
- optional dependency smoke:
  - when RAG HTTP URL is configured, project-knowledge HTTP path reaches upstream
  - when knowledge MCP SSE URL is configured, runtime service-private MCP config resolves from env defaults
- configuration validation:
  - missing required envs fail fast with actionable errors

## Acceptance criteria
1. A runtime-service-only container deployment path is documented and reproducible.
2. A root full-stack compose exists without Nginx and respects current canonical service chain.
3. A root full-stack compose exists with Nginx single entrypoint.
4. The runtime-service lane explicitly documents that it follows the repo’s validated demo-style deployment path.
5. Required real inputs are documented in repo shape, not as scattered secrets.
6. `platform-api-v2` worker is included in the multi-container stack.
7. No default deployment path bypasses `platform-api-v2` to let `platform-web-vue` hit `interaction-data-service` directly.
8. `interaction-data-service` runs DB-backed in the v1 stack.
9. External RAG HTTP and runtime knowledge MCP SSE dependencies are optional and documented as such.
10. Verification steps are concrete enough to prove health before claiming completion.
11. Rebuild / recreate / rollback runbook is documented.
12. End users can build the runtime-service image through repo-local compose assets without installing LangGraph CLI.

## Risks
- Some currently registered runtime graphs may be unsafe to ship unchanged into a containerized lane because of blocking-IO constraints.
- `platform-web-vue` and `interaction-data-service` still lack repo-native Docker packaging and will need first-class build/serve decisions.
- Service-private knowledge MCP config currently lives in runnable config shape; env-backed default mapping still needs explicit design and implementation.

## Retro / doc decision
- Add a dedicated containerized deployment guide rather than mutating the current local-deployment contract into something it is not.
- Update app READMEs only after assets exist and are verified.
- Keep `docs/local-deployment-contract.yaml` as canonical for current local default bring-up until containerized deployment is actually implemented and accepted.
- Add a checklist-style delivery page so planning can be tracked as concrete TODOs, not only prose PRD/Test Spec.
