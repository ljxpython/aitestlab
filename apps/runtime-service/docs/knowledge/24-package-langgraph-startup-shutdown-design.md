# Package、langgraph.json、启动与优雅退出设计（Draft）

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `11-agent-service-directory-architecture.md`、
> `13-runtime-service-target-code-layout.md`、
> `23-graph-thread-backend-checkpoint-lifecycle-design.md`、
> `26-runtime-custom-routes-and-model-config-design.md`

## 1. 本轮结论

部署边界固定为：

```text
pyproject.toml  -> Python Package 和依赖
langgraph.json  -> Graph、Auth 和 Agent Server 部署配置
agent.py -> Service 显式装配和 get_agent(config)
Agent Server    -> HTTP、Queue、Thread、Run、Checkpoint、Drain、恢复
Platform API    -> 调度、幂等、权限、Run 默认值和控制面
```

必须遵守：

1. `apps/runtime-service` 是项目根，`src/runtime_service` 是唯一正式 Python 包。
2. `langgraph.json` 放在 `apps/runtime-service/`，只注册 `src/runtime_service/graphs/` 下的稳定入口。
3. 生产只保留一份规范 `langgraph.json`，不复制 auth、Graph 和环境配置。
4. Dockerfile 不重复维护 `LANGSERVE_GRAPHS`、依赖列表或 Graph 路径。
5. 静态 Graph 在启动阶段加载；Thread Sandbox、MCP 和用户级 Backend 延迟到真实 Run。
6. Agent Server 负责生产 Queue、Thread、Run、Checkpoint 和 shutdown drain；Service 不实现第二套生命周期管理器。
7. 优雅退出先停止接收新任务，再让进行中的 Run 在可恢复边界退出；硬退出由 Agent Server 的恢复/清理机制处理。
8. `langgraph.json.http.app` 只挂载 `runtime_service.webapp:app` 的生命周期，用于进程级 Langfuse
   初始化和有界关闭；不新增 Runtime Custom Route。前端和模型配置由 Platform API 承担，Runtime
   只消费透传的 RuntimeContext。

## 2. Package 结构

目标物理布局：

```text
apps/runtime-service/
├── pyproject.toml
├── uv.lock
├── langgraph.json
├── .env.example
├── src/
│   └── runtime_service/
│       ├── __init__.py
│       ├── auth/
│       ├── runtime/
│       ├── middlewares/
│       ├── observability/
│       ├── webapp.py
│       ├── graphs/
│       │   └── reference_agent.py
│       └── services/
│           └── reference_agent/
│               └── agent.py
├── tests/
└── deploy/
```

`pyproject.toml` 使用标准 src layout：

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

本地、测试和容器都通过安装包导入：

```bash
uv sync --frozen
uv run python -c "import runtime_service"
```

不能依赖当前工作目录偶然位于 `apps/runtime-service`，也不能通过手工修改 `PYTHONPATH` 掩盖包配置错误。

依赖和版本的唯一来源：

```text
pyproject.toml -> 声明依赖范围
uv.lock        -> 锁定实际版本
langgraph.json -> 声明 Agent Server 使用的包和 Graph
```

Python、LangGraph CLI、LangGraph API 基础镜像和锁文件必须通过版本矩阵一起验证。

## 3. langgraph.json

