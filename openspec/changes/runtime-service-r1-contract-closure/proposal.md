## Why

R1 当前只有本地能力的部分实现，不能证明设计要求已经进入真实 Agent Server 链路：Delegation JWT 缺少 `scope` 和 `context_hash`，Actor 权限没有参与 Tool 决议，Service 仍使用固定 Principal/Policy。现在补齐这些缺口，才能让 Runtime 在不依赖 Platform API 查询的前提下，对每次 Run 使用可验证且可复现的身份、策略和 Context。

## What Changes

- **BREAKING** 冻结并校验 Delegation claims 中的 `scope` 与 `context_hash`，篡改或不一致时 fail-closed。
- 让 Resolver 对 Required/Optional Tools 同时应用 Service、RuntimePolicy 和 `RuntimePrincipal.permissions` 的交集规则。
- 补齐 Runtime 合同的边界测试、输入不可变性测试和 `ResolvedRuntimeConfig` 的安全 snapshot round-trip 测试。
- 将 Agent Server Auth 产生的 Principal/Policy 接入 `reference_agent` 的 Runtime Resolver 链，移除生产路径对固定身份和策略的依赖。
- 保留 fake/local signer 仅作为测试输入，不增加 Platform API、Policy 查询服务或公共 Capability Registry。
- 更新 R1 对齐目录、verification 证据和相关运行文档；真实 Agent Server 证据作为独立的 shortest-chain/formal 验收边界记录。

## Capabilities

### New Capabilities

无。此次是对已有 Runtime 合同和 Agent Service 组合根要求的闭合，不创建重复 capability。

### Modified Capabilities

- `runtime-contracts`：补充 Delegation `scope/context_hash`、Principal 权限交集、snapshot 安全投影和完整边界验收要求。
- `runtime-agent-service-integration`：补充 Agent Server Auth 到 Principal/Policy，再到 Context/Resolver 的真实组合根接线要求。

## Impact

- 所属 locus：`apps/runtime-service`；最短链：Agent Server Auth -> `reference_agent` -> Runtime Resolver -> Model/Tool 边界。
- Band：B3 Governed，涉及 auth、permission、公开运行时契约和 Agent Server 集成。
- 主要代码：`src/runtime_service/runtime/auth.py`、`resolver.py`、`contracts.py`、`middlewares/runtime_config.py`、`services/reference_agent/agent.py`、`langgraph.json`。
- 主要测试：`tests/runtime/`、`tests/middlewares/`、`tests/services/reference_agent/`，新增最小 HTTP/Agent Server 集成门禁（若锁定 Server 版本支持该入口）。
- 兼容性：旧 `platform_runtime`、从 Context 注入身份、固定生产 Principal/Policy 均不保留兼容分支；本地无 Agent Server 的单测继续使用显式测试 fixture。
- 回滚：在 owner 接受前不应用代码；若 Agent Server 版本不支持所需 Auth 入口，保留当前本地实现并将链路状态标记为 `blocked`，不伪造完成。
