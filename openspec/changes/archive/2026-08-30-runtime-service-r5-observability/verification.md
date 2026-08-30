# R5 Verification

## Pre-Apply Review

- Owner decision: approved in conversation before implementation.
- Scope: Runtime Service only; no Platform API, Platform Web, database, Run Explorer, or Langfuse query proxy.
- Implementation rule: no new Builder, Factory, Provider, Registry, Plugin, Middleware framework, or graph factory.

## Checks

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 51 passed, 1 skipped |
| `uv run pytest tests/observability tests/services/reference_agent -q` | 13 passed |
| `LANGFUSE_ENABLED=false RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q` | 1 passed |
| `uv run python -m compileall -q src tests` | passed |
| `uv lock --check` | passed |
| `openspec validate runtime-service-r5-observability --strict --no-interactive` | passed |
| `git diff --check` | passed |
| Locked Langfuse SDK constructor/Callback smoke with local invalid endpoint | initialized successfully |
| Real Langfuse Workflow Trace smoke with configured `.env` | fetched after ingestion delay; name/session verified |
| Real DeepSeek `reference_agent` + Langfuse Trace smoke | fetched after ingestion delay; `AGENT`, `CHAIN`, and `GENERATION` observations verified |

## Evidence

- `LANGFUSE_ENABLED` defaults to disabled and the SDK is lazily imported.
- Explicit enablement validates public key, secret key, and base URL.
- Existing callbacks, metadata, and tags are retained; trusted Runtime metadata overwrites conflicting values.
- Concurrent bindings keep per-Run callback and thread metadata isolated.
- Callback input strings, long values, credential keys, and common token fields are redacted or dropped.
- Run success/failure/timeout/cancel, Tool error, and token counters are emitted through the Runtime diagnostic callback.
- Langfuse flush is bounded and exporter/callback failures are fail-soft.
- All four demo Service entrypoints bind the adapter at their `get_agent(config)` return boundary.

## Uncovered Boundaries And Residual Risk

- The explicitly enabled Langfuse smoke tests used the configured endpoint and test-only prompts; no credentials were printed. Langfuse ingestion was asynchronous and required polling before the Trace became queryable.
- Exact Langfuse server ingestion and UI queryability remain deployment concerns; Runtime output, SSE, Run state, and logs remain authoritative.
- Langfuse SDK callback propagation for every future Deep Agents release must be rechecked when dependencies are upgraded.

## Docs / Runbook Impact

- Updated `apps/runtime-service/README.md` with non-secret Langfuse settings and privacy rules.
- Updated knowledge docs 16 and 28 to make R5 Runtime-only metadata scope explicit.
- No Platform API or production deployment documentation was changed.
