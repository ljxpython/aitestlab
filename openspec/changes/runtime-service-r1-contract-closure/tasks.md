## 1. Runtime 合同与快照测试

- [x] 1.1 补齐五类 Runtime 类型、Context、Principal、Policy 的字段类型、范围、bool、NaN、inf、重复值、空值和不可变性失败测试。
- [x] 1.2 实现 `runtime-context/v1` 的规范化 Context hash，并为等价输入、语义变化、缺失 hash 和篡改 hash 增加失败测试。
- [x] 1.3 为 `ResolvedRuntimeConfig` 增加安全 JSON snapshot 投影和 round-trip 测试，断言不包含完整 Prompt、JWT、secret、模型实例或 callback。
- [x] 1.4 扩展 `tests/runtime/test_auth.py`，覆盖 `scope` 结构、tenant/project/assistant/thread 一致性、`context_hash`、未知 claim 和错误脱敏。

## 2. Resolver 权限闭合

- [x] 2.1 在 Service 私有配置中声明最小 permission-to-tool 映射，并扩展 `resolve_runtime_config` 的 Required/Optional Tool 三方交集和 fail-closed 错误测试。
- [x] 2.2 验证 `tools=None`、`tools=()`、显式 optional tools、Required Tools 和 Actor permissions 的组合语义，确保输入对象不被修改。
- [x] 2.3 增加无 I/O 门禁测试，证明 Resolver 不访问网络、数据库、文件系统、MCP 或 Provider。

## 3. Agent Server Auth 与 Service 接线

- [x] 3.1 新增 `runtime_service/auth/platform.py` 的 `langgraph_sdk.Auth` 适配器，复用纯 verifier，输出最小且不进入 Prompt 的 runtime auth facts。
- [x] 3.2 在 `langgraph.json` 注册 Auth path，并固定 local signer、真实 Delegation JWT 和缺少/无效 Authorization 的 HTTP 行为。
- [x] 3.3 修改 `RuntimeConfigMiddleware`，从 `runtime.server_info.user` 读取已验证 Principal/Policy/scope/hash，统一在 agent、model、tool 边界解析并 fail-closed。
- [x] 3.4 移除 `reference_agent` 生产路径对模块级固定 Principal/Policy 的依赖，保留显式测试 fixture 和 `_runtime_model` 测试注入边界。
- [x] 3.5 增加最小 Agent Server shortest-chain 测试，验证 Auth -> RuntimeContext -> Resolver -> Model/Tool 的可信事实一致传播；环境或版本不支持时记录 `blocked`，不得用 skip 宣称通过。

## 4. 验证与文档收口

- [x] 4.1 运行 R1 local、middleware 和 shortest-chain 测试，记录命令、输入、结果、未覆盖边界和真实环境阻塞原因。
- [x] 4.2 更新 14、28、31 号文档的实现位置、测试位置、验证记录、状态和“是否实现”列；只有完整 Requirement 才填 `✅`。
- [x] 4.3 创建并持续维护本 change 的 `verification.md`，记录 owner pre-apply review、Disposition、证据和残余风险。
- [x] 4.4 检查 runtime-service README、部署配置和 runbook 是否需要同步；完成 `git diff --check`、compile/test 和 graphify 更新。
