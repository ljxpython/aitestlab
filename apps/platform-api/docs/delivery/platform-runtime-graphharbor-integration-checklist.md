# Platform API -> GraphHarbor 真实联调清单

这份清单证明的是：真实的 `platform-api` HTTP 请求经过 Platform access token、项目权限和
按操作 scope 签发的 Runtime delegation JWT 后，到达 GraphHarbor Agent Server。它不把直连
GraphHarbor、mock upstream 或旧 `langgraph dev` 当作 Platform 集成证据。

## 1. 前置条件

必须由启动服务的人显式确认：

- [ ] `platform-api` 已启动并启用数据库、`auth_required=true`
- [ ] `platform-api` 的 `PLATFORM_API_LANGGRAPH_UPSTREAM_URL` 指向 GraphHarbor API
- [ ] `platform-api` 的 `PLATFORM_API_RUNTIME_DELEGATION_SECRET` 与 GraphHarbor Auth 配置匹配
- [ ] GraphHarbor API、Worker、PostgreSQL、Redis 已启动并通过 `/ready`
- [ ] 测试 access token 对目标 project 有 Runtime read/write 权限
- [ ] `PLATFORM_API_EXPECTED_UPSTREAM_URL` 是启动配置中实际的 GraphHarbor URL
- [ ] Platform Runtime Catalog 已按该 upstream URL 完成 models/tools refresh，至少有一个 enabled model

测试不会读取或打印 secret，也不会创建用户、项目、容器或数据库；Thread 会产生一条带
`platform-graphharbor-*` 标记的测试数据，按现有数据保留策略处理。

## 2. 运行命令

在 `apps/platform-api` 目录执行：

```bash
PLATFORM_RUNTIME_INTEGRATION=1 \
PLATFORM_API_BASE_URL=http://127.0.0.1:<platform-api-port> \
PLATFORM_API_ACCESS_TOKEN=<platform-access-token> \
PLATFORM_API_PROJECT_ID=<project-uuid> \
PLATFORM_API_EXPECTED_UPSTREAM_URL=http://127.0.0.1:<graphharbor-port> \
uv run --frozen python -m unittest discover -s tests/integration -p 'test_*.py'
```

缺少任一变量，或没有显式设置 `PLATFORM_RUNTIME_INTEGRATION=1` 时，测试必须 skip；真实
HTTP 请求返回错误、认证失败、scope 错误或结构不符合预期时必须 fail。

`PLATFORM_API_EXPECTED_UPSTREAM_URL` 是启动配置的人工路由确认项。当前 Platform API 没有
向普通 project actor 暴露内部 upstream 配置，因此该变量不能替代部署配置审计；它与真实
GraphHarbor `/info`、graph search 和 Thread 返回共同构成这条最小链路证据。

## 3. 验收项

| 验收项 | 测试 | 必须证明 |
| --- | --- | --- |
| 未认证拒绝 | `test_platform_rejects_unauthenticated_runtime_request` | Platform API 返回 401/403，不把匿名请求送入 upstream |
| Runtime info | `test_platform_gateway_reaches_graphharbor_for_info_graphs_and_thread` | `/api/langgraph/info` 返回标准 info shape |
| Graph search | 同上 | `/api/langgraph/graphs/search` 返回 items/total/limit/offset |
| Thread scope | 同上 | GraphHarbor 返回的 Thread metadata.project_id 等于 Platform project |
| 缺环境语义 | `test_missing_gate_is_explicit_skip` | 未授权真实环境时明确 skip，不伪造通过 |

## 4. 未覆盖边界

本清单不证明真实模型 Run、SSE replay、Worker 接管、Sandbox、远程 MCP、Langfuse/OTLP、灰度、
回滚或性能 SLO；这些继续遵守 Runtime R6 文档中的 `deferred` 或独立验收状态。
