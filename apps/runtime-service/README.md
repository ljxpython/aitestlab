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

- `reference_agent`：`create_agent` + Runtime 模型解析
- `workflow_demo`：真实模型 `create_agent` + Typed `StateGraph` 条件路由/HITL

生产配置 `langgraph.json` 注册 `reference_agent` 和真实模型驱动的 `workflow_demo`；本地学习配置
`langgraph.demo.json` 额外注册能力 Demo。每个 Service 的正式入口都是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

## 安装和配置

```bash
uv sync --frozen
```

R6 使用 PyPI 上发布的 GraphHarbor 正式包，依赖由锁文件统一管理：

```bash
uv sync --frozen
uv run --frozen graphharbor --version
```

安装和启动使用 `.venv/bin/...` 或 `uv run --frozen ...`，不依赖相邻 GraphHarbor 源码仓库、
本地 wheel 或 `tool.uv.sources` override。

直接 Runtime Provider smoke 使用项目根 `.env`。正式 Platform Run 不读取这些变量，而是使用
Platform Models 目录签发的短期引用，并通过 `PLATFORM_RUNTIME_MODEL_CONFIG_URL` 获取连接配置。
该文件已加入 Git 忽略，变量从本机 `~/.my_best/.env` 注入：

- `DEEPSEEK_PROXY_URL`、`DEEPSEEK_PROXY_API_KEY`、`DEEPSEEK_PROXY_DEFAULT_MODEL`：文本模型
- `GPT_PROXY_URL`、`GPT_PROXY_API_KEY`、`GPT_PROXY_DEFAULT_MODEL`：多模态模型
- Provider smoke 使用 `tests/e2e` 的 `e2e` marker 选择，不依赖启动开关

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

## GraphHarbor 启动

### 本地进程模式

需要同时启动 Runtime 和 Platform 时，从仓库根目录执行：

```bash
bash "./scripts/local-stack.sh" doctor
bash "./scripts/local-stack.sh" start
```

停止和查看状态：

```bash
bash "./scripts/local-stack.sh" status
bash "./scripts/local-stack.sh" stop
```

该脚本使用本机 PostgreSQL/Redis，直接管理 GraphHarbor API、Worker、Platform API、Platform Worker
和 Platform Web 的本地进程；它不影响旧的 `platform-web-demo-*` 脚本。GraphHarbor 本身没有前端，
平台前端是 `platform-web`。`doctor` 会校验 Runtime 配置、本机 PostgreSQL/Redis、Platform upstream、
Delegation secret 和端口；`start` 会先执行数据库迁移，再启动进程并等待 Runtime `/ready` 和 Platform API 健康检查。
项目脚本不会自动删除 PostgreSQL 数据目录中的 `postmaster.pid`；检测到失效锁时只给出人工确认后的修复提示。

从本目录执行：

```bash
uv run --frozen graphharbor migrate upgrade
uv run --frozen graphharbor serve --host 127.0.0.1 --port 8123 --config ./langgraph.json
```

学习 Demo 时，使用已配置 PostgreSQL/Redis 且注册 Demo graph 的配置：

```bash
uv run --frozen graphharbor serve --host 127.0.0.1 --port 8124 --config ./langgraph.demo.json
```

启动后检查：

```bash
curl http://127.0.0.1:8123/info
```

测试 fake model 只说明 Service 可以脱离 Provider 执行；正式 `reference_agent` 和 `workflow_demo`
使用 Runtime 模型解析调用 Provider。GraphHarbor 仍需要隔离 PostgreSQL 和 Redis。当前 R3 已接入
Runtime 配置、调用上限、Tool Error/Retry 和单次 Model timeout；生产
Provider fallback/retry 和 Platform Gateway 仍按 28 号计划单独验收。

## R4 能力 Demo（已完成）

`langgraph.demo.json` 注册五个可学习 Graph：

- `reference_agent`：`create_agent`、RuntimeContext、Middleware 和显式只读 Tool；
- `workflow_demo`：真实模型驱动的 `create_agent`，外层保留 Typed `StateGraph` 条件路由和 HITL；
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
uv run --frozen graphharbor serve --host 127.0.0.1 --port 8124 --config ./langgraph.demo.json
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
uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q
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
RUNTIME_DURABLE_URL=http://127.0.0.1:8123 uv run --no-sync pytest tests/durable -m durable -q
```

缺少真实服务时测试会明确跳过，不能将跳过结果当作 R6 通过。

R6 追加验收：

```bash
# 独立 Docker bridge network namespace 的 SSE 断线重连。
# 当前 shell 必须显式提供与 Compose API/Worker 相同的测试 Token。
R6_COMPOSE_PROJECT="r6-verify-$(date +%Y%m%d%H%M%S)" \
RUNTIME_SERVICE_IMAGE=aitestlab-runtime-service:r6-post20 \
R6_RUNTIME_SERVICE_PORT=18134 \
R6_TEST_TOKEN_SECRET="$R6_TEST_TOKEN_SECRET" \
./scripts/r6_network_sse_acceptance.sh

# 隔离 PostgreSQL backup/restore
scripts/r6_postgres_backup_restore.sh

# 性能基线，只记录数据，不自动判定 SLO
.venv/bin/python scripts/r6_performance_baseline.py --url http://127.0.0.1:18123 --runs 4
```

`r6_network_sse_acceptance.sh` 是 bridge SSE 的唯一入口：它先检查 API `/ready`，将目标 Compose
project 的 Worker 收敛为唯一运行实例，再用 `recovery_demo` 执行真实 Worker 功能探针；探针成功后
才启动 bridge 客户端执行 SSE cursor/replay 验收。默认退出会执行带 `--remove-orphans` 的项目清理，
不删除 volume；仅调试时显式设置 `R6_KEEP_SERVICES=1`。

跨网络、备份恢复和性能基线的当前证据会写入 `openspec/changes/archive/2026-09-02-runtime-service-r6-durable-run/verification.md`；
远程 MCP/Sandbox、Langfuse 服务端故障矩阵和 Platform 灰度回滚未通过前，R6 仍保持 `not_ready`。Runtime 镜像回滚
使用 `scripts/r6_runtime_rollback.sh`，默认 dry-run，生产执行必须显式 `--apply` 并设置 `R6_ROLLBACK_CONFIRM=1`。

## 文档入口

1. `docs/README.md`
2. `docs/knowledge/28-runtime-refactor-development-plan.md`
3. `docs/knowledge/13-runtime-service-target-code-layout.md`
4. `docs/knowledge/24-package-langgraph-startup-shutdown-design.md`
5. `docs/knowledge/25-runtime-testing-and-cross-service-contract-design.md`

`docs/standards/` 将在 R0 完成后，根据绿色重构后的实际实现重新生成；在此之前不要引用归档
目录中的旧标准。
