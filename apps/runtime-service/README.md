# Runtime Service

`apps/runtime-service` 是 LangGraph、LangChain 和 DeepAgents 的执行层。当前按绿色重构开发，
新代码唯一位于：

```text
apps/runtime-service/src/runtime_service/
```

旧 `runtime_service/` 包已经归档到 `archive/apps/runtime-service/runtime_service/`，不再导入、
适配或维护。

## R0 基线

R0 当前提供两个参考入口：

- `reference_agent`：`create_agent` + fake model
- `workflow_demo`：Typed `StateGraph` + 确定性节点

生产配置 `langgraph.json` 只注册 `reference_agent`；本地学习配置
`langgraph.demo.json` 注册两个 Demo。每个 Service 的正式入口都是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

## 安装和配置

```bash
uv sync --frozen
```

真实模型 E2E 使用项目根 `.env`。该文件已加入 Git 忽略，变量从本机
`~/.my_best/.env` 注入：

- `DEEPSEEK_PROXY_URL`、`DEEPSEEK_PROXY_API_KEY`、`DEEPSEEK_PROXY_DEFAULT_MODEL`：文本模型
- `GPT_PROXY_URL`、`GPT_PROXY_API_KEY`、`GPT_PROXY_DEFAULT_MODEL`：多模态模型
- `RUNTIME_E2E=1`：显式开启真实模型 E2E

不要把 API Key 写入 `.env.example`、测试 fixture、日志或 OpenSpec。缺少真实模型凭据时，
真实 E2E 必须报告未执行或失败，不能自动降级为 fake model。

## 本地启动

从本目录执行：

```bash
uv run langgraph dev --config ./langgraph.json --port 8123 --no-browser
```

学习两个 Demo 时使用：

```bash
uv run langgraph dev --config ./langgraph.demo.json --port 8124 --no-browser
```

启动后检查：

```bash
curl http://127.0.0.1:8123/info
```

R0 使用 fake model，不需要 Platform API 或 Provider 凭据即可启动。Auth、RuntimeContext、
Middleware、Tool、Backend、Checkpoint 和 Platform Gateway 按 28 号计划的后续阶段实施。

## R4 能力 Demo（已完成）

`langgraph.demo.json` 注册五个可学习 Graph：

- `reference_agent`：`create_agent`、RuntimeContext、Middleware 和显式只读 Tool；
- `workflow_demo`：Typed `StateGraph`；
- `deep_agent_demo`：`create_deep_agent`、`StateBackend`、Bundled Skill、缩权 Subagent；
- `mcp_demo`：Service 私有 stdio fake MCP（`MultiServerMCPClient.get_tools()`）、名称冲突和 allowlist；
- `backend_demo`：Thread-scoped `StateBackend`。

每个 Service 的组合逻辑都直接写在自己的 `get_agent()` 中。没有公共 `build_agent`、Builder、
Factory 或 Registry；只有在出现真实重复或复杂生命周期时，才允许 Service 私有下划线辅助函数。

R4 已归档。下一阶段是 R5 Runtime 可观测、Run Event 和事件投影；对应 Platform Run Explorer
变更在 Runtime 验证完成后再实施。

本地运行能力 Demo：

```bash
uv run langgraph dev --config ./langgraph.demo.json --port 8124 --no-browser
```

## R1 Runtime 合同

R1 已新增 `src/runtime_service/runtime/` 公共最小能力：

- `contracts.py`：不可变的 Principal、Context、Policy、Defaults 和 Resolved Config
- `resolver.py`：严格解析、默认值合并、Tool allowlist 检查和稳定 hash
- `auth.py`：短期 Runtime Delegation JWT 验证
- `modeling.py`：`deepseek:`、`openai:` 显式模型构造和官方 `init_chat_model` 回退
- `runtime_config.py`：只解析新 Context，不兼容旧配置字段

R1 不修改 R0 Graph，也不读取 Platform API。R1 单元测试使用本地合同和假构造器：

```bash
uv run pytest tests/runtime -q
```

模型 Provider 凭据只在 `modeling.py` 的执行边界读取；R1 测试不会调用真实 Provider。

## 测试

快速测试不访问外部服务：

```bash
uv run pytest tests/test_r0_baseline.py -q
```

真实文本模型 E2E：

```bash
RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q
```

真实模型 E2E 必须使用 DeepSeek 文本中转；后续多模态 E2E 使用 GPT 中转。测试分层和跨服务
契约见 `docs/knowledge/25-runtime-testing-and-cross-service-contract-design.md`。

## 文档入口

1. `docs/README.md`
2. `docs/knowledge/28-runtime-refactor-development-plan.md`
3. `docs/knowledge/13-runtime-service-target-code-layout.md`
4. `docs/knowledge/24-package-langgraph-startup-shutdown-design.md`
5. `docs/knowledge/25-runtime-testing-and-cross-service-contract-design.md`

`docs/standards/` 将在 R0 完成后，根据绿色重构后的实际实现重新生成；在此之前不要引用归档
目录中的旧标准。
