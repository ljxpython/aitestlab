## ADDED Requirements

### Requirement: Platform Runtime Gateway SHALL reach GraphHarbor through the compatible Agent Server protocol

当 Platform API 配置的 Runtime upstream 指向 GraphHarbor 时，Platform Runtime Gateway SHALL 通过真实 HTTP 请求完成平台 access token 校验、项目权限校验、包含 Runtime policy snapshot、scope 和 context hash 的 Runtime delegation token 签发，并访问 GraphHarbor 的标准 Agent Server endpoint。Gateway 不得要求上层调用方理解 GraphHarbor 专用 API。

#### Scenario: Platform requests Runtime info through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime read 权限的 Platform API 客户端请求 `/api/langgraph/info`
- **THEN** Platform API 返回 GraphHarbor 的 JSON info 响应，且请求经过 GraphHarbor 的 delegation authentication

#### Scenario: Platform searches graphs through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime read 权限的 Platform API 客户端请求 `/api/langgraph/graphs/search`
- **THEN** Platform API 返回 GraphHarbor 的 graph search 响应，并向 upstream 注入当前项目 scope

#### Scenario: Platform creates a scoped Thread through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime write 权限的 Platform API 客户端请求 `/api/langgraph/threads`
- **THEN** Platform API 返回 GraphHarbor 创建的 Thread，并将当前项目 scope 写入 Thread metadata

#### Scenario: Missing Platform or upstream environment is explicit
- **WHEN** 集成测试缺少 Platform API 地址、access token、project ID 或 GraphHarbor upstream 配置
- **THEN** 测试明确报告缺失输入并跳过；不得启动旧 `langgraph dev`，也不得将 skip 计为通过

### Requirement: Platform-to-GraphHarbor integration SHALL preserve denial semantics

Platform Gateway SHALL preserve fail-closed behavior at both boundaries：Platform API 对未认证或无项目权限请求拒绝；GraphHarbor 对缺失或无效 delegation token 请求拒绝。测试不得用 mock upstream 代替真实 GraphHarbor。

#### Scenario: Platform rejects an unauthenticated gateway request
- **WHEN** 客户端不提供有效 Platform access token 请求 Runtime Gateway
- **THEN** Platform API 返回稳定的 401/403，且 GraphHarbor 不会被当作匿名执行面调用

#### Scenario: GraphHarbor rejects a request without valid delegation
- **WHEN** 直接请求 GraphHarbor 时不提供有效 Runtime delegation token
- **THEN** GraphHarbor 返回认证失败，且 Platform Gateway 集成测试不能通过该请求冒充已认证链路
