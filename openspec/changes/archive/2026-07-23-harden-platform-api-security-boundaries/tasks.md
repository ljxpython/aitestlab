## 1. Pre-apply Gate

- [x] 1.1 Record owner review as `Approved` or an explicitly authorized `Waived` decision in `verification.md` before changing application code.
- [x] 1.2 Add focused failing regression tests for protected role transitions and credential issuance, optional-auth header forgery, super-admin project-scope enforcement, operation metadata redaction, login audit actor attribution, bounded audit response capture, and user-create password length.

## 2. Authorization and Actor Trust

- [x] 2.1 Classify permission scope before the platform super-admin shortcut so every project permission requires project scope and an allowed project role.
- [x] 2.2 Add one super-admin-only permission and require it for user and service-account super-admin role transitions and super-admin service-account token issuance.
- [x] 2.3 Initialize request contexts with an anonymous actor and populate identity and roles only after bearer-token or API-key verification.

## 3. Privacy, Audit, and Validation

- [x] 3.1 Redact `actor_snapshot` in the shared stored-operation-to-public-view conversion while preserving stored execution metadata.
- [x] 3.2 Pass the successful login principal through request-local audit state and use it as the audit actor without exposing credentials.
- [x] 3.3 Restrict audit payload capture to declared, bounded JSON bodies and preserve file, SSE, generic streaming, unbounded JSON, and oversized JSON response iterators.
- [x] 3.4 Set the user-create password minimum to eight characters, matching administrative reset behavior.

## 4. Verification and Acceptance

- [x] 4.1 Run the focused authorization, identity, audit, operation, service-account, and user contract tests and record commands, inputs, and results in `verification.md`.
- [x] 4.2 Run the complete `apps/platform-api/tests` unittest suite as the shortest affected chain and record results and uncovered boundaries.
- [x] 4.3 Run OpenSpec validation and `graphify update .`; record validation results and graph update status.
- [x] 4.4 Review docs and runbook impact, update current standards or operator guidance only if implementation changes their stated contract, and record the decision.
- [x] 4.5 Record residual risks and owner acceptance disposition in `verification.md`; after acceptance, sync the new capability spec before archive.
