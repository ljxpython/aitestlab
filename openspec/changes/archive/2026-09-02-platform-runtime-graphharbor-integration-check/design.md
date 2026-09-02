## Context

`platform-api` 的 Runtime Gateway 已通过 `langgraph-sdk` 和 HTTP adapter 抽象上游 Agent Server，生产配置使用 `PLATFORM_API_LANGGRAPH_UPSTREAM_URL`。Runtime Service 的容器入口已经改为 GraphHarbor `serve`，并由独立 Worker、PostgreSQL 和 Redis 提供 Durable 执行。

当前缺口包括真实跨服务证据和 delegation 合同收口：真实 Platform API 请求必须完成 Platform access token 校验、项目权限检查、带 policy snapshot/scope/context hash 的 Runtime delegation JWT 签发，并被 GraphHarbor Auth 接收。

## Goals / Non-Goals

**Goals:**

- 使用真实运行中的 Platform API 和 GraphHarbor HTTP 服务完成最短链路验证。
- 验证 `/api/langgraph/info`、`/api/langgraph/graphs/search` 和 `/api/langgraph/threads` 经过 Platform Gateway 后仍可用。
- 验证 Platform 生成的 delegation token 能被 GraphHarbor 接受，并保留项目 scope。
- 将环境、命令、版本、结果和未覆盖边界写入 `verification.md`。

**Non-Goals:**

- 不新增 GraphHarbor 专用 adapter、业务路由或 Runtime 业务逻辑。
- 不实施 legacy/GraphHarbor 双 upstream、灰度、route ownership 或 rollback。
- 不在本变更中证明 Platform Web 链路、真实模型 Run、生产 SLO、Sandbox、远程 MCP 或观测服务端故障。

## Decisions

1. **测试入口使用真实 Platform API HTTP 地址**

   测试通过 `PLATFORM_RUNTIME_INTEGRATION=1` 显式开启，并从环境读取 `PLATFORM_API_BASE_URL`、`PLATFORM_API_ACCESS_TOKEN`、`PLATFORM_API_PROJECT_ID` 和 `PLATFORM_API_EXPECTED_UPSTREAM_URL`。不在测试中伪造 Platform middleware，也不把 access token 或 secret 写入仓库。

2. **先验证只读/创建边界，再验证执行链**

   测试依次调用 `/api/langgraph/info`、`/api/langgraph/graphs/search` 和 `/api/langgraph/threads`。这三步足以证明 Platform Gateway、delegation auth、project scope 和 GraphHarbor 协议入口连通；真实模型 Run 需要额外的模型 catalog/policy 和凭据，不作为这条最小兼容性测试的隐式前置条件。

3. **保持现有命名和 adapter**

   `LangGraphRuntimeGatewayUpstream`、`/api/langgraph` 和 `PLATFORM_API_LANGGRAPH_UPSTREAM_URL` 暂不改名。它们表达的是现有协议和历史 API 兼容面；改名会扩大 diff，且不能增加验证价值。GraphHarbor 通过相同的协议被配置为 upstream。

4. **失败和缺环境必须可区分**

   缺少任一显式测试环境变量时使用标准库 `unittest.SkipTest`，并输出缺失变量名；请求失败、401/403、项目 scope 错误或 GraphHarbor 协议不兼容必须失败，不能 skip。

5. **Delegation token 必须携带 Runtime Auth 合同**

   Platform 从已同步的 Runtime Catalog 和项目 Policy 计算允许模型/工具，生成稳定 policy revision，并签发 `policy_version`、`allowed_model_ids`、`allowed_tool_names`、`scope` 和 `context_hash`。没有可用模型目录时 fail-closed，不发放假默认模型。

## Risks / Trade-offs

- [Platform API 连接的是错误 upstream] -> 测试要求 `PLATFORM_API_EXPECTED_UPSTREAM_URL`，并通过 `/api/langgraph/info` 结果和运行配置记录确认目标地址；不把直连 GraphHarbor 当作 Platform Gateway 证据。
- [Platform access token 与项目数据不匹配] -> 使用已存在的 active 用户、active project 和项目成员关系；测试不自动创建或删除平台数据。
- [测试创建 Thread 产生残留数据] -> 使用带测试前缀的 metadata；测试不删除不属于自己的 Thread，清理策略由现有 Platform/Runtime 数据保留规则负责。
- [只读接口通过但 Run 执行仍不兼容] -> 明确本变更只关闭 Gateway 协议和 delegation auth 的最小链路；完整 Run/stream 仍由 R6 Durable 和后续 Platform 合同验收。

## Migration Plan

1. 添加环境门控测试和本变更 verification 记录。
2. 在隔离环境启动 GraphHarbor API/Worker/PG/Redis，并启动 Platform API，配置 Platform upstream URL 指向 GraphHarbor。
3. 运行测试并保存脱敏结果。
4. 测试失败时不改变任何服务数据；删除测试文件即可回滚本变更。

## Open Questions

- Platform API 的长期配置字段是否从 `LANGGRAPH_UPSTREAM_*` 迁移为 provider-neutral 名称，留给独立配置治理变更决定。
- 真实 Run/stream 是否纳入 Platform Gateway 的下一条 governed integration，需要另行冻结模型 catalog、delegation context 和 Run 事件契约。
