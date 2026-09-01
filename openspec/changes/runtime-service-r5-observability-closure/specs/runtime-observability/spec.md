## MODIFIED Requirements

### Requirement: Langfuse must be explicitly enabled and lifecycle-scoped

Runtime Service SHALL keep Langfuse disabled unless `LANGFUSE_ENABLED=true`. When explicitly enabled,
the Agent Server application lifespan MUST validate `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and
`LANGFUSE_BASE_URL` before serving Runs, initialize one process-scoped client, and perform one bounded
flush at shutdown. A direct Graph entrypoint MUST NOT create a second process client when the lifespan
has already initialized one.

#### Scenario: Langfuse is disabled by default
- **WHEN** `LANGFUSE_ENABLED` is absent, false, or any value other than case-insensitive `true`
- **THEN** Runtime Service does not import or initialize the Langfuse SDK and Agent execution is unchanged

#### Scenario: Explicit enablement has incomplete configuration
- **WHEN** `LANGFUSE_ENABLED=true` and a required Langfuse setting is missing
- **THEN** lifespan initialization fails with stable `LangfuseConfigurationError` semantics before serving Runs

#### Scenario: Lifespan owns one process client
- **WHEN** the application starts with valid Langfuse settings and multiple Graph entries are loaded
- **THEN** startup initializes one client, Graph entrypoints reuse it, and no per-Run process client is created

#### Scenario: Shutdown flush exceeds its bound
- **WHEN** the process is shutting down and Langfuse flush does not complete within the configured bound
- **THEN** Runtime Service emits a structured warning and completes shutdown without waiting indefinitely

### Requirement: Graph entrypoints must merge per-run Langfuse callbacks safely

The Runtime observability adapter SHALL bind one Langfuse Callback to each Graph invocation at the
`get_agent(config)` return boundary. It MUST preserve caller callbacks, preserve only allowlisted caller
metadata and low-cardinality tags, and make trusted Runtime metadata take precedence over conflicting
untrusted values. The adapter MUST NOT create or choose the Graph, Model, Tool, Backend, Skill, or
Subagent, and callback binding MUST NOT change the Graph topology or business Runtime resolution.

#### Scenario: Existing RunnableConfig values are safely preserved
- **WHEN** a caller supplies callbacks, approved metadata, and approved tags to `get_agent(config)`
- **THEN** the returned Graph contains the caller callbacks plus the Langfuse and diagnostics callbacks,
  retains approved values, and drops unknown metadata or high-cardinality tags

#### Scenario: Concurrent Runs use isolated callbacks
- **WHEN** two Runs execute concurrently with different `run_id`, `thread_id`, or principals
- **THEN** each Run has isolated callback state and its Trace metadata is not visible in the other Run

#### Scenario: Runtime metadata conflicts with caller metadata
- **WHEN** caller metadata contains a different value for a trusted Runtime field
- **THEN** the trusted resolved value is retained and the caller cannot overwrite it

### Requirement: Traces must use a bounded metadata allowlist

Runtime Service SHALL map `thread_id` to Langfuse session, one Graph invocation to one Trace, and
`RuntimePrincipal.user_id` to the Trace user. It MUST allow only approved correlation, resolved-config,
and low-cardinality tag fields. `user_id`, `tenant_id`, `project_id`, `model_id`, policy fields and
configuration hashes MUST come only from trusted Auth/Resolver output. It MUST reject credentials,
identity guesses from untrusted config, full prompt/response content, and unbounded Tool payloads.

#### Scenario: Runtime principal is associated after resolution
- **WHEN** Auth and Runtime resolver produce a valid `RuntimePrincipal` and `ResolvedRuntimeConfig`
- **THEN** the Trace may contain the principal and safe config hash/version summary, with `user_id` derived
  only from the trusted principal

#### Scenario: Untrusted config contains identity fields
- **WHEN** ordinary `RunnableConfig.metadata` or `configurable` contains user, tenant, or project identity
  without trusted Runtime metadata
- **THEN** those values are ignored for Trace identity and do not grant any authorization

#### Scenario: Sensitive payload reaches the callback boundary
- **WHEN** callback input contains a recognized token, cookie, authorization header, or secret key
- **THEN** the value is redacted or the full payload is dropped before export

#### Scenario: Tool payload exceeds the bounded summary
- **WHEN** a Tool input or result is larger than the configured safe summary bound
- **THEN** the full payload is dropped and only a bounded tool name/error category summary remains

### Requirement: Observability failures must be fail-soft

After valid startup configuration, Langfuse exporter network failures, bounded queue saturation,
callback exceptions, and bounded flush failures MUST NOT change Agent input, output, cancellation,
interrupt, timeout, or original exception semantics. Runtime Service SHALL emit a structured warning and
increment a diagnostic counter for each observable exporter failure or dropped event. Invalid explicit
startup configuration remains fail-closed as defined above.

#### Scenario: Langfuse endpoint is unavailable during a Run
- **WHEN** a Model or Tool executes while the Langfuse endpoint is unavailable
- **THEN** the Agent Run continues with its original result or error and Runtime logs the export failure

#### Scenario: Export queue is full
- **WHEN** the bounded exporter queue cannot accept a Trace event
- **THEN** the event is dropped, a drop metric is incremented, and the Agent execution is not blocked

#### Scenario: Agent fails while Langfuse also fails
- **WHEN** the Agent raises an original Model, Tool, interrupt, cancel, or timeout error and Langfuse reports an error
- **THEN** the caller receives the original Agent error and not an observability exception

#### Scenario: Flush fails during shutdown
- **WHEN** the process shutdown flush raises or exceeds its timeout
- **THEN** Runtime records `flush_error` or `flush_timeout`, logs a bounded warning, and allows shutdown to complete

### Requirement: Runtime observability must expose minimal diagnostic signals

Runtime Service SHALL emit structured events and counters for Run success, failure, timeout, cancellation,
Tool error, Langfuse export failure, dropped event, token usage, and total duration. Signals MUST contain
`graph_id`, `run_id`, `thread_id`, and `request_id` when available, plus bounded status/duration/error
fields, and never credentials or full content. The metrics snapshot contract MUST expose stable counter
names for local and deployment diagnostics without adding a second Run state machine.

#### Scenario: Run completes successfully
- **WHEN** a Graph invocation reaches a successful terminal state
- **THEN** logs and metrics include graph, run, thread, request, status, and duration without prompt or response bodies

#### Scenario: Tool fails
- **WHEN** a Tool invocation raises an exception
- **THEN** the diagnostic signal includes the Tool name and stable error category without full arguments or result

#### Scenario: Run is cancelled or times out
- **WHEN** a Graph invocation ends with cancellation or timeout
- **THEN** the diagnostic signal records `cancelled` or `timeout`, its bounded duration, and the same available identifiers

#### Scenario: Exporter drops or fails an event
- **WHEN** the exporter reports a callback error, endpoint error, queue drop, or flush failure
- **THEN** the corresponding stable counter increments and the structured signal contains no secret or full payload
