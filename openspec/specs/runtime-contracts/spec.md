# runtime-contracts Specification

## Purpose
TBD - created by archiving change runtime-service-r1-contracts-auth-modeling. Update Purpose after archive.
## Requirements
### Requirement: Runtime 合同类型必须不可变且字段明确
Runtime SHALL provide `RuntimePrincipal`, `RuntimeContext`, `RuntimePolicy`, `AgentDefaults` and `ResolvedRuntimeConfig` as immutable typed values. Boundary parsers MUST reject unknown fields, identity fields in context, invalid primitive types, duplicate names and out-of-range generation parameters.

#### Scenario: 合法合同值保持不可变
- **WHEN** caller constructs valid Runtime values and attempts to mutate a field
- **THEN** mutation fails and the original value remains unchanged

#### Scenario: Context 拒绝未知和身份字段
- **WHEN** boundary parser receives `user_id`, `token`, or an undeclared field in RuntimeContext
- **THEN** it raises a stable context error and does not construct a permissive value

### Requirement: Resolver 必须纯函数决议有效运行配置
`resolve_runtime_config` MUST validate all inputs, merge Context over AgentDefaults, enforce RuntimePolicy allowlists, preserve explicit zero/empty values, and return a deterministic `config_hash` without I/O or input mutation.

#### Scenario: Context 覆盖默认值
- **WHEN** Context provides `model_id` or generation parameters
- **THEN** the resolved value uses that explicit value, including `temperature=0`

#### Scenario: 缺省值和 Optional Tool 语义
- **WHEN** Context has `tools=None`
- **THEN** Optional Tools inherit from AgentDefaults
- **WHEN** Context has `tools=()`
- **THEN** all Optional Tools are disabled while Required Tools remain

#### Scenario: 越权模型或工具被拒绝
- **WHEN** selected model or Required/Optional Tool is absent from declarations or Policy allowlists
- **THEN** Resolver fails closed with a stable error code and no partial config

#### Scenario: 等价输入产生稳定 hash
- **WHEN** equivalent normalized inputs are resolved more than once
- **THEN** `prompt_hash` and `config_hash` are identical and contain no secret or full Prompt

### Requirement: Delegation JWT 必须生成可信 Principal 和 Policy
Runtime SHALL verify a short-lived Delegation JWT with explicit algorithm, issuer, audience and required claims, then construct `RuntimePrincipal` and `RuntimePolicy`. Invalid signature, expiry, scope, claim type or policy type MUST fail closed.

#### Scenario: 合法 Delegation JWT
- **WHEN** token contains `type=runtime_delegation`, valid time claims, matching scope and allowlists
- **THEN** verification returns the expected Principal and Policy values

#### Scenario: JWT 签名或时间无效
- **WHEN** token signature is invalid or the token is expired/not-yet-valid
- **THEN** verification raises `runtime.auth.invalid_token` without exposing token contents

#### Scenario: JWT scope 与身份不一致
- **WHEN** policy claims use tenant/project values different from the Principal scope
- **THEN** verification fails with `runtime.auth.invalid_principal`

### Requirement: Modeling 只能从已决议配置创建模型
`build_model` MUST accept only `ResolvedRuntimeConfig`, use an explicit provider/model mapping, read provider credentials from Runtime environment or an injected secret mapping, and map initialization failures to a stable Runtime error. It MUST NOT accept raw Context or `RunnableConfig`.

#### Scenario: DeepSeek 中转模型初始化
- **WHEN** resolved model ID uses `deepseek:<model>` and required DeepSeek settings exist
- **THEN** Modeling constructs a `ChatDeepSeek` with the resolved generation parameters and proxy settings

#### Scenario: OpenAI/GPT 中转模型初始化
- **WHEN** resolved model ID uses `openai:<model>` and required GPT settings exist
- **THEN** Modeling constructs a `ChatOpenAI` with the resolved generation parameters and proxy settings

#### Scenario: Provider 配置缺失或初始化失败
- **WHEN** required credentials are absent or the provider rejects initialization
- **THEN** Modeling raises `runtime.model.initialization_failed` and never falls back to a fake model

### Requirement: Runtime Config 适配必须保持边界清晰
The Runtime Config adapter MUST parse only the explicit runtime context supplied by the caller and delegate authorization and default merging to the Resolver. It MUST NOT read legacy configuration fields or mutate `RunnableConfig`.

#### Scenario: 新 Context 解析
- **WHEN** adapter receives a mapping under the new Context boundary
- **THEN** it returns a validated `RuntimeContext` or the same stable context error as the parser

#### Scenario: 旧配置字段拒绝
- **WHEN** adapter receives `platform_runtime`, `enable_tools`, or identity fields
- **THEN** it rejects the input instead of applying compatibility fallback

