## ADDED Requirements

### Requirement: Runtime route is selected for each new Run

`platform-api` SHALL select exactly one runtime route for every newly created runtime Run.
The route policy SHALL support an explicit GraphHarbor percentage from 0 through 100 and
optional Agent, tenant or project allowlists. With no matching rule, the default route SHALL
remain `legacy`.

#### Scenario: Default traffic stays on legacy

- **WHEN** the GraphHarbor route is disabled or its percentage is `0`
- **THEN** a new Run is sent to the legacy upstream and no GraphHarbor request is created

#### Scenario: Stable percentage selection

- **WHEN** a new Run matches a percentage policy
- **THEN** the gateway uses a deterministic hash of its authenticated scope and idempotency key
  to select either `legacy` or `graphharbor`, and retries of the same idempotent request keep the
  same route

#### Scenario: Explicit project allowlist

- **WHEN** a project is present in the GraphHarbor allowlist
- **THEN** a new Run for that project uses GraphHarbor regardless of the percentage, unless the
  route is disabled globally

### Requirement: Run route ownership is durable

The platform SHALL persist `runtime_route` before or atomically with upstream Run creation and
SHALL use that value for all later operations belonging to the Run, including state, history,
stream, command, join, cancel and delete.

#### Scenario: Route policy changes after Run creation

- **WHEN** the percentage or allowlist changes after a Run has started
- **THEN** requests for that Run continue to use its recorded upstream and are not rebalanced

#### Scenario: Duplicate start is idempotent

- **WHEN** the same project, thread and `Idempotency-Key` are submitted again
- **THEN** the gateway returns the existing durable Run and does not create a second upstream Run
  or change its recorded route

#### Scenario: Upstream response is ambiguous

- **WHEN** an upstream request times out after dispatch may have occurred
- **THEN** the gateway retries only the recorded route under the existing idempotency key and
  never silently creates a new Run on the other route

### Requirement: Rollback only affects new assignments

The gateway SHALL provide an immediate route rollback that disables new GraphHarbor assignments
without deleting or rewriting existing platform durable records or upstream facts.

#### Scenario: Rollback during rollout

- **WHEN** an operator disables GraphHarbor routing
- **THEN** new Runs use `legacy`, while existing GraphHarbor Runs retain their route and remain
  queryable, streamable and cancellable

#### Scenario: Rollback preserves facts

- **WHEN** rollback completes
- **THEN** no Run, Event, Checkpoint or idempotency record is deleted as part of route rollback

### Requirement: Route configuration is governed and observable

Route changes SHALL be permission-protected, validated to the supported rollout steps or an
explicit allowlisted scope, audited with actor, old value, new value and request id, and exposed
in the platform configuration snapshot and metrics without credentials.

#### Scenario: Unauthorized route change

- **WHEN** an actor without platform configuration write permission changes the route
- **THEN** the request is rejected and the active route policy remains unchanged

#### Scenario: Invalid route configuration

- **WHEN** a route URL is missing, a percentage is outside 0 through 100, or both upstreams are
  not distinct and reachable by configuration validation
- **THEN** the configuration is rejected before it can affect new Runs

#### Scenario: Route decision is diagnosable

- **WHEN** an operator inspects a Run or platform metrics
- **THEN** the recorded route, route-policy version, selection reason, upstream latency and
  rollback state are available without exposing JWTs, API keys or prompt content