LangGraph CLI 默认读取当前目录的 `langgraph.json`。目标配置：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "python_version": "3.13",
  "dependencies": ["."],
  "http": {
    "app": "./src/runtime_service/webapp.py:app"
  },
  "auth": {
    "path": "./src/runtime_service/auth/platform.py:auth"
  },
  "graphs": {
    "reference_agent": {
      "path": "./src/runtime_service/graphs/reference_agent.py:get_agent",
      "description": "Runtime Service reference agent"
    }
  },
  "env": ".env"
}
```

当前 `http.app` 只承载生命周期，不提供业务路由。任何未来 Runtime Custom Route 都必须单独评审，
同时验证路由认证、命名空间和默认路由覆盖风险。

字段职责：

| 字段 | 作用 | 约束 |
| --- | --- | --- |
| `dependencies` | 当前包和额外本地包 | 首期使用 `["."]`，不指向 requirements 文件 |
| `graphs` | Graph 稳定导出表 | 只指向 `graphs/*.py`，不注册 Service 私有路径 |
| `auth` | Agent Server Auth 入口 | 使用新 Runtime Auth，不注册 Legacy Auth |
| `env` | 环境变量文件 | 只放路径，secret 不写入 JSON |
| `python_version` | 运行时 Python 版本 | 必须与 Package 和镜像一致 |

稳定导出层只重导出入口：

```python
from runtime_service.services.reference_agent.agent import get_agent

__all__ = ["get_agent"]
```

### 3.1 单一配置真源

新架构不维护以下重复配置：

- `runtime_service/langgraph.json`；
- `langgraph_auth.json`；
- `langgraph.local-integration.json`；
- Dockerfile 中手工编写的 `LANGSERVE_GRAPHS`；
- 生产和本地各自复制一份 Graph 列表。

本地与生产的差异通过环境变量、凭证签发方式和持久化后端表达。只有 Graph 集合确实不同且无法通过环境配置解决时，才单独评审第二份配置文件。

### 3.2 Checkpoint 和 Store 配置

Checkpoint/Store TTL 可以使用 Agent Server 或 `langgraph.json` 支持的部署配置，但具体字段必须以锁定版本的 CLI schema 为准。Service 代码不创建数据库 Checkpointer、Store Manager 或清理器。

## 4. 启动生命周期

```text
进程启动
  -> 读取 langgraph.json
  -> 安装/加载 runtime_service
  -> 加载 Auth
  -> 导入 graphs/<graph_id>.py
  -> 加载静态 Graph
  -> 校验注册、依赖和基础配置
  -> readiness=true
  -> 接受 HTTP / Queue 请求
```

启动阶段允许：

- 导入 Python 包；
- 编译静态 Graph；
- 校验 Graph 导出和 State Schema；
- 校验必要环境变量和 Auth 配置；
- 初始化进程级、无用户归属的客户端。

启动阶段禁止：

- 创建 Thread Sandbox；
- 读取用户、租户或 Thread 状态；
- 连接用户级 MCP；
- 创建用户级 Backend；
- 执行文件、代码、数据库写入或其他不可逆动作。

静态 Graph 导入失败、Auth 配置非法或必要依赖缺失时，进程必须启动失败，不允许进入部分可用的 ready 状态。

动态 Graph 只在真实执行上下文中获取 Thread Backend。对于统一的 `get_agent(config)` 入口，可参考 Open SWE 的 `graph_loaded_for_execution(config)`；如果锁定版本提供可靠的 `ServerRuntime.execution_runtime`，则使用官方机制。schema、visualization 等 introspection 请求不能触发昂贵资源初始化。

## 5. 本地启动

从项目根启动：

```bash
cd apps/runtime-service
uv run langgraph dev \
  --config ./langgraph.json \
  --port 8123 \
  --no-browser
```

本地调试必须复用生产入口：

- 同一 `langgraph.json`；
- 同一 Graph 导出路径；
- 同一 Auth；
- 同一 `RuntimeContext`、Resolver 和 Middleware；
- 同一 `get_agent(config)`。

本地可以替换 Token Signer、环境变量、日志级别和测试持久化后端，但不能用 local flag 绕过身份、策略或工具权限。

最小启动验证：

```bash
uv run python -c "from runtime_service.graphs.reference_agent import get_agent"
uv run langgraph dev --config ./langgraph.json --no-browser
curl http://127.0.0.1:8123/info
```

## 6. 生产构建和部署

优先使用 LangGraph CLI 根据 `langgraph.json` 生成 Dockerfile：

```bash
langgraph dockerfile -c langgraph.json deploy/Dockerfile
```

如果确实需要自定义 Dockerfile，只允许增加系统依赖、基础镜像或构建参数，不得复制：

- Python 依赖列表；
- Graph 注册表；
- Auth 路径；
- `.env` 内容；
- Checkpoint 业务逻辑。

修改 `langgraph.json` 后，生成的 Dockerfile 必须重新生成或明确同步。生产镜像必须验证：

```text
包可导入
所有 Graph 可加载
Auth 可初始化
readiness 只在完整成功后返回
容器收到 SIGTERM 可进入 drain
```

## 7. 优雅退出

### 7.1 退出顺序

```text
收到 SIGTERM/SIGINT
  -> 停止接收新 HTTP 请求
  -> 停止领取新的 Queue Run
  -> 对进行中的 Run 发起 drain
  -> 当前 super-step 完成并保存可恢复 Checkpoint
  -> 在 Grace Period 内等待结束
  -> 超时 Run 重新入队或标记 abandoned
  -> flush Trace、日志和指标
  -> 释放 Service 自有资源
  -> 进程退出
```

LangGraph >= 1.2 提供 `RunControl` 和 `GraphDrained`，可用于需要显式控制的执行路径：

```python
control = RunControl()

try:
    result = await graph.ainvoke(
        input_data,
        config=config,
        control=control,
    )
except GraphDrained:
    # 当前边界已持久化，可使用同一 thread/config 恢复
    pass
```

Agent Server 已经负责 Queue lease、Run 状态、恢复和 sweeper。Service 不实现全局 signal handler、Run 列表扫描或自定义重试队列。

R5 使用 `http.app` 的 FastAPI lifespan 管理进程级 Langfuse client：startup 只校验显式启用的
Langfuse 配置并初始化一次，shutdown 执行一次有界 flush。该 app 不拥有 Run、Thread、Queue 或
Checkpoint，也不添加业务路由；生产 drain 和 Worker recovery 仍由 Agent Server 负责。

目标生产镜像验证已确认 Agent Server 能加载 custom auth 和 `webapp.py:app`，并连接 PostgreSQL/Redis；
但当前 LangSmith 账号的 Agent Server entitlement 检查返回 `403`，combined lifespan 尚未完成 startup，
容器以退出码 `3` 退出。因此这条证据只证明镜像配置和 app import，不证明生产 startup、SIGTERM、
bounded flush 或 drain。

### 7.2 Hard Shutdown

进程崩溃或 Grace Period 到期时：

```text
Worker 心跳停止
  -> Agent Server sweeper 发现失联 Run
  -> Run 重新入队或进入明确失败状态
  -> 新 Worker 从最近 Checkpoint 恢复
```

Run 不能因为客户端 SSE 断开就被标记为取消；断线策略由 Platform 的 Durable Run 默认值决定。

### 7.3 资源释放

静态 Graph 通常没有需要释放的资源。动态 Graph 的 Sandbox、MCP Client 或临时 Backend 必须由明确的资源所有者释放：

```text
获取资源 -> 执行 Run -> 完成/失败/取消 -> 释放资源
```

禁止使用 `atexit` 清理异步资源，禁止在模块导入时连接用户级服务。如果资源需要 factory setup/teardown，则采用官方 async context manager factory 并单独评审。

## 8. 具体落地顺序

1. 创建 `src/runtime_service` 和标准 Package 配置，执行 `uv sync --frozen` 与 import 检查。
2. 创建唯一 `apps/runtime-service/langgraph.json`，只注册 `graphs/*.py` 新入口。
3. 实现静态 `reference_agent`，确认模块加载只编译一次。
4. 使用 `langgraph dev` 验证 `/info`、Graph 加载、Auth 和基础 Run。
5. 使用 Agent Server 的真实持久化验证 Thread、Checkpoint、Interrupt 和 Worker 重启。
6. 再增加动态 Backend Agent，验证 introspection 隔离、Sandbox 重连和资源 TTL。
7. 使用 SIGTERM、RunControl 或 Agent Server 原生 drain 验证优雅退出和恢复。
8. 通过容器启动、readiness、shutdown、恢复 E2E 后，才更新生产部署配置。

## 9. 测试与发布门槛

| 场景 | 必须证明 |
| --- | --- |
| Package import | 安装后 `runtime_service` 从 `src` 正常导入 |
| langgraph.json | 所有 Graph/Auth 路径可解析，无 Legacy 注册 |
| 启动失败 | 依赖、Auth 或 Graph 非法时不进入 ready |
| 静态 Graph | 多次加载不重复编译，不发生用户级 I/O |
| introspection | schema/visualization 不创建 Sandbox/MCP |
| graceful drain | 停止接收新 Run，进行中 Run 在可恢复边界退出 |
| hard shutdown | Worker 失联后 Run 可被恢复或明确标记失败 |
| resource cleanup | MCP、Sandbox、临时 Backend 在退出时释放 |
| config single source | Dockerfile 不复制 Graph/依赖配置 |

未通过上述测试前，不允许把旧 `runtime_service/langgraph.json`、Legacy graph 或手工 `LANGSERVE_GRAPHS` 作为新部署入口继续维护。

## 10. 明确不建设

- `PackageManager`；
- `GraphManager`；
- `ShutdownManager`；
- 自定义 Durable Run 队列；
- 每个 Service 自己的 Checkpointer 清理器；
- 多份互相漂移的 `langgraph.json`；
- Dockerfile 内重复的 Graph、Auth 和依赖注册；
- 通过 local flag 绕过 Auth、Resolver 或 Capability Policy。

## 11. 参考资料

- LangGraph CLI 配置：`/langsmith/cli`
- Monorepo `langgraph.json`：`/langsmith/monorepo-support`
- Graph Rebuild：`/langsmith/graph-rebuild`
- Graceful Shutdown：`/oss/python/langgraph/fault-tolerance#graceful-shutdown`
- Agent Server Run Lifecycle：`/langsmith/agent-server#run-execution-lifecycle`
- Open SWE：`agent/server.py`、`langgraph.json`

## 12. 实现对齐目录

> 本目录只核对本文在 R0 可验收的部分。Agent Server Durable、优雅退出和资源恢复
> 属于 R6 或生产部署门槛，不得用 `langgraph dev` 的 in-memory 结果冒充。

| ID | 要求 | 阶段 | 实现位置 | 测试位置 | 验证记录 | 状态 | 缺口/后续 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `24-R0-DEP-001` | 安装后可从 `src` 导入 `runtime_service` | R0 | `pyproject.toml`；`src/runtime_service/__init__.py` | `tests/test_r0_baseline.py:22-25` | 本轮 `uv run python -c "import runtime_service"` 通过 | `implemented-local` | 继续保留安装后 import 检查 |
| `24-R0-DEP-002` | 根 `langgraph.json` 是生产 Graph 注册入口 | R0 | `langgraph.json:1-10` | `tests/test_r0_baseline.py:28-34` | 配置解析通过；本地服务 `/info` 返回 `0.13.0` / `1.2.11` | `implemented-local` | 当前配置按 R0 延后 Auth，不能写成生产认证已完成 |
| `24-R0-DEP-003` | R0 基线不依赖 R4 Demo 注册，完整 Demo 配置由 R4 验收 | R0 | `langgraph.demo.json:5-25`；R4 测试归属 | `tests/test_r0_baseline.py`；`tests/services/test_r4_capability_demos.py:test_demo_config_registers_all_r4_capability_graphs` | R0 `6 passed`；R4 `10 passed` | `implemented-local` | `langgraph.demo.json` 按设计注册五个示例；R0 不再把 R4 Graph 当作自身门槛 |
| `24-R0-DEP-004` | Dockerfile 的 Graph 注册由生产配置生成并保持同步 | R0 | `deploy/Dockerfile:3-20`；`langgraph.json:5-10` | `tests/test_r0_baseline.py:test_docker_graph_registry_matches_production_config` | R0 `6 passed`，逐项比较 Graph ID、路径和描述 | `implemented-local` | 修改 `langgraph.json` 后必须重新生成 Dockerfile；测试不替代真实容器启动验证 |
| `24-R0-DEP-005` | `langgraph dev --config ./langgraph.json` 能启动并可 introspection | R0 | `langgraph.json`；`graphs/reference_agent.py` | `tests/test_r0_baseline.py`；`curl /info` | 本轮启动成功，`/info` 返回 JSON；日志显示 `noop` auth 和 in-memory runtime | `implemented-local` | 只证明 local_dev，不证明 licensed Agent Server |
| `24-R0-DEP-006` | Graph/Auth/依赖非法时不能进入 ready | R0 | 当前无统一启动失败门禁 | 无 | 未找到可失败的启动失败测试 | `missing` | 增加最小非法配置/导入失败检查；生产 readiness 留给 R6/部署验证 |
| `24-R0-DEP-007` | Agent Server 负责 Queue、Checkpoint、drain 和 worker recovery | R6 | Agent Server 外部能力 | `tests/durable/` | R0 不执行；当前 Durable 测试因无 `RUNTIME_DURABLE_URL` 全部 skip | `deferred` | 不把 R6 后置能力算进 R0 |
