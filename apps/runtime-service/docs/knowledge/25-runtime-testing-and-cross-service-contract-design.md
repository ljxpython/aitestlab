# Runtime 测试目录与跨服务契约测试设计

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `11-agent-service-directory-architecture.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `18-open-swe-to-runtime-event-and-run-explorer-design.md`、
> `22-platform-runtime-contract-design.md`、
> `23-graph-thread-backend-checkpoint-lifecycle-design.md`、
> `24-package-langgraph-startup-shutdown-design.md`

## 1. 目标与边界

测试体系只证明 Runtime Service 的真实行为和 Platform API / Runtime Service 的稳定边界，
不为旧目录保留兼容测试，也不通过测试反向维护旧架构。

目标按以下顺序推进：

```text
Unit -> Composition -> Cross-service Contract -> Agent Server Integration -> Durable -> E2E
```

快速测试必须可在本地、无真实模型、无 PostgreSQL、无 Redis、无外部 Sandbox 的条件下运行。
真实模型和真实基础设施测试单独执行，不阻塞普通提交反馈，但 E2E 门禁本身不允许用 fake model
冒充真实模型通过。

## 2. Open SWE 借鉴边界

### 2.1 借鉴

- 使用 `pytest`、`pytest-asyncio` 和 `uv`，并开启 `asyncio_mode = "auto"`；
- `tests/` 放在 Package 外部，按 `agent`、`middleware`、`tools`、`sandbox`、`auth` 等领域拆分；
- 默认测试以 Unit 为主，Integration / E2E 单独执行；
- 对 `get_agent(config)` 做装配测试，验证 Agent 类型、工具集合、Backend、Subagent 和
  Middleware 顺序；
- 用 fake model、fake client、fake backend 替换外部边界，但保留被测 Agent 组合逻辑；
- 增加 import hygiene 测试，防止入口加载不必要的重依赖；
- 对 Durable Run 默认值、Sandbox 准备、权限和失败语义写行为测试；
- 快速 E2E 可以模拟外部 SaaS，但模型行为 E2E 必须使用真实模型，尽量真实运行 Agent、Middleware、Tool 和服务入口；
- Prompt 测试验证渲染、组合、优先级或实际行为，不断言静态文本存在即可。

### 2.2 不照搬

- Slack、GitHub、Linear、PR 和 Electron 的业务测试；
- Open SWE 特有的 Sandbox 状态管理和 Dashboard 业务；
- 为了契约测试引入 Pact 等新框架；
- 让 Platform API 和 Runtime Service 调用同一份生产解析函数，造成自测自夸；
- 为尚未存在的 Provider、Subagent 或外部服务预留测试脚手架。

## 3. Runtime Service 测试目录

新架构统一使用：

```text
apps/runtime-service/
├── src/
│   └── runtime_service/
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── runtime.py
    │   ├── graphs.py
    │   └── auth.py
    ├── runtime/
    │   ├── test_contracts.py
    │   ├── test_resolver.py
    │   ├── test_modeling.py
    │   └── test_errors.py
    ├── middleware/
    │   ├── test_context_validation.py
    │   ├── test_middleware_order.py
    │   ├── test_tool_error.py
    │   └── test_run_finalizer.py
    ├── graphs/
    │   ├── test_graph_entries.py
    │   ├── test_graph_introspection.py
    │   └── test_langgraph_config.py
    ├── integration/
    │   ├── test_agent_runtime.py
    │   ├── test_stream_events.py
    │   ├── test_interrupt_resume.py
    │   └── test_backend_reconnect.py
    ├── durable/
    │   ├── test_checkpoint_resume.py
    │   ├── test_worker_restart.py
    │   └── test_run_cancel.py
    ├── contracts/
    │   ├── test_platform_payload.py
    │   ├── test_delegation_claims.py
    │   ├── test_error_mapping.py
    │   └── test_event_sequence.py
    └── services/
        └── reference_agent/
            ├── test_agent.py
            ├── test_tool_assembly.py
            └── test_subagent_assembly.py
