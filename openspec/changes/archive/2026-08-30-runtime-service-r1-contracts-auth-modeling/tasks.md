## 1. Runtime 合同与错误

- [x] 1.1 创建 `runtime/contracts.py`，实现五类不可变 dataclass 及公开导出。
- [x] 1.2 创建 `runtime/errors.py`，实现稳定 code/field 错误类型和安全字符串摘要。

## 2. Resolver

- [x] 2.1 实现 Context、Principal、Policy、Defaults 的严格解析与类型/范围校验。
- [x] 2.2 实现 `resolve_runtime_config` 的默认值合并、Tool allowlist 检查和 SHA-256 canonical hash。
- [x] 2.3 增加 `runtime_config.py` 的最小 Context 适配入口，拒绝旧字段且不修改输入。

## 3. Auth 与 Modeling

- [x] 3.1 实现 `auth.py` 的 Delegation JWT 验证、scope 校验和 Principal/Policy 映射。
- [x] 3.2 实现 `modeling.py` 的 DeepSeek/GPT 显式 Provider 分支和标准 `init_chat_model` 回退。
- [x] 3.3 将 Provider 缺失、格式错误和初始化失败映射为稳定 Runtime 错误，不自动 fake fallback。

## 4. 测试与验证

- [x] 4.1 增加合同和 Resolver 单测，覆盖不可变性、未知字段、边界值、三态 Tools 和 hash 稳定性。
- [x] 4.2 增加 Auth 单测，覆盖合法 token、签名/过期/issuer/audience/type/scope/claim 错误。
- [x] 4.3 增加 Modeling 单测，使用 monkeypatch/fake constructor 验证 Provider 参数和失败映射，不调用真实 Provider。
- [x] 4.4 运行 R0 回归、R1 单测、compileall 和 OpenSpec 严格校验；确认 R0 Graph 仍可无凭据启动。

## 5. 文档与收口

- [x] 5.1 更新 Runtime Service 文档入口，记录 R1 新模块边界和本地 Resolver/Auth 调试方式。
- [x] 5.2 创建并维护 `verification.md`，记录 pre-apply review、命令结果、未覆盖边界和 docs/runbook 影响。
