# RunnableConfig vs ServerRuntime：背景资料（归档）

> 说明：这份文档保留为历史背景材料，不再作为 `runtime_service` 当前开发的主规范入口。
> 当前推荐范式请优先参考 `docs/README.md`、`docs/standards/02-architecture.md` 和 `docs/standards/03-agent-development-playbook.md`。

本文用于回答一个高频问题：在 LangGraph 部署与运行中，什么时候用 `RunnableConfig`，什么时候用 `ServerRuntime`。

## 1. 一句话结论

- 默认优先 `RunnableConfig`：把行为差异放在节点内部按配置分支，通常更易测试、维护、演进。
- 仅在“图工厂阶段必须感知服务端上下文”时使用 `ServerRuntime`（例如按认证用户装配资源）。
- `ServerRuntime` 是部署侧图工厂上下文，不是普通业务参数容器；并且官方标注为 beta。

## 2. 官方定义（来源摘要）

### 2.1 RunnableConfig

- `RunnableConfig` 是 `langchain_core` 的 `TypedDict`，用于 `Runnable` 调用配置。
- 关键字段：`tags`、`metadata`、`callbacks`、`run_name`、`max_concurrency`、`recursion_limit`、`configurable`、`run_id`。
- 配置支持父子 runnable 自动传播并合并（不是简单覆盖）。

### 2.2 ServerRuntime

- `ServerRuntime` 是 `langgraph_sdk.runtime` 中传给图工厂（factory）的运行时上下文。
- 典型可用信息：`access_context`、`user`、`store`、`ensure_user()`、`execution_runtime`。
- 图工厂会在多种访问上下文被调用（不只执行 run），包括读状态、更新状态、读 assistant schema。

## 3. 核心差异（工程视角）

| 维度 | RunnableConfig | ServerRuntime |
|---|---|---|
| 所属层级 | Runnable/节点调用层 | Agent Server 图工厂层 |
| 主要用途 | 控制一次调用行为、透传 `configurable` 参数 | 在工厂构图时感知服务端访问上下文/用户/存储 |
| 典型注入点 | `invoke/ainvoke(..., config=...)`，节点内 `get_config()` | `make_graph(config, runtime)` 或 `make_graph(runtime)` |
| 生命周期 | 随每次 runnable 调用传播 | 随 server 对 factory 的每次访问触发 |
| 数据形态 | 轻量配置字典（TypedDict） | 结构化运行时对象（含 user/store/context） |
| 拓扑影响 | 通常不改图拓扑，仅改节点行为 | 可能按上下文重建图；官方要求保持拓扑一致 |
| 性能风险 | 较低，主要是节点逻辑耗时 | 若工厂做重初始化，易触发 slow graph load |
| 稳定性 | 核心调用机制，广泛稳定使用 | 官方标注 beta，升级需关注兼容 |

## 4. 官方约束与常见坑

### 4.1 官方约束

- 官方建议：大多数定制应优先在节点内部基于 config 条件分支，而不是动态改整个图结构。
- 使用 `ServerRuntime` 时，factory 在不同 access context 下都可能被调用。
- 官方要求返回图的拓扑保持一致；尤其写路径（`threads.create_run` / `threads.update`）若拓扑漂移会有状态风险。
- 可用 `execution_runtime` 区分“真实执行”与“只读/内省调用”，从而跳过昂贵初始化。

### 4.2 常见坑

- 把模型/数据库/MCP 重连接放进 factory，导致图加载慢与吞吐下降。
- 在 `assistants.read` 与 `threads.create_run` 返回不同拓扑，导致 pending tasks 或 schema 表现异常。
- 把业务参数错误地塞进 `ServerRuntime` 路径，导致本该是节点逻辑的东西被部署层耦合。

## 5. 针对本仓库（runtime_service）的落地建议

### 5.1 现状

- 当前多数图采用 `RunnableConfig + get_config() + RuntimeContext` 模式（节点内解析运行参数）。
- 已存在 factory 入口场景（如 `assistant_entrypoint`），并观察到 slow graph load 告警风险。

### 5.2 推荐策略

- 规则一：`config-first`。优先把模型、工具、开关控制放在节点执行阶段（按 `RunnableConfig`/context 解析）。
- 规则二：`factory-by-exception`。仅当必须在工厂期读取服务端 user/store/access context 才引入 `ServerRuntime`。
- 规则三：工厂保持轻量（只装配图），重操作延后到节点执行。
- 规则四：若使用 `ServerRuntime`，确保各 access context 下图拓扑一致。

### 5.3 选型决策树（简版）

1) 需求只是“每次运行参数不同”？
- 是：用 `RunnableConfig`（默认）。

2) 需求是“必须在 factory 期按认证用户装配资源/连接”？
- 是：用 `ServerRuntime`，并用 `execution_runtime` 做执行期门控。

3) 是否会改变节点/边/状态结构？
- 若会：重构设计，避免跨 access context 拓扑漂移。

## 6. 最小示例（对照）

### 6.1 RunnableConfig（节点内分支）

```python
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config

def node(state):
    config: RunnableConfig = get_config()
    mode = (config.get("configurable") or {}).get("mode", "default")
    # 根据 mode 决定节点行为
    return state
```

### 6.2 ServerRuntime（工厂上下文）

```python
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime

async def make_graph(config: RunnableConfig, runtime: ServerRuntime):
    user = runtime.ensure_user()
    # 根据 user.identity 决定工厂期装配策略
    return compiled_graph
```

## 7. 参考来源（官方）

- Graph rebuild at runtime（ServerRuntime / access contexts）
  - https://docs.langchain.com/langsmith/graph-rebuild
- RunnableConfig reference
  - https://reference.langchain.com/python/langchain-core/runnables/config/RunnableConfig
- ServerRuntime reference
  - https://reference.langchain.com/python/langgraph-sdk/runtime/ServerRuntime
