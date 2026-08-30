## 1. Service Runtime 组合根

- [x] 1.1 在 `reference_agent/agent_server.py` 声明本服务的 `AgentDefaults`、演示 `RuntimePrincipal` 和 `RuntimePolicy`，并从 `RunnableConfig` 解析新 Context。
- [x] 1.2 在组合根中调用 `resolve_runtime_config` 和 `build_model`，使用 `create_agent(..., context_schema=RuntimeContext)` 构造 graph，并保留 `with_config(config)`。
- [x] 1.3 为测试提供显式 fake model 注入路径；默认路径不得把 Provider 缺失静默替换为 fake model。

## 2. 组合测试与文档

- [x] 2.1 新增 `tests/services/reference_agent/test_agent_server.py`，覆盖默认入口、合法 Context、零值覆盖、非法 Context/Policy 和 fake model 行为。
- [x] 2.2 更新 `reference_agent/README.md` 和必要的 Graph 描述，说明 Runtime Context 入口、静态/动态生命周期和本地调试命令。

## 3. 验证与交付记录

- [x] 3.1 运行 R0/R1/R2 单元和组合测试、`compileall`、`uv lock --check` 以及 `git diff --check`。
- [x] 3.2 运行 OpenSpec strict validate、更新 graphify，并在 `verification.md` 记录检查命令、结果、未覆盖边界和文档影响。
