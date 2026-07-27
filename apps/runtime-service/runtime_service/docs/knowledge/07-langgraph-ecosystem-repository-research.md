# LangGraph 生态优秀仓库调研与 runtime-service 对照

- 文档类型：Supporting
- 调研快照：2026-07-27
- 适用范围：`apps/runtime-service`
- 权威边界：本文用于解释外部实现和改进方向；现行约束仍以
  `docs/standards/` 与 `openspec/specs/` 为准。

## 1. 结论

没有一个仓库可以完整照搬到当前项目。最有价值的对照组合是：

1. `open-swe`：生产运行、sandbox、thread/run 调度与中间件治理。
2. `open_deep_research`：显式业务工作流、并行子图、预算和领域评测。
3. `deepagents`：长任务 Agent Harness，不重复实现文件、skills、subagent 和上下文压缩。
4. `langgraph-bigtool`：工具全集注册与运行时可见子集分离。
5. `agent-chat-ui`：threads、stream、interrupt、history 和 UI message 的前端协议。

当前 `runtime-service` 的总体方向合理：静态 graph、`RuntimeContext`、共享
middleware 和 Agent Server 可以继续保留。运行时发现工具的执行闭环已在
`RuntimeRequestMiddleware` 中补齐：模型可见工具和 ToolNode 可执行工具由同一
runtime context 与 allowlist 驱动。

## 2. 仓库清单

