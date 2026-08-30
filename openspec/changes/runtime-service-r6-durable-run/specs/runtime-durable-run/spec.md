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
