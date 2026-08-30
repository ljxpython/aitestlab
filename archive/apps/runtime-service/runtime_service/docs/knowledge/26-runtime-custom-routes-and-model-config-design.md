# Runtime Custom Route 与模型配置边界设计

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `12-runtime-context-and-local-debug-architecture.md`、
> `13-runtime-service-target-code-layout.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `22-platform-runtime-contract-design.md`、
> `24-package-langgraph-startup-shutdown-design.md`、
> `25-runtime-testing-and-cross-service-contract-design.md`

## 1. 本次结论

本次 Runtime Service 重构不新增 Custom Route，也不在 Runtime 建设模型配置中心。

```text
Platform API
  -> 保存模型目录、项目/Assistant 默认模型、允许模型和用户权限
  -> 校验请求并生成本次 Run 的配置快照
  -> 透传 RuntimeContext + Delegation Token

Runtime Service
  -> 验证 Token 和 RuntimeContext
  -> 按本地执行能力再次校验 model_id
  -> modeling.py 创建 ChatModel
  -> 执行 Graph
```

Runtime 不提供模型配置 CRUD，不反向调用 Platform API 获取配置，也不接受客户端直接提交的
权限、模型白名单或 Provider 凭据。

## 2. Custom Route 的定位

LangGraph Agent Server 已提供 Graph、Thread、Run、Checkpoint、Interrupt、Resume 和 Stream
接口。Custom Route 只有在存在明确的非 LangGraph 协议或 Runtime 专属只读诊断需求时才考虑。

本次不创建：

- `custom_routes/` 包；
- `/models`、`/model-config` 等配置管理接口；
- `/debug/run` 等第二套执行接口；
- Route Registry、HTTP Builder 或 Debug Server。

如果未来确实需要 Custom Route，最多增加一个经过评审的 `http_app.py`，并通过
`langgraph.json.http.app` 挂载。路由必须使用 `/internal/*` 或明确业务前缀，不能覆盖
`/threads`、`/runs`、`/assistants`、`/info`、`/ok` 等 Agent Server 默认路由。

## 3. 模型配置职责

### 3.1 Platform API 控制面

Platform API 管理：

- Model Catalog；
- Project / Assistant 默认模型；
- 允许使用的模型集合；
- 用户是否可以覆盖模型；
- 生成参数上限；
- 配置变更审计；
- Run 启动时的不可变配置快照。

前端只访问 Platform API，修改配置和启动 Run 都不直接访问 Runtime。

### 3.2 Runtime Service 执行面

Runtime Service 只保留：

- Service `AgentDefaults`；
- 本地允许执行的 model_id；
- Provider credentials；
- `model_id -> ChatModel` 的明确映射；
- RuntimeContext 和 RuntimePolicy 的严格校验。

Provider 凭据只从 Runtime 环境或 Secret Store 读取，不能进入 Platform JSON、Thread metadata、
事件或日志。

Run 请求使用 14 号文档定义的 `context`：

```json
{
  "assistant_id": "reference_agent",
  "context": {
    "model_id": "openai:gpt-5.5",
    "temperature": 0.2,
    "max_tokens": 4096,
    "tools": null
  },
  "config": {
    "configurable": {
      "thread_id": "thread-123"
    }
  }
}
```

`model_id` 属于 RuntimeContext，不放入 `configurable`。Runtime resolver 仍要对 Platform
传入的候选值执行本地 fail-closed 校验；Platform 权限检查不能替代 Runtime 的执行能力检查。

模型配置改变只影响后续 Run，进行中的 Run 继续使用启动时的配置快照。

## 4. 前后端调用链

```text
Platform Web
    -> Platform API: 读取/修改模型配置
    -> Platform API: 鉴权、策略检查、生成 Run snapshot
    -> Runtime Service: Protocol v2 + Delegation Token
        -> auth/platform.py
        -> RuntimeContext resolver
        -> RuntimeConfig Middleware
        -> get_agent(config)
        -> Graph / Model / Tool execution
```

生产环境不允许浏览器绕过 Platform API 直接调用 Runtime。Runtime 只接受 Platform 注入的
可信身份和受控配置。

## 5. Open SWE 可借鉴点

Open SWE 在 `langgraph.json` 中使用 `http.app = agent.webapp:app`，由 FastAPI 组合 Dashboard、
Webhook、Plan 和 Health 路由；`agent.server.get_agent()` 再按 Thread、Profile 和 Team 默认值
解析模型并调用 `make_model(...)`。

本项目借鉴：

- Graph 入口和 HTTP App 可以由 LangGraph 配置组合；
- 模型在 `get_agent(config)` 执行期解析；
- 本地模型凭据由环境提供；
- FastAPI lifespan 负责必要的启动检查和资源释放。

本项目不复制：

- Open SWE 的 Dashboard、Webhook 和业务路由；
- 在 Runtime 内维护 Team/Profile 模型配置；
- 通过 Custom Route 代替 Platform 控制面。

参考：<https://docs.langchain.com/langsmith/custom-routes>

## 6. Runtime 独立开发与调试

不启动 Platform API 也可以开发 Runtime：

1. 使用 `.env` 提供本地 Provider 凭据和默认模型；
2. 使用本地短期 Delegation Token；
3. 启动 `langgraph dev --config ./langgraph.json`；
4. 通过 LangGraph SDK 或 curl 调用标准 Thread / Run / Stream 接口；
5. 用 fake ChatModel 做确定性 Unit、Composition 和 Integration 测试；
6. 用单独模型 smoke 脚本验证真实 Provider 连通性。

本地调试请求仍然使用同样的 `RuntimeContext` 结构。只是在没有 Platform API 时，由本地脚本
生成最小合法 Token 和配置快照；不添加 `/debug` 绕过正式认证和解析链路。

## 7. 未来重新评估 Custom Route 的条件

只有出现以下真实需求，才重新设计 Custom Route：

- 前端需要非 LangGraph 的流式协议适配；
- Runtime 有无法放入 Graph Tool 的只读诊断接口；
- 外部系统必须向 Runtime 发送专属协议，且 Platform API 不适合承接。

届时仍须单独评审路由 Auth、幂等、错误信封、CORS、事件关联和 `langgraph.json.http.app`，
不能直接把业务接口塞进 Runtime。
