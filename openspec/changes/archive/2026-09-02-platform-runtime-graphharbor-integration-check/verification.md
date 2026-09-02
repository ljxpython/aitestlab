# Verification: Platform API -> GraphHarbor

## Decision

- Pre-apply review: approved by owner in the active conversation.
- Scope: real `platform-api -> Runtime Gateway -> GraphHarbor` HTTP compatibility evidence.
- No GraphHarbor source change, no route ownership change, no production rollout/rollback.

## Checks

| Check | Result |
| --- | --- |
| Local integration harness without explicit environment | `5 tests`, `3 skipped`, no false pass |
| Affected Platform delegation tests | `18 tests`, `OK` |
| Compile check | `compileall` passed |
| Formatting gate | `git diff --check` passed |
| Final real HTTP acceptance | `4 tests`, `OK` |
| Full platform-api unittest discovery | `123 tests`, `2 failures`, `3 skipped`; existing schema-provider baseline failures |

## Real environment

- GraphHarbor API: existing isolated container, `18123/ready` returned `ready=true`.
- GraphHarbor version: `0.13.0.post20` deployment baseline.
- GraphHarbor topology: independent API, Worker, PostgreSQL and Redis containers.
- Platform API: temporary local process on `2144`, stopped after acceptance.
- Platform database: copied to `/tmp/platform-api-graphharbor-integration.db`; existing project data was not modified.
- Catalog precondition: isolated copy mapped catalog runtime IDs to `http://127.0.0.1:18123`, with 4 models and 5 tools.
- Delegation secret: Platform process used the same secret as the running GraphHarbor deployment; values were not printed or committed.

## Evidence covered

- Unauthenticated `GET /api/langgraph/info` returns 401/403 at Platform API.
- Authenticated Platform API `GET /api/langgraph/info` returns standard info shape.
- Authenticated Platform API `POST /api/langgraph/graphs/search` returns `items/total/limit/offset`.
- Authenticated Platform API `POST /api/langgraph/threads` creates a Thread.
- Returned Thread metadata contains the requested marker and the Platform project ID.
- The first real run exposed two configuration/contract failures: mismatched delegation secret and missing Runtime policy claims. Both were corrected before the single final acceptance run.

The full local discovery is not a clean regression gate. Both failures are in the pre-existing
`test_graph_parameter_schema_provider` contract: its fixture points to the removed
`apps/runtime-service/runtime_service` layout and expects the removed `test_case_agent` private
configuration fields. They are unrelated to this change and remain explicitly open rather than
being counted as integration evidence.

## Uncovered boundaries

- Real model Run/stream through Platform Gateway, Run ID projection and context hash for non-empty run context.
- Sandbox/remote MCP recovery and cleanup, Langfuse/OTLP server failure behavior, rollback, Platform canary/route ownership and performance SLO.
- The final acceptance proves the minimum compatibility chain, not unrestricted production cutover.

## Documentation impact

- Added `apps/platform-api/docs/delivery/platform-runtime-graphharbor-integration-checklist.md`.
- Updated Platform docs index and Runtime GraphHarbor selection/alignment documents.
- Updated delegation token contract and policy snapshot implementation in Platform API.
- Owner acceptance: approved sync/archive in the active conversation; accepted spec was synced before archive.
