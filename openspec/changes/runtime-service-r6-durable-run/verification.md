# R6 Verification

## Pre-apply review

- Status: post20 formal acceptance passed; the change remains open for owner acceptance, spec sync and archive.
- Owner review: completed before `/opsx:apply`.
- Scope: `apps/runtime-service` Durable Run validation; Platform API is out of scope.
- Agent Server decision: GraphHarbor selected as the R6 candidate; its repository remains generic and
  Runtime-specific Principal/Policy structures stay in this repository.
- Owner approval: foundational cross-repository implementation and an isolated PostgreSQL 16.9 /
  Redis 7.4.2 environment were explicitly approved on 2026-09-01.

## Planned checks

- Formal GraphHarbor install: resolve the published `graphharbor==0.13.0.post20` and its locked
  `graphharbor-runtime==0.13.0.post20` from PyPI; no local source override or wheel artifact is used.
- Fast: `uv run --no-sync pytest tests -m "not integration and not durable and not e2e"`
- Durable: `uv run --no-sync pytest tests/durable -m durable`
- Agent Server integration: `uv run --no-sync pytest tests/integration -m integration`
- Smoke: isolated PostgreSQL/Redis/Worker with local Delegation Token and real Agent Server.

## Evidence to record during implementation

- Historical post17 lock record: `langgraph==1.2.11`, `langgraph-sdk==0.4.3`,
  `graphharbor==0.13.0.post17` and `graphharbor-runtime==0.13.0.post17`. This record is superseded by
  the post20 closure target; Runtime no longer directly depends on `langgraph-cli[inmem]`,
  `langgraph-api` or `langgraph-runtime-inmem`.
- Infrastructure startup command and configuration source.
- Production deployment must provide separate external delegation JWT and internal RuntimeContext
  settings: `PLATFORM_RUNTIME_DELEGATION_*` and `GRAPHHARBOR_RUNTIME_CONTEXT_*`.
- Thread/Run/checkpoint identifiers and event cursor assertions (redacted).
- Worker restart, SIGTERM, cancel, timeout, Tool failure and reconnect results.
- Uncovered boundaries and any version-specific behavior requiring follow-up.

## Current execution results

### Historical evidence superseded by the post20 closure batch

The earlier post17/post18 evidence below remains useful for provenance, but it is not the current
release gate. Any post17/post18/post19 result must be re-established against post20 after the closure tasks.

### Historical post19 Runtime review (2026-09-02)

- Isolated acceptance project: `r6-verify`, API `http://127.0.0.1:18133`; PostgreSQL, Redis and Workspace
  volumes are separate from the preserved `r6-current` environment. The old `r6-current` PostgreSQL
  volume contained incompatible historical `thread_id` types and was not modified.
- Compose graph source is configurable through `RUNTIME_GRAPH_CONFIG`; the R6 acceptance command uses
  `/app/langgraph.r6.json`, while the production default remains `/app/langgraph.json`.
- Published GraphHarbor package and container distribution are both `graphharbor==0.13.0.post19` and
  `graphharbor-runtime==0.13.0.post19`; the Docker build asserts both versions.
- Real API/Worker durable suite with the Worker deadline at 300 seconds:
  `pytest tests/durable -m durable -q -rs` returned **14 passed, 1 skipped in 157.11s**;
  the only skip is the separately gated timeout case.
- Compose lifecycle suite against the actual `worker` service returned **restart 1 passed** and
  **SIGTERM 1 passed**. These tests use the deterministic `recovery_demo` and assert that the
  `checkpointed` marker is recovered before completion, so model latency is outside this gate.
- Independent `r6_worker_fault_injection.py` runs against the same PostgreSQL/Redis chain passed for both
  `SIGTERM` and `SIGKILL`. Each recovered from `marker=checkpointed`, reached `success`, persisted one
  `shutdown_requeue` and one terminal event.
- The timeout acceptance uses `GRAPHHARBOR_RUN_TIMEOUT_SECONDS=10`; normal real-model runs remain successful,
  while `timeout_demo` reaches exactly one `timeout/timeout` terminal result.

