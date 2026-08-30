# runtime_service 标准重构蓝图（伪代码）

> 历史讨论：本文不作为新 Runtime 实现依据。新架构契约以
> `14-runtime-contracts-and-resolution-design.md` 为准；本文的 Tool Registry、旧字段和
> 多层 RuntimeRequest 方案均已废弃。

> 本文档只回答一件事：如果现在不管兼容，按官方推荐和最小复杂度重做，`runtime_service` 应该长什么样。

## 1. 总结版结论

推荐方案不是“纯 middleware 一把梭”，也不是“middleware + service + manager + factory + adapter”这种脑残分层。

最推荐的是：

- 一个公共 `RuntimeRequestMiddleware`
- 一个最薄的 `resolver helper`
- graph 顶层静态导出
- `RuntimeContext` 只放公共业务字段
- `tools/registry.py` 只做公开可选工具 catalog
- graph 自己保留少量本地必备工具

也就是：

```text
request.runtime.context
  -> RuntimeRequestMiddleware
  -> resolve_runtime_request(...)
  -> request.override(model/system_message/tools)
  -> create_agent(...) / create_deep_agent(...)
```

## 2. “纯 middleware” 和 “middleware + resolver helper” 是什么意思

### 2.1 纯 middleware

意思是把这些逻辑全塞进一个 middleware 类里：

- 读 `RuntimeContext`
- 校验字段
- 合并 graph 默认值
- 解析模型
- 解析工具
- 生成最终 system prompt
- `request.override(...)`

优点：

- 文件少
- 初看很直接

缺点：

- middleware 很快会发胖
- 纯计算逻辑和 LangChain 生命周期强耦合
- 单元测试难写
- graph 默认值、工具 registry、模型解析全揉在一起

### 2.2 `middleware + resolver helper`

意思是只保留两层：

1. `RuntimeRequestMiddleware`
2. `resolve_runtime_request(...)`

职责分工：

- middleware 只负责接 LangChain 生命周期、读 `request.runtime.context`、调用 helper、最后 `request.override(...)`
- helper 只负责纯计算：校验、合并默认值、解析模型、解析工具、生成最终运行时结果

这是我最推荐的方式，因为：

- 比纯 middleware 更好测
- 比一堆 manager/service/factory 更简单
- 符合官方把动态行为放在 middleware 的思路
- 同时保留最小的纯函数解析层，不会把所有逻辑焊死在请求对象上

## 3. 推荐目录形态

按奥卡姆剃刀，先别搞 package 套 package。

推荐最小目录：

```text
runtime_service/
  middlewares/
    runtime_request.py
  runtime/
    context.py
    runtime_request_resolver.py
  tools/
    registry.py
```

说明：

- `middlewares/runtime_request.py`：只放公开 middleware
- `runtime/runtime_request_resolver.py`：只放解析 helper 和返回类型
- `tools/registry.py`：只放公开工具 catalog 与实例解析

## 4. 最终 `RuntimeContext` 公共字段

不考虑兼容时，`RuntimeContext` 就收成这一版，不再夹带私货：

```python
@dataclass(frozen=True)
class RuntimeContext:
    # trusted injected
    user_id: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    project_id: str | None = None

    # run-level business inputs
    model_id: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    enable_tools: bool | None = None
    tools: list[str] | None = None
```

明确移除：

- `environment`
- `skills`
- `subagents`

原因：

- `environment` 属于部署默认值，不是公开运行时业务字段
- `skills/subagents` 属于 deepagent 内部能力，不进入 v1 公共 contract

## 5. graph 默认值结构

每个 graph 只保留自己的业务默认值，不再自己到处解析 `config/configurable/env`。

推荐：

```python
@dataclass(frozen=True)
class AgentDefaults:
    model_id: str
    system_prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    enable_tools: bool = True
    public_tools: tuple[str, ...] = ()
```

assistant 示例：

```python
ASSISTANT_DEFAULTS = AgentDefaults(
    model_id="openai:gpt-4.1",
    system_prompt=resolve_assistant_system_prompt(SYSTEM_PROMPT, demo_enabled=True),
    temperature=0.2,
    enable_tools=True,
    public_tools=("web_search", "mcp:browser"),
)
```

## 6. `tools/registry.py` 最推荐的 catalog 结构

别把 registry 做成一坨 if/else，也别让 graph 到处自己拼工具。

推荐把它收成“公开能力目录”：

```python
ToolResolver = Callable[[], Awaitable[list[BaseTool]]]


@dataclass(frozen=True)
class ToolCapability:
    name: str
    kind: Literal["builtin", "mcp_server"]
    description: str
    resolver: ToolResolver
```

```python
TOOL_CATALOG: dict[str, ToolCapability] = {
    "web_search": ToolCapability(
        name="web_search",
        kind="builtin",
        description="Search the web",
        resolver=resolve_web_search_tools,
    ),
    "mcp:browser": ToolCapability(
        name="mcp:browser",
        kind="mcp_server",
        description="Browser MCP tools",
        resolver=resolve_browser_mcp_tools,
    ),
}
```

对外 API：

```python
def get_tool_catalog() -> dict[str, ToolCapability]:
    return TOOL_CATALOG


async def resolve_public_tools(tool_names: Sequence[str]) -> list[BaseTool]:
    resolved: list[BaseTool] = []
    seen: set[str] = set()

    for name in tool_names:
        key = normalize_tool_name(name)
        if key not in TOOL_CATALOG:
            raise ValueError(f"Unsupported tool: {key}")
        if key in seen:
            continue
        seen.add(key)
        resolved.extend(await TOOL_CATALOG[key].resolver())

    return resolved
```