```

规则：

1. 新测试放在 `apps/runtime-service/tests/`，不放入 `src/runtime_service/`。
2. 旧的 `runtime_service/tests/` 属于 Legacy，不纳入新架构维护范围。
3. 目录只有在出现对应行为时才创建，不提前生成空测试模块。
4. 测试文件按领域命名，Service 自有测试放在 `tests/services/<service_name>/`，禁止出现一个
   覆盖所有 Runtime 行为的巨型测试文件。

## 4. 测试层级与责任

### 4.1 Unit

覆盖 `contracts.py`、`resolver.py`、`modeling.py`、Runtime 异常和独立 Middleware。

重点验证：

- 不可变 Runtime 类型和字段边界；
- 默认值、字段拒绝、Policy 收缩和 hash 稳定性；
- `tools=None`、`tools=()`、非空 tools 的三态语义；
- 错误类型到稳定错误码的映射；
- Middleware 的输入、输出、异常和清理行为。

### 4.2 Composition

不启动真实 Agent Server，直接调用 Service 的 `get_agent(config)` 并捕获官方构造函数参数，
验证：

- 返回值是 `Pregel` 或已编译图；
- `create_agent`、`create_deep_agent` 或 `StateGraph.compile()` 选择正确；
- 工具是显式列表，没有自动扫描；
- Middleware 顺序和配置正确；
- Subagent 使用显式定义的缩权配置；
- 静态 Graph 不因普通 Run 配置重复构建。

### 4.3 Agent Server Integration

使用真实 `langgraph.json` 和本地 Agent Server，验证：

- Graph entrypoint 可导入；
- `/info` 或等价 introspection 不创建昂贵资源；
- `run.start`、`input.respond`、cancel 和 SSE 可用；
- `thread_id`、`context`、`configurable` 的映射符合 14、22 号文档；
- `stream_subgraphs` 时 Subagent namespace 稳定；
- 鉴权失败在建立 SSE 前返回 HTTP 错误。

### 4.4 Durable

只在独立环境验证生产级基础设施：

- Checkpoint 保存、恢复和指定 `checkpoint_id`；
- Interrupt 后精确恢复；
- Worker 重启后 Run 可继续或被明确标记为 abandoned；
- cancel、断线和 graceful shutdown 语义；
- Thread、Backend、Checkpoint 的作用域不会串线。

### 4.5 E2E

遵循 Open SWE 的边界替换方式，但把模型真实度作为独立门禁：Agent Service、Middleware、工具、
LangGraph 入口和本地隔离 Backend 尽量真实；涉及模型协议、输出格式、工具选择或多模态行为的
E2E 必须使用真实模型。文本模型固定使用 DeepSeek 中转，多模态模型固定使用 GPT 中转，凭据从
本机 `.env` 或 CI Secret 注入。未设置 `RUNTIME_E2E=1` 时测试只做快速 fake model 验证；设置后
缺少凭据必须失败并明确报告未执行，不得静默降级。首期不建设 Playwright、Electron 或业务 SaaS
的完整复制品。

## 5. 跨服务契约的单一事实源

Platform API 与 Runtime Service 共享的可执行样例放在仓库级目录：

```text
contracts/
└── runtime-v1/
    ├── run_start_minimal.json
    ├── run_start_context_null.json
    ├── run_start_tools_empty.json
    ├── run_start_tools_override.json
    ├── run_start_invalid.json
    ├── delegation_claims.json
    ├── errors/
    │   ├── invalid_context.json
    │   ├── forbidden.json
    │   ├── thread_not_found.json
    │   └── run_conflict.json
    └── events/
        ├── run_started.json
        ├── tool_call.json
        ├── interrupt.json
        └── run_terminal.json