- Isolated infrastructure: PostgreSQL 16.9 at `127.0.0.1:65432` and Redis 7.4.2 at
  `127.0.0.1:65379`; GraphHarbor used a non-superuser application role, a dedicated database and
  a namespaced Redis prefix. Credentials are intentionally omitted.
- Published package: `graphharbor==0.13.0.post19` and
  `graphharbor-runtime==0.13.0.post19`; production API readiness passed for graph discovery,
  PostgreSQL, all three schema heads, Redis and queue.
- Earlier final-wheel evidence recorded `10 passed, 5 skipped`; that result is superseded by the latest
  `r6-verify` run above. Skips remain excluded from pass counts.
- GraphHarbor real-process fault harness: `SIGTERM` persisted one `shutdown_requeue` and recovered
  from the checkpoint; `SIGKILL` recovered after lease expiry. Both reached `success` with exactly
  one PostgreSQL terminal event.
- The Worker fault harness used the same signing key as the API process explicitly, preventing
  `R6_TEST_TOKEN_SECRET` / `PLATFORM_RUNTIME_DELEGATION_SECRET` environment drift.
- The real resumable stream test observed strictly increasing event IDs, replayed only IDs after
  the acknowledged cursor, and returned `cursor_expired` with `run_snapshot` for an evicted cursor.
  The disconnect test closed its observer after metadata and the Run subsequently reached `success`.
- GraphHarbor terminal race harness: duplicate queue hints produced one claim; concurrent reaper,
  late finalize and cancel produced one terminal event and removed the lease.
- Runtime R6 terminal acceptance config registers deterministic `failure_demo` and `timeout_demo`
  graphs without changing production `langgraph.json`. With the Worker deadline set to
  `GRAPHHARBOR_RUN_TIMEOUT_SECONDS=10`, PostgreSQL recorded exactly one terminal event for each:
  `error/business_error` for `runtime.demo.unrecoverable_tool` and `timeout/timeout` for the
  configured deadline. Runtime composition coverage remains green.
- GraphHarbor's generic Worker deadline is configured by the optional positive
  `GRAPHHARBOR_RUN_TIMEOUT_SECONDS`; its PostgreSQL contract test passed (`1 passed, 47 deselected`)
  and Ruff passed for the changed GraphHarbor files.
- Runtime fast suite after installing the published GraphHarbor package: **182 passed, 20 deselected in 47.41s**.
  Integration, durable and real-service E2E tests remain separately gated; the real GraphHarbor
  runs above provide the R6 chain evidence.
- Deep Agent tracing coverage uses the registered `summarizer` subagent and verifies the
  `deepagents==0.7.8` contract separately: the child result is returned in a `ToolMessage`,
  the parent produces the final message, and parent/child/parent model callbacks are observed.
- Workspace quota validation and mutation now share a per-Thread cross-process lock; the
  concurrent quota test proves that only one competing write can consume the last quota.
- Langfuse SDK queue saturation is covered with the pinned OpenTelemetry `BatchSpanProcessor`:
  a blocked exporter causes bounded non-blocking drops with the SDK `Queue full, dropping Span`
  signal, while the Runtime process remains available.
- GraphHarbor full suite: **132 passed, 14 skipped in 124.15s**; Ruff, mypy, lock and version checks
  passed. Wheels installed and started on Python 3.11, 3.12 and 3.13.
- GraphHarbor production contract after adding the generic Worker deadline: **48 passed in 48.91s**;
  targeted Ruff and mypy also passed.
- Runtime Thread Workspace acceptance against the published GraphHarbor package has partial evidence with
  isolated PostgreSQL 16.9, Redis 7.4.2, a real API and independent replacement Workers:
  `scripts/r6_workspace_acceptance.py` completes the write, replacement-Worker read, Thread/tenant
  isolation and unavailable-root fail-closed checks, but fails on the subsequent API restart readiness.
  A same-port serve restart probe reproduces the second-process non-listening condition within 120 seconds.
  The prior all-pass claim is therefore superseded; credentials and identifiers are intentionally omitted.
