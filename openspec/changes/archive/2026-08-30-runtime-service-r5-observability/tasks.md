## 1. Dependency And Configuration

- [x] 1.1 Add `langfuse>=4.14,<5` to `apps/runtime-service/pyproject.toml` and refresh the lockfile.
- [x] 1.2 Add non-secret Langfuse configuration documentation and verify the ignored `.env` is loaded by both LangGraph configs.

## 2. Runtime Adapter

- [x] 2.1 Create `src/runtime_service/observability/__init__.py` and `langfuse.py` with lazy SDK import, validated settings, and process-scoped client lifecycle.
- [x] 2.2 Implement per-invocation callback binding that merges callbacks, metadata, and tags without overwriting trusted Runtime fields.
- [x] 2.3 Implement bounded redaction/drop rules for credentials and full content, plus structured warnings and drop/error counters.
- [x] 2.4 Implement bounded shutdown flush and fail-soft handling for callback, exporter, queue, and flush failures.

## 3. Service Integration

- [x] 3.1 Bind the adapter from `reference_agent.get_agent()` after Graph creation while preserving the existing `get_agent(config) -> Pregel` contract.
- [x] 3.2 Bind the same adapter at the explicit return boundary of all Runtime demo services; no service-specific tracing implementation was added.

## 4. Tests And Evidence

- [x] 4.1 Add focused tests for disabled/default behavior, incomplete configuration, metadata merge, trusted identity, redaction, concurrency, Subagent propagation, and fail-soft semantics.
- [x] 4.2 Run real-model E2E with local `.env` and `LANGFUSE_ENABLED=false` by default; record the explicitly enabled Trace smoke-test decision without logging credentials.
- [x] 4.3 Create and maintain `verification.md` with owner pre-apply review, commands, results, uncovered boundaries, residual risk, and docs/runbook impact.
- [x] 4.4 Run `openspec validate runtime-service-r5-observability --strict --no-interactive` and the Runtime test/lint/compile checks.
