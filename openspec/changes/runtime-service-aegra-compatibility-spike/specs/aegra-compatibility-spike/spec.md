## ADDED Requirements

### Requirement: Aegra SHALL load the canonical Runtime Agent entry

The Spike SHALL register the existing Runtime Agent export and prove that Aegra invokes
`async def get_agent(config: RunnableConfig) -> Pregel` with the actual per-Run configuration.
The Spike SHALL NOT require a second Agent entry point or a production Runtime code change.

#### Scenario: Async factory receives per-Run config

- **WHEN** a Run is submitted with a unique model and trace metadata configuration
- **THEN** the canonical `get_agent(config)` export is invoked with that configuration and returns an executable `Pregel`

#### Scenario: Invalid graph export is rejected

- **WHEN** the configured export is missing, returns a non-Graph value, or has an unsupported signature
- **THEN** Aegra fails the load or Run with a diagnosable error and does not execute a partial Run

### Requirement: The Spike SHALL prove durable persistence and recovery

The Spike SHALL use real PostgreSQL and Redis services and SHALL verify Checkpoint persistence,
worker lease recovery, graceful handoff, and final Run convergence.

#### Scenario: Checkpoint resumes after worker restart

- **WHEN** a worker is terminated after a checkpoint and the same Run is re-enqueued
- **THEN** another worker resumes from the latest checkpoint and produces one terminal result

#### Scenario: Duplicate completion is idempotent

- **WHEN** a delayed worker attempts to finalize a Run that is already terminal
- **THEN** the persisted terminal state remains unchanged and no duplicate terminal event is accepted

### Requirement: The Spike SHALL prove stream replay and HITL semantics

The Spike SHALL verify SSE replay, event ordering, interrupt/resume, cancellation, and reconnect
behavior using the real Aegra server and SDK-compatible protocol.

#### Scenario: SSE reconnect replays missing events

- **WHEN** the client disconnects after event sequence `N` and reconnects with the last event ID
- **THEN** the server delivers events after `N` in order without counting duplicate events twice

#### Scenario: HITL interrupt resumes the same Run contract

- **WHEN** the Agent interrupts for approval and the client submits a valid resume command
- **THEN** the Run transitions through the documented states and completes with ordered interrupt and resume events

### Requirement: Workspace, Backend, and Subagent access SHALL be isolated

The Spike SHALL execute at least two Threads and, where available, a DeepAgent fixture to prove
that workspace files, Backend state, tools, skills, and Subagent namespaces cannot cross Thread or
permission boundaries, including after worker handoff.

#### Scenario: Thread workspaces do not cross-read

- **WHEN** Thread A writes a marker file and Thread B attempts to read it
- **THEN** Thread B cannot observe or modify Thread A's marker

#### Scenario: Subagent receives only delegated capabilities

- **WHEN** a parent Agent invokes a Subagent with a restricted tool set
- **THEN** the Subagent cannot call tools or access workspace paths outside the delegated policy

### Requirement: RuntimeContext and authorization SHALL fail closed

The Spike SHALL send a signed or otherwise server-authorized RuntimeContext through the Platform
boundary fixture and verify identity, project, thread, run, model, tool policy, and trace metadata
at the Runtime boundary. Client overrides SHALL be rejected.

#### Scenario: Authorized context executes

- **WHEN** the request carries a valid context with an allowed model and tool policy
- **THEN** the Agent executes and the effective context is available in Run and Trace metadata

#### Scenario: Client attempts a protected override

- **WHEN** a client changes `thread_id`, `run_id`, model provider, tenant, or tool policy in the request body
- **THEN** the request is rejected or the server-authoritative value wins, and no unauthorized resource is touched

### Requirement: Langfuse observation SHALL be correlated without blocking execution

The Spike SHALL send traces to the configured Langfuse endpoint and SHALL verify correlation by
Platform Run ID, Runtime Run ID, Thread ID, Agent version, and model reference. Trace exporter
failure SHALL NOT change a successful or failed Run terminal state.

#### Scenario: Trace contains joinable identifiers

- **WHEN** a real model Run completes
- **THEN** the Langfuse trace contains the documented correlation metadata without credentials or prompt secrets being logged

#### Scenario: Langfuse is unavailable

- **WHEN** the trace exporter is unreachable or returns an error
- **THEN** the Run still reaches its correct terminal state and the failure is observable in service logs/metrics

### Requirement: Spike results SHALL be reproducible and shall not alter production defaults

The Spike SHALL pin the Aegra and LangGraph dependency versions, document commands and environment
requirements, redact secrets, and produce a pass/fail/blocked evidence report. It SHALL remain
opt-in and SHALL NOT replace the current R6 deployment automatically.

#### Scenario: Missing real dependency is reported as blocked

- **WHEN** required model, PostgreSQL, Redis, or Langfuse credentials are absent
- **THEN** the relevant check is marked `blocked` with the missing prerequisite and no fake success is emitted

#### Scenario: Production Runtime remains unchanged

- **WHEN** the Spike is installed or executed
- **THEN** the formal Runtime `pyproject.toml`, `langgraph.json`, and R6 Docker path remain unchanged unless a later replacement change is approved
