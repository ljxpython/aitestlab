## 1. Version and environment baseline

- [x] 1.1 Lock LangGraph Agent Server/CLI/SDK versions used by R6 and record them in the test report.
- [x] 1.2 Choose the existing CI-supported PostgreSQL/Redis service-container or Compose path without changing production Runtime code.
- [x] 1.3 Add a local smoke command that starts the isolated services and uses a test-only Delegation Token signer.

## 2. Durable lifecycle tests

- [x] 2.1 Add integration coverage for `durability="sync"`, Thread reuse, Run completion and checkpoint inspection.
- [ ] 2.2 Add interrupt/resume coverage, including two sequential interrupts and invalid checkpoint rejection.
- [ ] 2.3 Add Worker termination/restart coverage proving recovery from the latest persisted checkpoint.
- [ ] 2.4 Add cancel, timeout and unrecoverable Tool failure coverage with exactly one terminal state.

## 3. Stream recovery tests

- [ ] 3.1 Verify monotonic per-Run event cursors and `since` replay against the real Agent Server stream.
- [ ] 3.2 Verify reconnect deduplication and cursor-expired behavior.
- [ ] 3.3 Verify SSE disconnect leaves the Run active/completed according to execution and does not cancel it.

## 4. Resource and shutdown tests

- [ ] 4.1 Add Thread-scoped Backend reconnect and two-Thread isolation coverage.
- [ ] 4.2 Add fail-closed coverage when Backend/MCP/Sandbox reconnect cannot be performed.
- [ ] 4.3 Send SIGTERM during an active Run and verify drain, checkpoint persistence and recovery within grace period.
- [ ] 4.4 Verify hard Worker loss is recovered or marked with an explicit terminal outcome by Agent Server.

## 5. Evidence and handoff

- [ ] 5.1 Run fast Unit/Composition/Contract tests and the isolated R6 durable job.
- [x] 5.2 Record commands, versions, infrastructure inputs, results and uncovered boundaries in `verification.md`.
- [x] 5.3 Update Runtime knowledge docs only for confirmed version-specific behavior; do not add speculative APIs.
- [ ] 5.4 Obtain owner review before `/opsx:apply`; after implementation, sync accepted specs and archive the change.
