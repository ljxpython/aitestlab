## Context

The affected behavior is owned by `apps/platform-api` but crosses its request-context, IAM, identity, users, service-accounts, operations, and audit modules. The current implementation has five trust-boundary problems: privileged roles are treated like ordinary writable fields, request headers can construct an actor before authentication, the IAM super-admin shortcut runs before scope classification, execution-only operation metadata is returned publicly, and login audit has no authenticated actor. Response-body audit capture must also remain bounded without consuming file or streaming iterators.

The permission, audit, and operations leaf standards are authoritative. No schema migration, new dependency, trusted proxy, or cross-service protocol change is required.

## Goals / Non-Goals

**Goals:**

- Enforce protected-principal changes at shared application-service and IAM boundaries.
- Make verified token/API-key authentication the only source of actor identity and roles.
- Preserve project membership checks for every project-scoped permission.
- Keep execution snapshots available to workers but absent from public operation views.
- Give successful login events an explicit audit actor.
- Audit useful bounded JSON payloads without buffering files or streams.
- Lock each security and stability boundary with focused regression tests.

**Non-Goals:**

- Add trusted-proxy/header authentication or change tenant/project routing headers.
- Replace the policy engine, audit schema, operation metadata storage, or role catalog.
- Add password-complexity rules beyond the existing eight-character minimum.
- Change platform-web UI or add dependencies, migrations, feature flags, or rollout machinery.

## Decisions

### 1. Classify permission scope before applying super-admin privilege

`IamPolicyEngine.evaluate` will first classify the permission as platform, project, or unknown. The super-admin shortcut will apply only to registered platform permissions. Project permissions will always require `project_id` and a matching project role.

This keeps the fix in the shared policy path used by all callers. Adding project checks to individual services was rejected because sibling callers could still bypass the standard.

### 2. Protect super-admin role transitions with one explicit permission

Add a registered platform permission granted only to `platform_super_admin`. User and service-account services will require it whenever a create or update would add or remove that role. Ordinary writes that do not change the protected role continue to use their existing write permissions.

Creating a token for a service account that already carries `platform_super_admin` will require the same protected permission; otherwise an operator could obtain the privilege without changing the account. Scattering direct role checks in HTTP handlers was rejected because the permission standard requires handlers to delegate authorization.

### 3. Build request actors only from verified credentials

The base request context will retain request, tenant, and project routing data but initialize an anonymous actor. Authentication middleware will replace it only after validating a bearer token or service-account API key and loading current roles from repositories. With `auth_required=false` and no credential, requests continue through as anonymous and protected policy checks deny them.

Supporting client role headers through an implicit development mode was rejected. A future trusted-proxy mode would require its own authenticated contract and is outside this change.

### 4. Redact execution-only metadata at the operation view boundary

Persisted metadata remains unchanged because workers reconstruct the submitter actor from it. The shared conversion from stored operation to public `OperationView` will copy metadata and remove `actor_snapshot`. This covers list, detail, mutation, and watch responses that reuse the view mapper without changing worker storage.

Moving the snapshot to a new database column was rejected because response-boundary redaction closes the disclosure without a migration.

### 5. Pass login identity explicitly to audit middleware

After a successful login, the identity HTTP endpoint will attach the authenticated user identity to request-local audit state. Audit middleware will prefer that explicit audit actor for the event while the public authentication route remains public. Tokens and passwords will not be attached or logged.

Re-authenticating the newly issued token inside middleware was rejected as duplicate work and unnecessary credential handling.

### 6. Capture only bounded JSON responses

Audit middleware will consume and rebuild a response body only when the response is JSON and its declared content length is present and below a small fixed cap. File responses, SSE, generic streaming responses, JSON streams without a declared bound, and oversized JSON will keep their iterators untouched; audit records only available headers and length.

The current `StreamingResponse` bypass already avoids the reported file/stream buffering on this worktree, but focused tests are required because Starlette middleware can wrap ordinary responses as streaming responses. Buffering every non-SSE response and adding a configurable capture subsystem were both rejected.

### 7. Reuse the established password minimum

The user-create contract will use `min_length=8`, matching update/reset behavior. Login input remains `min_length=1` because it validates credentials rather than establishes a password.

## Risks / Trade-offs

- [Existing automation relies on unauthenticated role headers] -> Document the compatibility break; callers must use a verified token or API key.
- [Super administrators currently operate projects without membership] -> Deny after deployment; explicitly provision project membership before rollout where needed.
- [Response metadata contains future internal keys] -> This change removes the known sensitive actor snapshot at the shared view mapper; add keys to the same private-key filter when execution-only metadata is introduced.
- [A JSON response lacks content length] -> Skip payload capture rather than risk unbounded buffering; core audit fields still record the request outcome.
- [Middleware response wrapping obscures concrete response classes] -> Verify behavior using actual ASGI requests with file, streaming, SSE, bounded JSON, and oversized/unbounded JSON responses.

## Migration Plan

1. Before deployment, identify clients using unauthenticated identity headers and super-admin workflows lacking project membership.
2. Deploy the code-only change; no database migration is required.
3. Monitor authorization denials, login audit actor population, and response memory/latency.
4. Roll back the application version if compatibility impact is unacceptable. Rollback restores the known security exposures and is not an acceptable steady state.

## Open Questions

- Owner review must confirm the intentional compatibility breaks for header-based development access and super-admin project access.