### 6.1 一个关键边界

`tools/registry.py` 只管理“公开可选工具”。

graph 本地必备工具不要混进去：

```python
ASSISTANT_REQUIRED_TOOLS = [
    lookup_internal_knowledge,
    draft_release_plan,
    send_demo_email,
    submit_high_impact_action,
]
```

这样边界最清楚：

- graph-required tools：graph 自己静态持有
- public optional tools：registry 动态解析

## 7. 运行时解析 helper 伪代码

helper 只做纯计算，不碰 LangChain hook。

```python
@dataclass(frozen=True)
class ResolvedRuntimeRequest:
    model: BaseChatModel
    system_prompt: str
    tools: list[BaseTool]


async def resolve_runtime_request(
    *,
    context: RuntimeContext,
    defaults: AgentDefaults,
    required_tools: Sequence[BaseTool],
) -> ResolvedRuntimeRequest:
    model_id = context.model_id or defaults.model_id
    system_prompt = context.system_prompt or defaults.system_prompt
    temperature = context.temperature if context.temperature is not None else defaults.temperature
    max_tokens = context.max_tokens if context.max_tokens is not None else defaults.max_tokens
    top_p = context.top_p if context.top_p is not None else defaults.top_p

    model = resolve_model_by_id(model_id)
    model = apply_model_params(
        model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )

    enable_tools = (
        context.enable_tools
        if context.enable_tools is not None
        else defaults.enable_tools
    )
    requested_public_tools = context.tools or list(defaults.public_tools)
    optional_tools = (
        await resolve_public_tools(requested_public_tools)
        if enable_tools
        else []
    )

    return ResolvedRuntimeRequest(
        model=model,
        system_prompt=system_prompt,
        tools=[*required_tools, *optional_tools],
    )
```

要求：

- 非法 `model_id` 直接报错
- 非法 `tools` 直接报错
- 不从 `config.configurable` 回读公共业务字段
- 不在这里处理 deepagent 的 `skills/subagents`

## 8. 公共 middleware 伪代码

middleware 只负责接请求，再把 helper 结果喂回去。

```python
class RuntimeRequestMiddleware(AgentMiddleware):
    def __init__(
        self,
        *,
        defaults: AgentDefaults,
        required_tools: Sequence[BaseTool],
    ) -> None:
        self.defaults = defaults
        self.required_tools = list(required_tools)

    async def awrap_model_call(self, request, handler):
        runtime_context = request.runtime.context or RuntimeContext()

        resolved = await resolve_runtime_request(
            context=runtime_context,
            defaults=self.defaults,
            required_tools=self.required_tools,
        )

        next_request = request.override(
            model=resolved.model,
            tools=resolved.tools,
            system_message=SystemMessage(content=resolved.system_prompt),
        )
        return await handler(next_request)
```

### 8.1 middleware 顺序

assistant 里推荐顺序：

1. `RuntimeRequestMiddleware`
2. `HumanInTheLoopMiddleware`
3. `MultimodalMiddleware`

原因：

- `RuntimeRequestMiddleware` 先确定本次调用的基础 model / tools / system prompt
- 后续 middleware 再在这个基础上追加审核或多模态增强
- 反过来排，后面的 middleware 很容易把前面的 `system_message` 覆盖掉

## 9. `assistant_agent` 标准样板伪代码

这才是我最推荐的 `assistant_agent` 形态：

```python
ASSISTANT_REQUIRED_TOOLS = [
    lookup_internal_knowledge,
    draft_release_plan,
    send_demo_email,
    submit_high_impact_action,
]


ASSISTANT_DEFAULTS = AgentDefaults(
    model_id="openai:gpt-4.1",
    system_prompt=resolve_assistant_system_prompt(SYSTEM_PROMPT, demo_enabled=True),
    temperature=0.2,
    enable_tools=True,
    public_tools=("web_search",),
)


BASELINE_MODEL = resolve_model_by_id(ASSISTANT_DEFAULTS.model_id)


graph = create_agent(
    model=BASELINE_MODEL,
    tools=ASSISTANT_REQUIRED_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=ASSISTANT_DEFAULTS,
            required_tools=ASSISTANT_REQUIRED_TOOLS,
        ),
        HumanInTheLoopMiddleware(...),
        MultimodalMiddleware(),
    ],
    context_schema=RuntimeContext,
    state_schema=MultimodalAgentState,
    name="assistant",
)
```

重点：

- 顶层直接静态导出 `graph`
- 不再导出 `make_graph`
- graph 内不自己手搓 runtime 解析
- graph 本地必备工具静态写死
- 公开可选工具走 registry
- run-level 动态行为全走 `RuntimeRequestMiddleware`

## 10. deepagent / test_case_service 的同一原则

即便换成 `create_deep_agent(...)`，原则也不变：

```python
graph = create_deep_agent(
    model=BASELINE_MODEL,
    tools=DEEPAGENT_REQUIRED_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(...),
        MultimodalMiddleware(),
    ],
    context_schema=RuntimeContext,
    memory=[...],
    skills=[...],      # 静态
    subagents=[...],   # 静态
)
```

关键点：

- `skills/subagents` 还是静态
- 不进入公开 runtime contract
- 公开动态输入仍然只走 `RuntimeContext`

## 11. 我最推荐的最终结论

一句话版：

- 不要纯 middleware 一坨写死
- 也不要搞多层 manager/service/factory 套娃
- 就用“一个公共 middleware + 一个 resolver helper + 一个公开 tool registry + graph 静态导出”

这是当前最符合官方范式、也最符合你要的简单可控方案。
