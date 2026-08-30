## Context

R0 已把 Runtime Service 切换到 `src/runtime_service`，但 Agent 仍只能依赖 Service 内部默认值。R1 需要冻结一次 Run 的身份、策略、请求候选值、Service 默认值和模型初始化边界。该变更属于 runtime-service 单一 locus 的 B3 Governed Change，因为它定义认证、权限和跨服务可复用的运行时契约；Platform API 本阶段只作为未来调用方，不修改其业务代码。

## Goals / Non-Goals

**Goals:**

- 用标准库不可变 dataclass 表达五类 Runtime 类型。
- 用同步纯函数完成严格字段校验、默认值合并、Tool allowlist 检查和稳定 hash。
- 用 PyJWT 验证最小 Delegation JWT，并映射 Principal/Policy，不访问 Platform API。
- 用一个明确的 `build_model` 将已决议模型 ID 转换为 LangChain ChatModel，支持 DeepSeek/GPT 中转环境。
- 提供最小 `runtime_config.py` 适配入口，供后续 Middleware 读取 Context。

**Non-Goals:**

- 不修改 R0 Graph，不把 R1 能力偷偷接入 `reference_agent`。
- 不实现 Middleware 生命周期、Tool Registry、MCP、Backend、Checkpoint、Trace 或 Platform Gateway。
- 不接受旧 `platform_runtime`、`enable_tools`、身份字段或任意扩展字段。
- 不创建 Builder、Factory、Registry、Provider 插件或配置中心。

## Decisions

### 1. dataclass 作为内部和边界合同

五类类型使用 `@dataclass(frozen=True, slots=True)`；JSON/mapping 进入 Resolver 时先严格解析为类型。这样保留 LangGraph `Runtime.context` 的轻量传递能力，又不把 Pydantic 的宽松额外字段行为当作授权边界。

备选方案：直接使用 `dict[str, Any]` 会丢失字段和不可变性；全面引入 Pydantic 会扩大 R1 依赖和 schema 行为，留到确有 Agent Server schema 需求时再评估。

### 2. Resolver 是纯函数

`resolve_runtime_config(principal, context, policy, defaults)` 只做校验、规范化、合并和 hash。它不读取环境、不调用网络/数据库/Provider、不接收 `RunnableConfig`，所有输入保持不变。`tools=None` 继承 Optional Tools，空 tuple 表示显式关闭 Optional Tools；任何越权或未声明 Tool 直接拒绝。

### 3. Auth 只验证短期 JWT

`verify_delegation_token` 使用 PyJWT 显式算法、issuer、audience 和时间校验，要求 `type=runtime_delegation` 及 Principal/Policy 必填 claims。Auth 只输出两个不可变类型；不从消息、metadata 或 Platform API 补身份。测试使用 HS256 专用密钥，生产密钥由部署 Secret 注入。

### 4. Modeling 使用显式 Provider 分支

`build_model` 只接受 `ResolvedRuntimeConfig`，解析 `provider:model` 格式。`deepseek` 使用 `ChatDeepSeek` 和 `DEEPSEEK_PROXY_*` 环境，`openai` 使用 `ChatOpenAI` 和 `GPT_PROXY_*` 环境，其他 Provider 交给 `init_chat_model` 的标准环境。环境读取位于 Modeling，不进入 Resolver；不使用 LangChain 的 runtime-configurable model 逃生口。

### 5. 错误保持轻量且稳定

`RuntimeErrorBase` 只保存 `code` 和可选 `field`，Auth、Resolution、Model 初始化分别使用稳定前缀。错误字符串不包含 JWT、API Key、Prompt 或完整 claims。不会建立复杂异常继承树。

## Risks / Trade-offs

- [JWT 算法或 claim 约定变更] -> 只接受明确算法和 `type`，通过契约测试锁定；变更必须提升 policy version。
- [Provider 环境缺失] -> Modeling 立即返回稳定错误；不自动切换 Provider 或 fake model。
- [Runtime.context 的未知字段可能在 Agent Server 更早被丢弃] -> R1 先测试本地 parser；真实 Agent Server schema/HTTP 行为留给 R2 集成门槛。
- [浮点 canonical JSON 差异] -> Resolver 将数值规范化为有限 float，并固定 JSON 参数、编码和 hash 前缀。

## Migration Plan

无运行时迁移。R1 只新增公共 Runtime 模块和单元测试；旧代码、旧 Graph、旧数据不读取。后续 R2 在新的 Agent Service 中显式调用 Resolver/Modeling；若 R1 验收失败，回滚仅为停止导入新模块，不改变 R0 配置。

## Open Questions

- R2 再用锁定版本的 LangGraph Agent Server 集成测试确定 `Runtime.context` 的最终注入位置。
- Platform Gateway 的 JWT 签发和配置快照属于 P1，不在 R1 实现。
