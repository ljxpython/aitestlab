## 1. Contract and configuration

- [ ] 1.1 Add typed legacy/GraphHarbor upstream and route-policy settings with default `0%` GraphHarbor traffic.
- [ ] 1.2 Add a permission-protected route-policy read/write contract, validation, audit event and masked configuration snapshot.
- [ ] 1.3 Add startup/readiness validation for upstream URLs and platform-api/GraphHarbor delegation JWT issuer/audience alignment.

## 2. Durable route ownership

- [ ] 2.1 Add a forward-compatible Alembic migration for nullable `runtime_route`, backfill existing rows to `legacy`, then enforce the allowed values.
- [ ] 2.2 Extend `DurableRunRecord`, `StoredDurableRun` and repository operations to persist and retrieve route ownership.
- [ ] 2.3 Implement deterministic percentage/allowlist selection using authenticated scope and idempotency key, with route-policy version and reason.
- [ ] 2.4 Make every runtime gateway operation resolve the persisted route before constructing its upstream client; reject null/unknown route ownership.
- [ ] 2.5 Prove duplicate start, ambiguous upstream timeout and retry never create a cross-route duplicate Run.

## 3. Rollout and rollback

- [ ] 3.1 Add rollout validation for `0% -> 1% -> 10% -> 50% -> 100%` and explicit tenant/project/Agent targeting.
- [ ] 3.2 Add immediate rollback that affects only new assignments and preserves existing Run/Event/Checkpoint facts.
- [ ] 3.3 Add route decision, route-policy version, upstream latency, error and rollback metrics plus structured logs without secrets or prompt content.

## 4. Verification and handoff

- [ ] 4.1 Run platform-api unit, migration, gateway and shortest-chain tests with the GraphHarbor acceptance endpoint configured at `0%`.
- [ ] 4.2 Run isolated two-upstream acceptance through platform-api and verify route ownership across state, stream, command, join, cancel and delete.
- [ ] 4.3 Exercise rollout and rollback stages and record latency, error rate, queue lag and durable fact counts.
- [ ] 4.4 Update `verification.md` with owner review, evidence, uncovered boundaries and disposition.
- [ ] 4.5 Obtain owner approval before `/opsx:apply`; after acceptance, sync specs and archive the change.
