# `create_agent(...)` 参数学习笔记

## 1. 先说结论

`create_agent(...)` 本质上就是帮你生成一个“模型调用 + 工具循环 + 可插 middleware + 可挂状态/上下文/schema”的编译后 graph。

最常见、最重要的参数就这么几类：

- 模型与工具
- 提示词
- 中间件
- 结构化输出
- 状态 schema
- 上下文 schema
- 持久化能力
- 中断 / 调试能力

如果只记一句话：
`response_format` 管结果格式，`state_schema` 管状态，`context_schema` 管运行时上下文。

## 2. 官方函数签名

本地当前环境里 `langchain.agents.create_agent` 的签名如下：

```python
(model, tools=None, *,
 system_prompt=None,
 middleware=(),
 response_format=None,
 state_schema=None,
 context_schema=None,
 checkpointer=None,
 store=None,
 interrupt_before=None,
 interrupt_after=None,
 debug=False,
 name=None,
 cache=None)
```

## 3. 参数逐个看

### 3.1 `model`

作用：

- 指定 agent 使用哪个 chat model

可传：

- 模型字符串
- 已初始化的 chat model 实例

典型写法：

```python
agent = create_agent(
    model="openai:gpt-4.1",
    tools=[...],
)
```

在本仓库里，一般不是直接写死，而是先经过：

- [modeling.py](../../runtime/modeling.py)
- [runtime_request_resolver.py](../../runtime/runtime_request_resolver.py)

### 3.2 `tools`

作用：

- 给 agent 提供可调用工具

可传：

- `BaseTool`
- 普通 callable
- tool dict

如果不传工具：

- agent 就只有模型节点，没有工具调用循环

### 3.3 `system_prompt`

作用：

- 作为系统消息加到对话最前面

适合放：

- 角色设定
- 输出要求
- 风险约束
- 业务目标

不适合放：

- 每次 run 都变化的业务字段
- 用户身份和项目上下文

这些更适合放 `context`，再由动态 prompt 或 graph 逻辑消费。

### 3.4 `middleware`

作用：

- 在 agent 生命周期不同阶段拦截和增强行为

典型用途：

- HITL
- 多模态
- 动态 prompt
- 工具请求改写
- 运行时补字段
- 审计和日志

本仓库已经大量在用：

- [MultimodalMiddleware](../../middlewares/multimodal/middleware.py)
- `HumanInTheLoopMiddleware`
- `ToolRuntimeContextSanitizerMiddleware`

### 3.5 `response_format`

作用：

- 让 agent 产出结构化结果

官方 docstring 里说明它可以接：

- `ToolStrategy`
- `ProviderStrategy`
- Pydantic model class
- schema dict

一句话理解：
它管的是“最终回答长什么结构”。

典型适合：

- 你要稳定 JSON 输出
- 你要把 agent 输出直接落数据库
- 你要做接口契约

不适合：

- 想靠它替代 state
- 想靠它替代运行时 context

这个是很多人一开始最容易搞混的地方。

### 3.6 `state_schema`

作用：

- 定义 agent graph state 的结构

官方 docstring 的意思是：

- 它会替换默认的 `AgentState`
- 允许你扩展 state 字段
- 更适合用于“状态结构扩展”

一句话理解：
`state_schema` 管“运行过程中图里保存什么状态”。

本仓库例子：

- [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)
  - `state_schema=MultimodalAgentState`

这个用法是合理的，因为多模态处理中间件确实需要额外 state。

### 3.7 `context_schema`

作用：

- 定义 runtime context 的结构

一句话理解：
`context_schema` 管“调用方在运行时额外塞进来的业务上下文长什么样”。

适合放：

- `user_id`
- `tenant_id`
- `project_id`
- `model_id`
- `system_prompt`
- 运行开关

不适合放：

- 对话 messages
- 中间状态
- checkpoint 数据

在本仓库里，最该接这个的是：