- Formal PyPI installation resolved both `0.13.0.post19` distributions into the Runtime `.venv`; module
  paths point to `site-packages`, and the lock entries use the PyPI registry rather than a local directory.
  The Dockerfile installs the same pinned versions and asserts their distribution metadata at build time.
- Backend/MCP/Sandbox reconnect fail-closed composition coverage passed: **5 passed in 10.64s**.
  Backend binding is checked before model construction; missing MCP registry entries and missing
  Sandbox credentials return stable `runtime.*.recovery_failed` errors.
- Real local Streamable HTTP MCP acceptance passed with an independent provider process, GraphHarbor API,
  replacement Worker, PostgreSQL and Redis: discovery/tool invocation, Worker replacement reconnect and
  provider restart recovery all succeeded after provider readiness polling. Missing Thread binding and
  unavailable provider both produced `runtime.mcp.recovery_failed`; all five Runs had exactly one terminal
  event. The acceptance entrypoint is
  `scripts/r6_mcp_acceptance.py`, its deterministic provider is `scripts/r6_mcp_server.py`, and the graph is
  `src/runtime_service/graphs/mcp_probe.py`. This is local provider evidence only; arbitrary remote MCP
  credentials, network and production cleanup remain open.
- Real Langfuse smoke passed with the published Runtime dependencies and credentials loaded from the local
  environment: `RUNTIME_E2E=1 RUNTIME_R5=1 uv run --frozen pytest tests/e2e/test_langfuse_real.py -m e2e -q`
  returned **1 passed in 13.99s**. This proves `auth_check`, workflow trace emission, bounded flush,
  and a bounded-retry service-side query of the final Trace and Observation for the smoke path.
  Runtime exporter failure classification and stable `event_dropped` counter are covered by
  `tests/observability/test_langfuse.py`; real service-side failure responses, a secondary generic
  OTLP destination, and cross-service propagation remain unverified.

- Cross-network SSE acceptance passed from an independent Docker bridge namespace with two SDK clients:
  `scripts/r6_network_sse_acceptance.py` returned `status=passed`, initial cursor `4`, two post-cursor
  events and final Run `success`. This is transport evidence for the isolated deployment, not packet-loss
  or multi-host failover evidence.
- Isolated PostgreSQL backup/restore acceptance passed:
  `scripts/r6_postgres_backup_restore.sh` read-only dumped the current R6 source container and restored
  successfully into a temporary `pgvector/pg16` container; source mutation was `none` and the temporary
  container was removed by the script.
- Performance baseline passed at four concurrent real API/Worker Runs:
  `scripts/r6_performance_baseline.py --url http://127.0.0.1:18123 --runs 4` returned all `success`;
  first event p50/p95 `508.63/535.72 ms`, completion p50/p95 `15648.47/15664.91 ms`, checkpoint read
  p50/p95 `27.39/42.80 ms`. This is baseline-only; queue lag and DB/Redis watermarks were not observable
  through the public API and no SLO decision was made.
- Runtime rollback is now an explicit dry-run/apply script at `scripts/r6_runtime_rollback.sh`. It requires
  a caller-supplied known-good image and `R6_ROLLBACK_CONFIRM=1`, never runs `compose down`, and does not
  delete PostgreSQL/Redis volumes. Platform route rollback remains outside this Runtime change and has not
  been executed.

### Repeat audit: API restart boundary (2026-09-02)

- The prior Workspace acceptance result is superseded for the API-restart claim. With the published
  `graphharbor==0.13.0.post19` and `graphharbor-runtime==0.13.0.post19`, the isolated acceptance repeatedly
  completed the Workspace write and replacement-Worker read, then failed at API `SIGTERM -> restart` readiness.
- A minimal same-port probe reproduced the boundary without a business Run: the first `serve` became ready and
  exited on `SIGTERM`; the second `serve` process remained alive but did not listen within 120 seconds.
- This is recorded as `30-R6-010=partial/❌`. Workspace Thread/tenant isolation and Worker recovery remain
  evidenced, but API restart recovery is not accepted. The resident Compose Worker was restored after testing.

### Closure gates locally verified (2026-09-02)

