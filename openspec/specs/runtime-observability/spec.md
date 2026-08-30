# runtime-observability Specification

## Purpose

定义 Runtime Service 的 Langfuse Trace、结构化诊断、脱敏和 fail-soft 边界。

## Requirements

### Requirement: Langfuse must be explicitly enabled and lifecycle-scoped

Runtime Service SHALL keep Langfuse disabled unless `LANGFUSE_ENABLED=true`. When explicitly enabled, the service MUST validate `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` during lifespan initialization, initialize one process-scoped client, and perform one bounded flush at shutdown.

#### Scenario: Langfuse is disabled by default
- **WHEN** `LANGFUSE_ENABLED` is absent, false, or any value other than case-insensitive `true`
- **THEN** Runtime Service does not import or initialize the Langfuse SDK and Agent execution is unchanged

#### Scenario: Explicit enablement has incomplete configuration
- **WHEN** `LANGFUSE_ENABLED=true` and a required Langfuse setting is missing
- **THEN** lifespan initialization fails with a stable configuration error before serving Runs

#### Scenario: Shutdown flush exceeds its bound
- **WHEN** the process is shutting down and Langfuse flush does not complete within the configured bound
- **THEN** Runtime Service emits a structured warning and completes shutdown without waiting indefinitely

### Requirement: Graph entrypoints must merge per-run Langfuse callbacks safely

The Runtime observability adapter SHALL bind one Langfuse Callback to each Graph invocation at the `get_agent(config)` return boundary. It MUST preserve and merge caller callbacks, metadata, and tags; trusted Runtime metadata takes precedence over conflicting untrusted values. The adapter MUST NOT create or choose the Graph, Model, Tool, Backend, Skill, or Subagent.

#### Scenario: Existing RunnableConfig values are preserved
- **WHEN** a caller supplies callbacks, metadata, and tags to `get_agent(config)`
- **THEN** the returned Graph contains the caller values plus the Langfuse callback and approved metadata/tags

#### Scenario: Concurrent Runs use isolated callbacks
- **WHEN** two Runs execute concurrently with different `run_id`, `thread_id`, or principals
- **THEN** each Run has isolated callback state and its Trace metadata is not visible in the other Run

#### Scenario: Runtime metadata conflicts with caller metadata
- **WHEN** caller metadata contains a different value for a trusted Runtime field
- **THEN** the trusted resolved value is retained and the caller cannot overwrite it

### Requirement: Traces must use a bounded metadata allowlist

Runtime Service SHALL map `thread_id` to Langfuse session, one Graph invocation to one Trace, and `RuntimePrincipal.user_id` to the Trace user. It MUST allow only approved correlation, resolved-config, and low-cardinality tag fields and MUST reject credentials, identity guesses from untrusted config, full prompt/response content, and unbounded Tool payloads.

#### Scenario: Runtime principal is associated after resolution
- **WHEN** Auth and Runtime resolver produce a valid `RuntimePrincipal` and `ResolvedRuntimeConfig`
- **THEN** the Trace may contain the principal and safe config hash/version summary

#### Scenario: Untrusted config contains identity fields
- **WHEN** ordinary `RunnableConfig.metadata` or `configurable` contains user, tenant, or project identity
- **THEN** those values are ignored for Trace identity and do not grant any authorization

#### Scenario: Sensitive payload reaches the callback boundary
- **WHEN** callback input contains a recognized token, cookie, authorization header, or secret key
- **THEN** the value is redacted or the full payload is dropped before export

### Requirement: Observability failures must be fail-soft

Langfuse initialization after valid configuration, exporter network failures, queue saturation, callback exceptions, and bounded flush failures MUST NOT change Agent input, output, cancellation, interrupt, timeout, or original exception semantics. Runtime Service SHALL emit a structured warning and increment a diagnostic counter for observable exporter failures.

#### Scenario: Langfuse endpoint is unavailable during a Run
- **WHEN** a Model or Tool executes while the Langfuse endpoint is unavailable
- **THEN** the Agent Run continues with its original result or error and Runtime logs the export failure

#### Scenario: Export queue is full
- **WHEN** the bounded exporter queue cannot accept a Trace event
- **THEN** the event is dropped, a drop metric is incremented, and the Agent execution is not blocked

#### Scenario: Agent fails while Langfuse also fails
- **WHEN** the Agent raises an original Model, Tool, interrupt, cancel, or timeout error and Langfuse reports an error
- **THEN** the caller receives the original Agent error and not an observability exception

### Requirement: Runtime observability must expose minimal diagnostic signals

Runtime Service SHALL emit structured events and counters for Run success, failure, timeout, cancellation, Tool error, Langfuse export failure, dropped event, and total duration. Signals MUST contain identifiers and bounded metadata only, never credentials or full content.

#### Scenario: Run completes successfully
- **WHEN** a Graph invocation reaches a successful terminal state
- **THEN** logs and metrics include graph, run, thread, status, and duration without prompt or response bodies

#### Scenario: Tool fails
- **WHEN** a Tool invocation raises an exception
- **THEN** the diagnostic signal includes the Tool name and stable error category without full arguments or result
