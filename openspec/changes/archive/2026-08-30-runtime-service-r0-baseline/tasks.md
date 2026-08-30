## 1. 包和目录基线

- [x] 1.1 更新 `apps/runtime-service/pyproject.toml`，启用 `src/runtime_service` 的可安装包发现并保持现有锁定依赖。
- [x] 1.2 创建 `src/runtime_service/`、`src/runtime_service/graphs/`、`src/runtime_service/services/` 及两个 Service 子目录的最小包文件。

## 2. R0 参考 Service

- [x] 2.1 实现 `reference_agent` 的静态 `create_agent` fake-model Graph 和异步 `get_agent(config)` 入口。
- [x] 2.2 实现 `workflow_demo` 的最小 Typed StateGraph 和异步 `get_agent(config)` 入口。
- [x] 2.3 创建 `graphs/reference_agent.py` 和 `graphs/workflow_demo.py`，只重导出对应 Service 入口，并补充 Service README。

## 3. LangGraph 配置

- [x] 3.1 创建根级 `apps/runtime-service/langgraph.json`，只注册 `reference_agent` 并提供描述。
- [x] 3.2 创建 `apps/runtime-service/langgraph.demo.json`，注册 `reference_agent` 和 `workflow_demo` 并提供描述。
- [x] 3.3 创建非敏感的根级 `.env.example`，确认配置不引用旧 Graph、旧 Auth 或旧 HTTP app。
- [x] 3.4 从 `~/.my_best/.env` 注入未跟踪的 Runtime `.env`，配置 DeepSeek 文本中转、GPT 多模态中转和 `RUNTIME_E2E` 开关，不输出或提交密钥。

## 4. 测试和验证

- [x] 4.1 增加 R0 测试，覆盖新包导入、配置 Graph 列表/描述、旧路径未注册和两个 `get_agent` 返回 `Pregel`。
- [x] 4.2 增加 fake model 与确定性 workflow 的最小执行测试，不依赖 Platform API、Provider secret 或外部基础设施。
- [x] 4.3 增加显式 `RUNTIME_E2E=1` 的真实模型 E2E：文本使用 DeepSeek 中转，后续多模态使用 GPT 中转；凭据缺失不得降级为 fake model。
- [x] 4.4 执行 `uv lock`、`uv sync`、`python -m compileall src`、R0 pytest 和 LangGraph 配置加载/smoke 检查；凭据可用时执行真实模型 E2E。

## 5. 文档和验证记录

- [x] 5.1 在 `verification.md` 持续记录 pre-apply review、执行命令、结果、未覆盖边界和 docs/runbook 影响。
- [x] 5.2 R0 门槛全部通过后，更新 28 号计划的当前阶段状态；不提前勾选或实施 R1。
