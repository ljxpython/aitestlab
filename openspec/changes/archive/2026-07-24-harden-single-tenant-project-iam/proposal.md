## 背景与原因

控制面已经具备平台级和项目级 RBAC，但单租户信任边界、本地密码生命周期、项目治理、机器身份授权和审计语义尚未形成安全的端到端 IAM 闭环。本变更将系统明确为“一个部署实例对应一个租户”，支持多用户和相互隔离的多项目，同时严格分离平台治理权限与项目内容访问权限。

## 变更内容

- 将部署实例视为服务端持有的唯一租户：保留数据库中的 `tenant_id`，不再信任客户端选择的租户请求头，也不提供租户管理或租户切换界面。
- 强化用户名密码认证：管理员创建或重置的密码可直接用于正常登录，用户可在安全设置中自愿修改密码；同时支持登录失败锁定、会话撤销、刷新令牌原子轮换，以及标准 JWT 签发方、受众和时间声明校验。
- 将粗粒度用户管理权限拆分为创建用户、修改资料、修改状态、重置凭据、分配平台角色和管理超级管理员等显式权限。
- 赋予超级管理员平台级项目治理能力，但不隐式开放项目业务内容：可查看和管理项目生命周期、指定项目管理员，并可在填写原因且留有审计记录后显式接管项目。
- 项目创建必须具备独立权限；普通项目访问继续以项目成员关系作为隔离边界。
- 增加项目范围的成员候选人查询，使项目管理员无需获取全局用户目录权限即可管理成员。
- **破坏性变更**：登录和个人资料响应不再返回完整 `project_roles` 映射，改为按当前项目查询授权；正式前端必须在同一发布链路中完成适配。
- 为服务账号增加显式项目授权，使机器身份只能按授予的项目和项目角色访问资源。
- 为用户生命周期、凭据、角色、项目治理、项目接管、成员关系和服务账号项目授权增加语义化审计动作。
- 同步更新 `platform-web` 控制面流程和 `platform-api` 契约，并处理数据库迁移与兼容性。

非目标：

- 多租户管理、租户切换、租户邀请或租户级角色。
- OIDC、SSO、MFA、邮件发送或邮件找回密码。
- 通用 ABAC/策略语言或自动过期的临时权限系统。
- 让超级管理员隐式访问项目知识库、测试用例、助手或 runtime 内容。

## 能力范围

### 新增能力

- `local-password-identity`：安全的本地密码账户创建、自愿改密、登录锁定、会话轮换与撤销，以及 JWT 声明校验。
- `platform-user-governance`：单租户内细粒度的平台用户生命周期和平台角色治理。
- `project-access-governance`：项目创建、生命周期治理、成员隔离、范围内成员发现、管理员恢复和超级管理员显式接管。
- `service-account-project-grants`：服务账号的显式项目角色和项目范围机器身份授权。
- `iam-audit-traceability`：身份与授权治理变更的语义化、可追责审计事件。

### 修改既有能力

无。仓库当前没有覆盖这些行为的已批准 OpenSpec 能力规格。

## 影响范围

- 主责位置：`apps/platform-api`；正式消费端：`apps/platform-web`。
- 影响链路：前端路由/页面 → 前端 service/type/authorization → HTTP 契约 → 认证与请求上下文 → IAM/users/projects/service-accounts 应用服务 → repository/数据库 → 审计写入与查询。
- 执行等级：B3 Governed，因为认证、授权、审计、数据归属、API 契约和数据库迁移语义均发生变化。
- 已加载标准：`AGENTS.md`、`docs/standards/01-ai-execution-system.md`、`apps/platform-api/docs/standards/permission-standard.md`、`apps/platform-api/docs/standards/audit-standard.md`、`apps/platform-api/docs/handbook/architecture.md`、`apps/platform-api/docs/handbook/project-handbook.md`、`apps/platform-web/docs/frontend-development-playbook.md`、`apps/platform-web/docs/control-plane-page-standard.md`。
- 预计存储变更包括用户登录状态字段、刷新令牌 family/消费状态和服务账号项目授权。现有用户、项目和成员关系必须通过显式迁移继续有效。
- 依赖登录或个人资料响应中完整 `project_roles` 的客户端，在正式前端切换到当前项目授权查询时需要兼容处理。
- 回滚不得删除已经迁移的身份或授权数据；应用回滚时可以暂时不使用新增列和表。
