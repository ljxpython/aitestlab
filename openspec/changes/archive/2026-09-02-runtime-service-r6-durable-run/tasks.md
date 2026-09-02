## 1. Version and environment baseline

- [x] 1.1 Lock LangGraph Agent Server/CLI/SDK versions used by R6 and record them in the test report.
- [x] 1.2 Choose the existing CI-supported PostgreSQL/Redis service-container or Compose path without changing production Runtime code.
- [x] 1.3 Add a local smoke command that starts the isolated services and uses a test-only Delegation Token signer.
- [x] 1.4 Pin the accepted GraphHarbor release, expose generic top-level custom-auth scope/policy fields and remove the official in-memory server from production dependencies.

## 2. Durable lifecycle tests

- [x] 2.1 Add integration coverage for `durability="sync"`, Thread reuse, Run completion and checkpoint inspection.
- [x] 2.2 Add interrupt/resume coverage, including two sequential interrupts and invalid checkpoint rejection.
- [x] 2.3 Add Worker termination/restart coverage proving recovery from the latest persisted checkpoint.
- [x] 2.4 Add cancel, timeout and unrecoverable Tool failure coverage with exactly one terminal state.

## 3. Stream recovery tests

- [x] 3.1 Verify monotonic per-Run event cursors and `since` replay against the real Agent Server stream.
- [x] 3.2 Verify reconnect deduplication and cursor-expired behavior.
- [x] 3.3 Verify SSE disconnect leaves the Run active/completed according to execution and does not cancel it.

## 4. Resource and shutdown tests

- [x] 4.1 Add Thread-scoped Workspace reconnect and two-Thread isolation coverage.
- [x] 4.2 Add fail-closed coverage when Backend/MCP/Sandbox reconnect cannot be performed.
- [x] 4.3 Send SIGTERM during an active Run and verify drain, checkpoint persistence and recovery within grace period.
- [x] 4.4 Verify hard Worker loss is recovered or marked with an explicit terminal outcome by Agent Server.

## 5. Evidence and handoff

- [x] 5.1 Run fast Unit/Composition/Contract tests and the isolated R6 durable job.
- [x] 5.2 Record commands, versions, infrastructure inputs, results and uncovered boundaries in `verification.md`.
- [x] 5.3 Update Runtime knowledge docs only for confirmed version-specific behavior; do not add speculative APIs.
- [x] 5.4 Obtain owner review before `/opsx:apply`; after implementation, owner accepts the verified Durable Core scope, syncs accepted specs and archives the change.

## 6. Approved R6 closure gates

- [x] 6.1 Add `host-infra` Compose and a static contract test proving API, Worker, and migration use external PostgreSQL/Redis without declaring local infrastructure.
- [x] 6.2 Align the GraphHarbor/Runtime RuntimeContext producer and consumer schema; reject unknown claims and add focused contract tests.
- [x] 6.3 Fix explicit-port API SIGTERM/restart behavior and add a same-port process-level probe without random-port fallback.
- [x] 6.4 Verify generic correlation fields across API/queue/Worker and exporter fail-soft behavior with focused tests.
- [x] 6.5 Run one formal R6 acceptance after all closure gates pass, record cleanup and residue evidence, and leave unsupported external Sandbox Provider evidence blocked.
- [x] 6.6 Sync accepted specs and archive the change only after verification and owner acceptance are complete.