- [RuntimeContext](../../runtime/context.py)

目前更贴标准的写法在这里：

- [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)
- [research_agent/graph.py](../../agents/research_agent/graph.py)
- [test_case_service/graph.py](../../services/test_case_service/graph.py)

### 3.8 `checkpointer`

作用：

- 保存单线程内的 graph state

典型用途：

- 对话记忆
- 中断恢复
- thread 级持久化

一句话：
`checkpointer` 管“同一个 thread 的短期记忆和恢复”。

### 3.9 `store`

作用：

- 跨线程持久化数据

典型用途：

- 长期记忆
- 跨会话共享数据
- 用户级资料存储

一句话：
`store` 管“跨线程、跨会话”的长期数据。

### 3.10 `interrupt_before` / `interrupt_after`

作用：

- 在指定节点前后中断

适合：

- 人工审批
- 人工观察
- 调试关键节点

不过在本仓库里，更常见的是直接用 middleware 或 `interrupt(...)` 风格，而不是大面积手配这两个。

### 3.11 `debug`

作用：

- 打开详细执行日志

适合：

- 调试 middleware
- 观察状态流转
- 排查 agent 执行路径

不建议默认常开，不然日志会很吵。

### 3.12 `name`

作用：

- 给编译后的 graph 命名

这在多 agent / subgraph 场景里很有用，尤其要区分流式输出来源时。

### 3.13 `cache`

作用：

- 给 graph 执行加缓存

这个不是当前仓库的重点，先知道有这玩意就行。

## 4. 三个最容易混的参数

### 4.1 `response_format` 不是 `state_schema`

- `response_format`
  - 约束最终输出格式
- `state_schema`
  - 约束 graph 内部状态结构

### 4.2 `context_schema` 不是 `state_schema`

- `context_schema`
  - 调用方运行时传入
  - 不属于状态
- `state_schema`
  - graph 自己运行过程中维护

### 4.3 `system_prompt` 不是 `context`

- `system_prompt`
  - 模型系统消息
- `context`
  - 业务运行时上下文

如果每次 run 都把项目 ID、租户信息、生效开关硬拼进 `system_prompt`，时间久了就会一团糟。

## 5. 一个推荐组合

对你们 `runtime_service` 来说，比较稳的组合通常是：

```python
return create_agent(
    model=model,
    tools=tools,
    middleware=[...],
    system_prompt=system_prompt,
    state_schema=CustomAgentState,
    context_schema=RuntimeContext,
    name="assistant",
)
```

这套组合的含义很清楚：

- 模型和工具决定“能做什么”
- `system_prompt` 决定“默认怎么说”
- `middleware` 决定“怎么拦和增强”
- `state_schema` 决定“状态长什么样”
- `context_schema` 决定“调用方能传什么上下文”

## 6. 回到你当前的 assistant graph

当前 [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)：

- `middleware` 用得没问题
- `state_schema=MultimodalAgentState` 也没问题
- 最大缺口是没传 `context_schema=RuntimeContext`

所以它现在是：

- 多模态状态有了
- 运行时 typed context 没正式接上

这就是为什么我前面说它“能跑，但不够标准”。

## 7. 学完这一篇后你应该记住什么

最关键就三句话：

- `response_format` 管输出格式
- `state_schema` 管内部状态
- `context_schema` 管运行时上下文

把这三个不再混掉，后面你改架构就顺很多。

## 8. 参考资料

- LangChain Agents
  - https://docs.langchain.com/oss/python/langchain/agents
- LangChain Structured output
  - https://docs.langchain.com/oss/python/langchain/structured-output
- 本地 `create_agent` 签名与 docstring
  - `apps/runtime-service/.venv` 当前安装版本实测
- 本仓库参考实现
  - [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)
  - [research_agent/graph.py](../../agents/research_agent/graph.py)
  - [test_case_service/graph.py](../../services/test_case_service/graph.py)
