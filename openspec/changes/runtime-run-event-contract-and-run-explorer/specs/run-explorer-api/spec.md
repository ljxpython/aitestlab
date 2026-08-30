## ADDED Requirements

### Requirement: Run 列表必须使用项目范围和稳定分页
`GET /api/runtime/runs` MUST 从已验证请求上下文派生 `project_id`，支持 assistant、graph、status、
actor 和时间窗口筛选，使用包含 `created_at + id` 的 cursor 分页，并限制单页大小。

#### Scenario: 查询项目 Run
- **WHEN** 有项目读取权限的用户请求 Run 列表
- **THEN** 系统只返回该项目范围内的 Run，并返回 `items`、`next_cursor` 和 `has_more`

#### Scenario: 伪造项目参数
- **WHEN** 请求体或查询参数提供与可信上下文不同的 `project_id`
- **THEN** 系统忽略该值或拒绝请求，不得跨项目返回 Run

### Requirement: Run 详情必须聚合核心状态和可用摘要
`GET /api/runtime/runs/{run_id}` MUST 返回 Run 核心记录、有限产品事件时间线、Operation、Audit
摘要、Langfuse Trace 摘要和每个数据源的 `source_status`。Langfuse、日志或指标单独不可用时，
接口 MUST 返回核心数据并标记对应来源不可用。

#### Scenario: Langfuse 不可用
- **WHEN** Run 存在且用户有权限，但 Langfuse 请求超时
- **THEN** 响应仍返回 Run 和平台事件，`source_status.langfuse` 为 `unavailable`

#### Scenario: Run 不属于项目
- **WHEN** 用户使用其他项目的 `run_id` 请求详情
- **THEN** 系统返回统一的未找到或无权限结果，不泄露目标 Run 是否存在

### Requirement: 产品事件必须单独分页查询
`GET /api/runtime/runs/{run_id}/events` MUST 支持 `after_sequence`、`limit` 和稳定排序，响应只
包含脱敏事件字段。详情接口不得因事件数量无限增长而返回完整历史。

#### Scenario: 查询后续事件
- **WHEN** 客户端传入 `after_sequence=42`
- **THEN** 系统只返回 `sequence > 42` 的事件，并按升序提供下一页游标

#### Scenario: 非法游标
- **WHEN** 客户端提交无法解析或不属于该项目范围的 cursor
- **THEN** 系统返回 400，不执行无界查询

### Requirement: 查询接口不得暴露外部观测凭据
Run Explorer MUST 由 Platform API 服务端访问 Langfuse、Prometheus 和 Loki；浏览器响应中不得
包含 API key、Bearer token、Cookie 或任意外部系统凭据。Trace 链接 MUST 由服务端生成并受权限控制。

#### Scenario: 返回 Trace 摘要
- **WHEN** 有权限用户请求包含 Langfuse 的 Run 详情
- **THEN** 响应只包含安全摘要或受控跳转地址，不包含 Langfuse secret key

### Requirement: 查询权限和接管行为必须可审计
Run 列表、详情、事件和外部摘要 MUST 每次执行项目/平台权限校验。平台管理员默认只能查看
全局 Run 元数据；读取项目内容或执行 break-glass 接管 MUST 写入 Audit。

#### Scenario: 管理员接管项目 Run
- **WHEN** 平台管理员以 break-glass 模式查看项目级敏感摘要
- **THEN** 系统要求接管原因并写入包含操作者、项目、目标 Run 和结果的 Audit 事件

### Requirement: 项目查询和平台查询必须使用不同权限边界
项目查询 MUST 使用 `/api/runtime/*` 并从可信请求上下文派生项目范围；跨项目平台查询 MUST
使用 `/api/admin/*` 并要求平台管理员权限。客户端不得通过 `scope=all` 或伪造 `project_id`
提升查询范围。

#### Scenario: 项目用户请求全局范围
- **WHEN** 项目用户向 `/api/runtime/runs` 提交 `scope=all`
- **THEN** 系统拒绝该范围参数或忽略它，响应仍只包含可信项目范围

#### Scenario: 平台管理员查询多个项目
- **WHEN** 具有平台运行读取权限的管理员请求 `/api/admin/runtime/runs`
- **THEN** 系统按授权后的项目筛选返回 Run 元数据，并不默认返回项目内容正文

### Requirement: 查询分页必须保持稳定顺序
Run 列表 MUST 使用包含 `created_at` 和主键的 cursor；事件查询 MUST 使用
`after_sequence` 并按 `sequence` 升序返回。非法、过期或跨范围 cursor MUST 返回 400。

#### Scenario: 事件分页
- **WHEN** 客户端请求 `after_sequence=42`
- **THEN** 响应只包含 `sequence > 42` 的事件，并返回 `next_after_sequence` 和 `has_more`

#### Scenario: 跨项目 cursor
- **WHEN** 客户端把项目 A 的 cursor 用于项目 B 的列表请求
- **THEN** 系统返回 400，不执行跨项目数据查询
