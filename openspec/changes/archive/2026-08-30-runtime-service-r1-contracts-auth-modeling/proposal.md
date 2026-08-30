## Why

R0 已经建立了可启动的 Runtime Service，但运行请求仍没有统一的 Context、Policy、身份和模型决议边界。现在进入 R1，需要把一次 Run 的输入严格收敛为可审计的不可变配置，并让 Runtime 在不依赖 Platform API 的情况下完成认证和模型初始化。

## What Changes

- **BREAKING**：在 `src/runtime_service/runtime/` 新增不可变的 Runtime 合同类型，不接受旧 `platform_runtime` 或未声明字段。
- 新增纯函数 Resolver，完成 Context/Policy/Defaults 校验、默认值合并、Tool allowlist 检查和 `config_hash` 生成。
- 新增 Runtime Delegation JWT 验证，将可信 claims 映射为 `RuntimePrincipal` 和 `RuntimePolicy`。
- 新增明确的 Runtime 错误码和安全错误摘要，不暴露 token、secret 或完整 Prompt。
- 新增 `modeling.py`，只接收 `ResolvedRuntimeConfig`，通过 LangChain `init_chat_model` 创建 ChatModel，并将 Provider 初始化失败映射为稳定错误。
- 新增 `runtime_config.py` 的最小运行时适配函数，为后续 Middleware 注入 Resolver 结果；本阶段不改造 R0 Graph。
- 增加 contracts、auth、resolver、modeling 的单元测试和真实 LangChain 初始化边界测试，不启动 Platform API。

## Capabilities

### New Capabilities

- `runtime-contracts`: 定义 RuntimeContext、RuntimePrincipal、RuntimePolicy、AgentDefaults、ResolvedRuntimeConfig、Resolver、Auth 和 Modeling 的最小行为契约。

### Modified Capabilities

无。R0 的 Graph/Service 边界保持不变，R1 能力通过新的 Runtime 包提供给后续 Service 和 Middleware 使用。

## Impact

- 影响 `apps/runtime-service/src/runtime_service/runtime/`、`apps/runtime-service/tests/runtime/` 和 R1 OpenSpec 主规格。
- 复用现有 `pyjwt`、`langchain`、`langchain-openai` 依赖，不新增公共 Builder、Factory、Registry 或 Provider 插件层。
- 当前不修改 `apps/platform-api`，不接入真实 Gateway；本地 Auth 测试使用专用测试密钥和最小 claims。
- R1 完成后，R0 Graph 仍可在无凭据环境中启动；R2 再把 RuntimeContext 接入 Agent Service。