| 仓库 | 快照状态 | 主要实现方式 | 适合借鉴 |
| --- | --- | --- | --- |
| [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe) | 活跃，约 10.4k Stars | DeepAgents + 每 thread sandbox + graph factory + durable run | 生产运行、权限、限额、失败恢复 |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | 活跃，约 12.4k Stars | 嵌套 `StateGraph` + supervisor + 并行 researcher | 固定研究流程、状态和评测 |
| [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | 活跃，约 26.8k Stars | `create_agent` 上叠加有序 middleware | 长任务 Harness 和扩展边界 |
| [langchain-ai/langgraph-bigtool](https://github.com/langchain-ai/langgraph-bigtool) | 活跃，约 550 Stars | registry 全量注册，运行时检索并 bind 子集 | 大工具集和工具执行契约 |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 活跃，约 28.7k Stars | 研究流水线 + DeepAgents 集成 + benchmark | 引用质量、私有文档和领域评测 |
| [langchain-ai/agent-chat-ui](https://github.com/langchain-ai/agent-chat-ui) | 活跃，约 3.0k Stars | LangGraph SDK `useStream` | thread、stream、HITL 和 artifact UI |
| [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit) | 活跃，约 36.3k Stars | LangGraph 到 AG-UI 的适配层 | 生成式 UI 和前后端状态协议 |
| [langchain-ai/langgraph-swarm-py](https://github.com/langchain-ai/langgraph-swarm-py) | 活跃，约 1.5k Stars | `active_agent` + Agent 间 handoff | 多轮客服和直接交接 |
| [langchain-ai/langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py) | 活跃，约 1.6k Stars | 中央 supervisor + handoff tools | 分层调度和消息历史裁剪 |
| [langchain-ai/open-agent-platform](https://github.com/langchain-ai/open-agent-platform) | 已归档，约 1.9k Stars | graph 与 assistant/config 分离 | 仅作配置型产品形态参考 |

Stars 只表示社区关注度，不作为架构质量或适用性的判断依据。

## 3. 关键实现对比

### 3.1 Open SWE：Harness 组合，不重写 Agent 循环

`open-swe` 使用 `create_deep_agent(...)` 组合工具、subagent、sandbox 和业务
middleware。它没有复制 DeepAgents 内置能力，而是把自身代码集中在：

- 按 thread 获取或恢复隔离 sandbox；
- 根据调用身份加载获授权的服务端工具；
- 对模型调用次数、工具重试和超时进行确定性约束；
- 使用 `durability="sync"` 保存执行进度；
- 新消息通过 `multitask_strategy="interrupt"` 中断并续跑同一 thread；
- 通过 checkpoint TTL 清理过期运行状态。

重点源码：

- [`agent/server.py`](https://github.com/langchain-ai/open-swe/blob/main/agent/server.py)
- [`agent/dispatch.py`](https://github.com/langchain-ai/open-swe/blob/main/agent/dispatch.py)
- [`langgraph.json`](https://github.com/langchain-ai/open-swe/blob/main/langgraph.json)

当前项目应借鉴其运行预算、统一 dispatch 和授权后加载工具；不应照搬其庞大的
Slack、Linear、GitHub 集成，也不必仅为动态模型或 prompt 改成 graph factory。

### 3.2 Open Deep Research：固定流程使用显式图

该仓库把确定的研究阶段直接表达为嵌套图：

```text
clarify -> research brief -> supervisor
                           -> parallel researchers
                           -> compression -> final report
```

它分别定义 Agent、Supervisor、Researcher 的 state，通过 reducer 控制追加或覆盖，
并显式限制并发研究单元、supervisor 迭代数、单 researcher 工具调用次数和结构化
输出重试次数。领域质量由 Deep Research Bench 和 LangSmith experiment 验证。

重点源码：

- [`deep_researcher.py`](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py)
- [`configuration.py`](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/configuration.py)
- [`tests/run_evaluate.py`](https://github.com/langchain-ai/open_deep_research/blob/main/tests/run_evaluate.py)

当前项目只有在步骤顺序和验收阶段本身属于业务规则时才应使用这种显式图；一般
工具调用 Agent 继续使用 `create_agent` 或 `create_deep_agent` 更简单。

### 3.3 DeepAgents：把通用长任务能力留给上游

DeepAgents 在 LangChain `create_agent` 上组合 filesystem、skills、subagent、
summarization、memory、prompt caching 和 HITL middleware，并保护 filesystem 和
subagent 等必要 middleware 不被错误移除。

当前项目已经采用 DeepAgents，后续应主要增加业务工具、backend、安全边界和少量
业务 middleware，不应自行复制 todo、文件工具、subagent 调度或上下文压缩。

### 3.4 BigTool：工具可见性与可执行性分层

`langgraph-bigtool` 先把全部工具放入稳定 registry，并使用包含全部工具的
`ToolNode`。模型初始只看到 `retrieve_tools`；检索完成后，再把选中的工具 bind
给模型。工具数量再大，实际执行仍由已注册 ToolNode 完成。

这验证了当前项目的正确边界：

- 已知工具：构图时注册，请求期只做 allowlist/filter。
- 真正运行时发现工具：同时实现模型注入和工具调用阶段的执行代理。
- 只有工具数量达到几十或上百且选择准确率成为问题时，才增加语义工具检索。

### 3.5 UI 与多代理仓库

`agent-chat-ui` 直接使用 LangGraph SDK 管理 `assistantId`、`threadId`、state history、
custom UI events 和 interrupt 决策，适合作为 `runtime-web` 的协议参考。

CopilotKit 主要解决 LangGraph 到 AG-UI 的适配和生成式 UI，不是 Agent 后端模板。
`langgraph-swarm` 适合 Agent 间直接交接；`langgraph-supervisor` 适合中央调度，但其
官方 README 已建议多数新场景直接使用 tools 实现 supervisor，而不是默认依赖该库。

## 4. 当前 runtime-service 对照

### 4.1 已有正确基础

- `langgraph.json` 统一注册 graph 和 HTTP app。
- 公共业务输入通过 `RuntimeContext` 进入运行时。
- 模型、prompt 和工具筛选收敛到 `RuntimeRequestMiddleware`。
- 复杂长任务使用 DeepAgents，固定步骤流使用显式 `StateGraph`。
- `tools/registry.py` 作为公共工具 catalog 真源。

### 4.2 动态工具闭环实施状态

`research_agent` 在 `create_deep_agent` 时传入空工具集合，但在请求期间加载 Tavily
MCP；`test_case_service` 也会在请求期间加载知识 MCP。共享 middleware 现在会在
model-call 阶段公开获准动态工具，并在 tool-call 阶段按相同 runtime context 与
allowlist 重新解析、精确绑定真实工具；静态同名工具优先，执行期失效时 fail-closed。

LangChain 官方动态工具文档要求运行时发现工具同时实现：

1. `wrap_model_call`：让模型看到工具；
2. `wrap_tool_call`：为未预注册工具提供真实执行路径。

参考：[Dynamic tool selection](https://docs.langchain.com/oss/python/langchain/tools#dynamic-tool-selection)。

本地 scripted model + fake dynamic tool 已验证最终产生真实 `ToolMessage`。真实
Tavily、LightRAG 和生产 MCP 的连接、凭证、目录漂移与外部副作用仍属于 live 验收
边界，不纳入无 secret 的自动化测试。

### 4.3 推荐实现顺序

1. 已完成动态 MCP 工具的模型可见与执行闭环，以及真实 ToolNode/Agent 轨迹测试。
2. 为 Agent 增加明确的 model-call、tool-call、recursion、并发和超时预算。
3. 为生产 graph 与 demo graph 建立独立部署清单，收紧生产鉴权和 CORS。
4. 为研究和测试用例 Agent 建立领域数据集、轨迹断言和质量基准。
5. 评估 `runtime-web` 是否缺少 history、interrupt 和 artifact 的标准 SDK 行为。

这些事项不应塞进同一个实现批次。第一批只处理动态工具执行契约，避免同时修改
运行时、部署安全、前端和评测体系。

## 5. 推荐阅读顺序

1. `langgraph-bigtool`：先理解工具注册和动态可见性的边界。
2. `open-swe`：再理解生产 run、sandbox、权限和恢复。
3. `open_deep_research`：学习显式子图、并行和领域评测。
4. `agent-chat-ui`：核对 LangGraph SDK 的 thread/stream/HITL 交互。
5. `gpt-researcher`：补充研究质量和引用真实性评测。
