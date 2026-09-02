## ADDED Requirements

### Requirement: Runtime SHALL persist and recover durable runs through Agent Server

Runtime Service SHALL use Agent Server native Thread, Run and Checkpoint lifecycle with
`durability="sync"`. A resumed Run MUST use the original `thread_id` and a valid checkpoint or
interrupt resume input; Runtime MUST NOT create a second persistence state machine.

#### Scenario: Sync checkpoint survives worker restart
- **WHEN** a Run reaches a persisted super-step and its Worker is terminated
- **THEN** a new Worker resumes from the latest valid checkpoint with the same `thread_id` and reaches one terminal state

#### Scenario: Invalid checkpoint is rejected
- **WHEN** a resume request names a missing, foreign, or malformed checkpoint
- **THEN** the Runtime returns a stable recovery error and does not execute with another Thread's state

### Requirement: Runtime SHALL support precise interrupt and resume semantics

An interrupt MUST expose enough Run/checkpoint identity for a caller to resume the same execution
scope. Multiple interrupts MUST be resumed in order, and a client disconnect MUST NOT implicitly resume
or cancel the Run.

#### Scenario: Resume after interrupt
- **WHEN** a Run interrupts and the caller submits valid resume input for the same Thread
- **THEN** execution continues from the recorded interrupt boundary and emits a single terminal event

#### Scenario: Repeated interrupt remains ordered
- **WHEN** the graph interrupts more than once before completion
- **THEN** each resume advances the same Run in order without skipping or replaying a prior checkpoint

### Requirement: Runtime SHALL provide resumable and deduplicated event streams

The Runtime event stream SHALL expose a monotonic per-Run cursor. A reconnect MAY provide `since` to
replay events; consumers MUST deduplicate by `(run_id, seq)`. Stream closure MUST NOT change Run state.

#### Scenario: SSE reconnect replays missing events
- **WHEN** an SSE connection closes after cursor `n` and the client reconnects with `since=n`
- **THEN** the service sends later retained events in order and does not duplicate already acknowledged events

#### Scenario: Cursor is outside retention
- **WHEN** a reconnect requests an expired cursor
- **THEN** the service returns an explicit cursor-expired result and directs the caller to Run snapshot recovery

### Requirement: Runtime SHALL converge cancellation and failures to one terminal state

Cancel, timeout, Tool failure, graceful drain, and hard shutdown SHALL each produce a deterministic
terminal outcome. Exactly one terminal event is allowed per Run, and no ordinary event may follow it.

#### Scenario: Client disconnect does not cancel
- **WHEN** the SSE observer disconnects while the Run is still executing
- **THEN** the Run remains active or completes according to execution, and can be observed again by replay or snapshot

#### Scenario: Cancel wins before completion
- **WHEN** a valid cancel reaches an active Run before its terminal transition
- **THEN** the Run becomes cancelled exactly once and subsequent cancel requests are idempotent

#### Scenario: Tool failure is terminal when unrecoverable
- **WHEN** a Tool fails without an allowed retry and the graph cannot continue
- **THEN** the Run becomes failed with a stable error category and no success terminal event

### Requirement: Thread-scoped resources SHALL remain isolated and recoverable

Any Backend, Workspace, MCP client, or Sandbox attached to a Thread MUST be selected from serialized,
validated Thread facts and MUST fail closed when reconnecting. A resource failure MUST NOT fall back to
another Thread or a host directory.

#### Scenario: Two Threads do not share Workspace state
- **WHEN** two Threads run concurrently with different resource identifiers
- **THEN** each Run reads and writes only its own resource scope

#### Scenario: Resource reconnect fails closed
- **WHEN** a Worker restarts and the recorded Thread resource cannot be reopened
- **THEN** the Run fails with a resource recovery error and no alternate resource is used

### Requirement: Runtime SHALL expose a Platform-independent durable smoke path

The Runtime repository SHALL provide a local smoke path using a test-only Delegation Token signer,
real Agent Server, and isolated PostgreSQL/Redis. The path MUST exercise Auth, Resolver, Graph,
Checkpoint, Stream, and terminal state without calling Platform API.

#### Scenario: Local smoke executes a real durable run
- **WHEN** the smoke environment is started with valid local test secrets
- **THEN** it creates a Thread, runs `reference_agent`, reconnects its stream, and verifies the final Run snapshot

#### Scenario: Missing infrastructure is reported explicitly
- **WHEN** PostgreSQL, Redis, Worker, or required test configuration is unavailable
- **THEN** the durable test is marked not executed or failed with a clear prerequisite error and never reported as passed

### Requirement: Runtime SHALL support explicit external infrastructure deployment

The Runtime deployment SHALL provide a host-infra mode that starts only API, Worker, and migration
containers. It MUST not declare PostgreSQL or Redis services, volumes, or `depends_on` edges, and API,
Worker, and migration MUST use the same explicitly configured external `DATABASE_URI` and `REDIS_URI`.

#### Scenario: Host-infra compose uses registered services
- **WHEN** host-infra deployment is rendered with valid external PostgreSQL and Redis URIs
- **THEN** only Runtime containers are declared and all three roles receive the same external endpoints

#### Scenario: Host-infra compose rejects implicit infrastructure
- **WHEN** the host-infra compose is inspected
- **THEN** no PostgreSQL/Redis service, data volume, or infrastructure dependency is present

### Requirement: RuntimeContext SHALL use one strict producer/consumer contract

The API producer and Worker consumer MUST agree on the exact signed RuntimeContext envelope schema,
including required identity, scope, run/thread binding, expiry, issuer/audience, and policy fields when
production requires them. Unknown top-level or nested claims MUST fail closed; Runtime-specific context
fields MUST remain outside GraphHarbor's generic envelope contract.

#### Scenario: Valid context crosses the Worker boundary
- **WHEN** API signs a context and a Worker verifies it for the same Run and Thread
- **THEN** the Worker receives the same normalized identity, scope, and policy facts

#### Scenario: Unknown context claim is rejected
- **WHEN** an envelope contains an unrecognized top-level or nested claim
- **THEN** verification returns a stable context error and the Run is not executed

### Requirement: Agent Server SHALL recover on same-port API restart

After an API process receives SIGTERM, it MUST exit within the configured grace period and a replacement
process MUST be able to bind the same explicitly requested host/port within a bounded readiness timeout.
The CLI MUST NOT silently substitute a random port for an explicitly requested port.

#### Scenario: API restarts on the requested port
- **WHEN** a ready API is terminated with SIGTERM and started again with the same host and port
- **THEN** the replacement serves `/ready` on that same port within the acceptance timeout

#### Scenario: Port conflict is explicit
- **WHEN** an explicitly requested port is still owned by another process
- **THEN** startup fails with a clear bind error rather than advertising a different port

### Requirement: Generic observability SHALL preserve correlation and fail soft

GraphHarbor MUST preserve generic `request_id`, `run_id`, `thread_id`, and `graph_id` correlation fields
across API, queue, Worker, and emitted events when supplied by the Runtime contract. A telemetry exporter
failure or bounded queue saturation MUST NOT block or change Run execution, and dropped telemetry MUST be
observable through a stable metric or log signal.

#### Scenario: Correlation survives Worker execution
- **WHEN** a correlated Run is queued and executed by another Worker
- **THEN** the generic correlation fields remain available on the Worker trace/event boundary

#### Scenario: Exporter failure does not fail the Run
- **WHEN** the configured telemetry exporter rejects data or its bounded queue is full
- **THEN** the Run remains available and terminal state is unchanged while a drop signal is emitted
