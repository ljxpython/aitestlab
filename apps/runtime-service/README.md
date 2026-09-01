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

### Langfuse 可观测（R5）

Runtime 默认不初始化 Langfuse。需要本地 Trace 时，在被 `langgraph.json` 和
`langgraph.demo.json` 引用的 `.env` 中显式设置：

```text
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=<由部署环境提供>
LANGFUSE_SECRET_KEY=<由部署环境提供>
LANGFUSE_BASE_URL=<Langfuse 服务地址>
LANGFUSE_TRACING_ENVIRONMENT=local
```

`LANGFUSE_ENABLED` 不是 `true` 时完全关闭；显式开启但缺少必填配置会在 application lifespan 启动时失败。
R5 只发送脱敏 metadata，不发送完整 Prompt、模型响应、Tool 参数或凭据。`.env` 已被 Git 忽略，
不要提交真实值。

生产和 Demo 配置都通过 `http.app=runtime_service.webapp:app` 管理进程级 Langfuse client；该 app
不添加业务路由。真实 smoke 必须显式执行：

```bash
RUNTIME_R5=1 uv run pytest tests/e2e/test_langfuse_real.py -m e2e -q
```

目标镜像已能加载该 custom app 并连接 PostgreSQL/Redis，但当前 Agent Server entitlement 检查返回
`403`，容器在 application startup 完成前以退出码 `3` 退出。生产 SIGTERM 与 bounded flush 因此仍未验证。

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

R0 使用 fake model，不需要 Platform API 或 Provider 凭据即可启动。当前 R3 已接入 Runtime
配置、调用上限、Tool Error/Retry 和单次 Model timeout；生产 Provider fallback/retry、Durable
Checkpoint 和 Platform Gateway 仍按 28 号计划单独验收。

## R4 能力 Demo（已完成）

`langgraph.demo.json` 注册五个可学习 Graph：

- `reference_agent`：`create_agent`、RuntimeContext、Middleware 和显式只读 Tool；
- `workflow_demo`：Typed `StateGraph`；
- `deep_agent_demo`：`create_deep_agent`、`StateBackend`、Bundled Skill、缩权 Subagent；
- `mcp_demo`：Service 私有 stdio fake MCP（`MultiServerMCPClient.get_tools()`）、名称冲突和 allowlist；
- `backend_demo`：Thread-scoped `StateBackend`。

每个 Service 的组合逻辑都直接写在自己的 `get_agent()` 中。没有公共 `build_agent`、Builder、
Factory 或 Registry；只有在出现真实重复或复杂生命周期时，才允许 Service 私有下划线辅助函数。

R4 已归档。R5 已完成 Runtime 本地生命周期、可信 metadata、Model/Tool/Subagent callback 和真实
Langfuse smoke；目标镜像仅完成 custom app import，SDK queue drop 指标、生产容器 startup/SIGTERM/drain
和跨服务传播仍未闭合。R6 Durable
Run 真实部署验证继续后置。
Platform Run Explorer 仍留到 Runtime 验证完成后的 P1 阶段。

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

## R6 Durable Run 验证

R6 使用 Agent Server 原生 Thread/Run/Checkpoint，不在 Runtime 内实现第二套持久化状态机。
快速测试不会启动外部服务；真实 Durable 测试需要一个正在运行的 Agent Server，并设置：

```text
RUNTIME_DURABLE_URL=http://127.0.0.1:8123
RUNTIME_DURABLE_ASSISTANT_ID=reference_agent
```

启动隔离 PostgreSQL、Redis 和 Runtime 容器并执行一次 smoke：

```bash
./scripts/r6-durable-smoke.sh
```

该脚本使用测试专用本地 Delegation Token，凭据只从环境变量读取，不调用 Platform API。保留
容器以便排查时设置 `R6_KEEP_SERVICES=1`。Durable 测试命令：

```bash
RUNTIME_DURABLE_URL=http://127.0.0.1:8123 uv run pytest tests/durable -m durable -q
```

缺少真实服务时测试会明确跳过，不能将跳过结果当作 R6 通过。

## 文档入口

1. `docs/README.md`
2. `docs/knowledge/28-runtime-refactor-development-plan.md`
3. `docs/knowledge/13-runtime-service-target-code-layout.md`
4. `docs/knowledge/24-package-langgraph-startup-shutdown-design.md`
5. `docs/knowledge/25-runtime-testing-and-cross-service-contract-design.md`

`docs/standards/` 将在 R0 完成后，根据绿色重构后的实际实现重新生成；在此之前不要引用归档
目录中的旧标准。