- `6.2` passed in the current GraphHarbor source tree. The strict RuntimeContext envelope rejects unknown
  top-level and nested claims, binds the context to one Run and scope, and preserves only the generic
  correlation fields. Evidence: `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/auth.py`,
  `graph_executor.py`, `thread_config.py`, and the focused cases in
  `libs/langgraph-runtime-pg/tests/test_production_contract.py`.
- `6.3` passed against locally rebuilt GraphHarbor wheels. The CLI now sets `SO_REUSEADDR` for the
  explicit requested port and raises on an unavailable explicit port; it does not fall back to a random
  port. The process probe `apps/runtime-service/scripts/r6_api_restart_probe.py` ran in the existing
  Compose network with a temporary `--rm` container, PostgreSQL `postgres:5432`, Redis `redis:6379`,
  port `18124`, and timeout `120s`; result was `{"status":"passed","port":18124,"first_exit_code":-15,"second_exit_code":null}`.
  This is local-source-wheel evidence. It does not prove that the already published PyPI `post19` wheel
  contains this source fix.
- `6.4` passed in focused contract tests. API-produced correlation is covered by
  `test_api_principal_producer_preserves_correlation`; queue/Worker forwarding is covered by
  `test_worker_publish_event_forwards_trace_context` and
  `test_worker_run_forwards_trace_context_to_graph_events`; Runtime exporter fail-soft and queue-drop
  behavior is covered by `tests/observability/test_langfuse.py` and
  `tests/observability/test_graph_tracing.py`. The prior focused runs returned `17 passed` for the
  explicit node-id contract set and `2 passed` for Worker correlation.
- No broad Runtime or GraphHarbor regression suite was rerun after this probe. The one-verification rule
  applies to this closure batch; existing results remain historical evidence and are not silently merged
  into the probe result.

### Historical formal post20 acceptance attempt before Harness repair (2026-09-02)

- Artifact and environment: published `graphharbor==0.13.0.post20` and
  `graphharbor-runtime==0.13.0.post20` inside image `aitestlab-runtime-service:r6-post20`;
  Compose project `r6-verify-post20-20260902`; API host port `18134`; separate PostgreSQL, Redis and
  Workspace volumes; `/ready` returned `ready=true` with graph, PostgreSQL, schema, Redis and queue checks
  all true. No credentials are recorded.
- The first command omitted `RUNTIME_DURABLE_URL`; the smoke script correctly defaulted to `8123`, while
  the container API listens on `8000`. It failed before creating a Thread and is classified as a Harness
  configuration error, not product evidence.
- The first Worker fault attempt ran while the Compose Worker was still active. It recovered the Run but
  recorded `shutdown_requeue_total=0`; because another Worker could claim the same PostgreSQL Run, this is
  invalid Harness evidence and not a GraphHarbor failure.
- After stopping the resident Compose Worker, the corrected continuation passed: Durable smoke returned
  `success` with a persisted checkpoint; independent `SIGTERM` and `SIGKILL` Worker replacement both
  recovered from `marker=checkpointed`, returned `success`, recorded exactly one terminal event, and the
  `SIGTERM` case recorded `shutdown_requeue_total=1`; Workspace acceptance returned
  `same_thread_reopened=true`, `api_restart_reopened=true`, isolation and unavailable-root checks passed;
  MCP discovery/call, Worker replacement, provider restart and fail-closed cases passed; the same-port API
  restart probe returned `status=passed`.
- The independent Docker bridge SSE step did not produce a cursor because it was started before the
  Compose Worker was restored. The client then failed with `first client received no SSE event cursor`;
  this is Harness-blocked evidence, not a product assertion, and the SSE step was not retried.
- Cleanup ran with `docker compose -p r6-verify-post20-20260902 -f
  apps/runtime-service/deploy/docker-compose.runtime-service.yml down --remove-orphans` without
  `--volumes`; the temporary containers and network were removed. The `post20` image and named volumes
  were retained, and the old `post19` project was not touched.
- Conclusion: the released `post20` artifact proves the listed Durable, Worker, Workspace, MCP and API
  restart boundaries, but formal R6 acceptance is `blocked` because the bridge SSE evidence was not
  completed in the same batch. Do not mark `6.5` or `6.6` complete.

