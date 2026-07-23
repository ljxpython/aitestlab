## Why

`platform-api` currently permits privilege escalation through user and service-account role changes, trusts client-supplied identity headers when authentication is optional, and lets a platform super administrator bypass project membership checks. Audit and operation responses also need tighter identity, privacy, and bounded-response guarantees.

## What Changes

- Require an existing platform super administrator to grant or revoke `platform_super_admin` on users or service accounts; ordinary operator write access remains valid for non-privileged roles.
- Treat unauthenticated requests as anonymous even when authentication enforcement is disabled; client identity and role headers no longer establish an actor.
- Apply project membership and project-role checks to every project-scoped permission, including platform super administrators.
- Exclude internal actor snapshots from operation list and detail responses while preserving them for execution.
- Record the authenticated user as the actor of a successful login audit event.
- Capture response bodies for audit only when they are bounded JSON responses; preserve file and streaming response iterators without buffering. The current all-streaming bypass is retained and locked with regression coverage.
- Enforce the same eight-character minimum for passwords supplied during user creation and administrative password reset.

## Capabilities

### New Capabilities

- `platform-api-security-boundaries`: Observable authorization, actor trust, audit safety, operation privacy, and password-validation requirements for the platform control plane.

### Modified Capabilities

None.

## Impact

- **Locus:** `apps/platform-api`.
- **Affected chain:** HTTP request context/authentication -> IAM policy and user/service-account services -> operation response mapping and audit middleware -> platform-api contract tests.
- **Band:** B3 Governed, because authentication, permission, audit, and data-disclosure semantics change.
- **Standards loaded:** `AGENTS.md`, `docs/standards/01-ai-execution-system.md`, `apps/platform-api/docs/standards/permission-standard.md`, `apps/platform-api/docs/standards/audit-standard.md`, and `apps/platform-api/docs/standards/operations-standard.md`.
- **Compatibility:** Operators that currently manage super-administrator roles and super administrators without explicit project membership will receive authorization failures. Requests that relied on client role headers while authentication was disabled will become anonymous.
- **Dependencies and migration:** No new dependency or database migration is expected. Rollback is a code rollback, but it would restore the reported security exposures.
- **Non-goals:** Changing the role catalog, adding trusted-proxy authentication, redesigning operation storage, changing password complexity beyond the existing minimum length, or altering unrelated platform-web behavior.