```

Fixtures 是人工审查的契约向量，不由被测 Pydantic 模型自动生成。两端必须独立读取同一向量，
不能通过调用对方的内部 Python 函数来“验证”。

## 6. 两端验证职责

### 6.1 Platform API

- 生成符合 Protocol v2 的请求；
- 从可信上下文生成 Delegation Token claims；
- 移除客户端提交的 tenant、project、user、role、permissions 等身份字段；
- 正确处理 `Idempotency-Key` 和请求摘要；
- 将 Runtime 错误转换成 Platform 错误信封；
- 保留 request、thread、run、assistant 的关联字段。

### 6.2 Runtime Service

- 接受合法 `run.start`、`input.respond` 和 cancel 请求；
- 拒绝未知字段、非法类型、错误 scope 和过期 Token；
- 按 14 号文档解析 `context.tools` 三态语义；
- 将 Delegation Token 映射成 `RuntimePrincipal` 和 `RuntimePolicy`；
- 返回稳定错误码和脱敏错误摘要；
- 不把 secret、完整 Prompt、Authorization 或敏感工具参数写入事件和日志。

## 7. 必须覆盖的契约向量

1. 最小合法 `run.start`；
2. `context` 缺省和 `null`；
3. `context.tools = []`；
4. `context.tools = ["tool_a"]`；
5. 未知 context 字段和非法类型；
6. 缺失或冲突的 `thread_id`；
7. 不属于当前项目的 `assistant_id`；
8. Token 签名错误、过期、audience 错误和 project scope 错误；
9. 客户端伪造身份、权限或凭据字段；
10. 非法 `durability`、`stream_resumable`、`on_disconnect`；
11. `run.cancel` 和 `input.respond`；
12. 相同幂等键和相同请求摘要只产生一个 Run；
13. 相同幂等键但请求摘要不同返回冲突；
14. Runtime 错误映射为 Platform 错误信封；
15. 敏感字段在事件和日志中被脱敏。

幂等记录的事实源是 Platform API。Runtime 不再实现第二套 Durable Run 去重，只验证接收到的
请求和关联 metadata 不被篡改。

## 8. 事件顺序与终态测试

事件测试同时验证 JSON 结构和时序：

```text
run.accepted
  -> run.started
  -> model.started
  -> tool.started
  -> tool.completed
  -> model.completed
  -> run.completed
```

失败或取消时以 `run.failed`、`run.cancelled` 之一作为唯一终态。必须保证：

- `seq` 单调递增；
- 一个 Run 只有一个终态；
- 终态之后没有普通事件；
- SSE 使用 `since` 能继续读取；
- Subagent 事件带稳定 namespace；
- Stream 断开不会被误判为 Run 取消。

## 9. 命令与 CI 分层

建议 Runtime Service 提供以下最小命令：

```bash
# 默认快速测试
uv run pytest tests -m "not integration and not durable and not e2e"

# Agent Server 集成测试
uv run pytest tests/integration -m integration

# Durable 测试
uv run pytest tests/durable -m durable

# Runtime 侧契约测试
uv run pytest tests/contracts

# Platform 侧契约测试
cd ../platform-api
uv run pytest tests/contracts

# 完整 E2E
RUNTIME_E2E=1 uv run pytest tests/e2e -m e2e
```

普通 CI 默认运行 Unit、Composition 和 Cross-service Contract。真实 Agent Server、数据库、
Worker Restart 和外部依赖测试进入独立 job。

首期只使用 `pytest`、`pytest-asyncio`、`httpx`、LangGraph SDK、fake ChatModel、fake Backend
和测试专用 `InMemorySaver`。不为测试新增契约框架或自定义测试运行时。

## 10. 实施顺序与验收门槛

1. 先创建新测试目录和最小 `conftest.py`，不迁移旧测试；
2. 为 `contracts.py`、`resolver.py`、`modeling.py` 建立 Unit 测试；
3. 为第一个 Reference Agent 建立 `get_agent` 装配和 import hygiene 测试；
4. 固化 `contracts/runtime-v1` fixtures，并在 Platform、Runtime 两端分别验证；
5. 启动本地 Agent Server，补齐 Protocol v2、SSE 和鉴权集成测试；
6. 具备真实 Checkpoint 基础设施后再开启 Durable job；
7. 最后建设少量跨边界 E2E，不把业务系统复制进 Runtime 测试目录。

完成阶段 0 和阶段 2 的最小验收前，不进入大规模 Agent、Tool、Backend 重构。任何测试失败
必须能定位到 Runtime、Platform、协议适配或外部基础设施中的一个明确边界。