### Closure batch status

- Owner approval for the host-infra, strict RuntimeContext, same-port restart, and generic observability
  closure gates was recorded on 2026-09-02.
- `6.1` through `6.5` are verified against the released `post20` artifact. `6.5` is closed by the one
  post-repair formal acceptance below. `6.6` remains pending until owner acceptance, spec sync and archive.

### SSE Harness repair (post20)

- Added `apps/runtime-service/scripts/r6_network_sse_acceptance.sh` as the only bridge SSE acceptance
  entrypoint. It requires an explicit `r6-*` Compose project, Compose env file, published Runtime image,
  host API port and test token; it does not load the deployment env file into the client container.
- The entrypoint stops and starts the selected Compose `worker` service with `--scale worker=1`, checks
  that exactly one Worker container is running, waits for API `/ready` using JSON semantics, and invokes
  the client with an explicit `RUNTIME_DURABLE_URL` pointing at the host mapping.
- The Python client now runs a deterministic `recovery_demo` Run and waits for `success` before creating
  the actual disconnect/reconnect Run. This is the Worker functional-readiness gate; a running container
  alone is not treated as Worker readiness. SSE reads have bounded waits and report API/Worker readiness
  in the structured result.
- Static checks after the repair: Python compile, Shell syntax, client `--help`, Ruff check/format, and
  `git diff --check` passed.

### Formal post20 acceptance after Harness repair (2026-09-02)

- The repaired bridge SSE Harness was executed exactly once against the published `post20` image, with
  API and Worker readiness gates, one Compose Worker, an independent Docker bridge client namespace and
  bounded SSE reads.
- The structured result was:

```json
{
  "status": "passed",
  "api_readiness": "passed",
  "worker_readiness": "passed",
  "initial_cursor": 4,
  "resumed_event_count": 2,
  "run_status": "success"
}
```

- The result proves the formal bridge SSE boundary: the first client received a cursor, the second client
  resumed strictly after that cursor, and the Run reached `success` without cancellation.
- Cleanup completed with `project_containers=0`, `project_networks=0`, `port_18135_listeners=0` and
  `retained_volumes=3`; the prior `post19` environment was not touched.
- This closes `30-R6-008` and OpenSpec `6.5`. `6.6` remains unchecked because owner acceptance, spec sync
  and archive are separate gates. Production cutover remains blocked by the external Sandbox/remote MCP
  matrix, exporter service-failure coverage, rollback rehearsal and Platform route ownership.

## Remaining R6 boundaries

- Runtime-specific Worker replacement is covered by `scripts/r6_worker_fault_injection.py` against
  the isolated GraphHarbor API, independent Worker, replacement Worker, PostgreSQL and Redis.
- SSE replay, cursor expiration and controlled observer disconnect are covered by
  `tests/durable/test_agent_server_durable.py`; transport-level packet loss across network nodes
  remains outside this local evidence.
- Backend/MCP/Sandbox reconnect adapters and fail-closed tests are implemented. Local Workspace quota
  mutation is serialized per Thread, and a real LangSmith Sandbox `403` is normalized to the stable
  recovery error. Local Streamable HTTP MCP
  discovery, call, Worker replacement and provider restart are covered by a real-process acceptance;
  arbitrary remote MCP and LangSmith Sandbox reconnect/cleanup across Worker replacement are not executed,
  so provider-level production readiness remains unproven. Thread Workspace has separate real-process evidence.
- Runtime pins the published GraphHarbor release and removes the official in-memory server from direct
  production dependencies. The Docker build installs both GraphHarbor distributions from PyPI without
  a development-machine path override. The released `post20` Runtime image passed the same-port restart
  probe; production rollout and rollback rehearsal remain open.
- Platform gateway routing, rollout and rollback remain outside R6 and production readiness stays
  `not_ready`.

## Docs and runbook impact

- Update `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` with confirmed R6 results.
- Update `23-graph-thread-backend-checkpoint-lifecycle-design.md`, `24-package-langgraph-startup-shutdown-design.md`
  or `25-runtime-testing-and-cross-service-contract-design.md` only when implementation evidence changes a decision.
