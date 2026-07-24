# 验证记录

- 状态：完成
- 处置结论：已接受
- 实施前评审：已批准
- Owner/授权：用户于 2026-07-23 明确表示“我同意”，批准原 proposal、specs、design、tasks；2026-07-24 又逐份确认取消首次登录强制改密，并明确授权按修订文档实施；未使用 apply 豁免。

## 实施前评审与边界

已批准并实施以下口径：

- 一个部署实例对应一个服务端默认租户，不提供租户选择或切换。
- 操作员可创建无平台角色用户并管理普通用户资料/状态，不能重置凭据或分配平台角色。
- 超级管理员治理项目元数据和生命周期，但不自动获得项目内容权限；接管必须填写原因并建立长期显式 `project_admin` 成员关系。
- 管理员创建或重置的密码可直接正常登录，用户可在安全页主动修改；连续五次失败仍锁定十五分钟。
- 登录和资料响应移除完整 `project_roles`；正式前端按当前项目请求 `/access`。
- 服务账号通过显式项目 grant 获得项目角色。
- 使用增量 Alembic 迁移，应用回滚保留新增列、grant 表和令牌历史。

仓库内正式消费端只确认 `platform-web`。`apps/platform-web/examples/sub2api-reference` 是参考资产；仓库外消费端仍需发布前人工确认。

## 实施结果

- 数据库：新增 revision `20260723_0001`，包含用户密码状态/锁定字段、刷新令牌 family/消费字段和唯一服务账号项目 grant 表；`.gitignore` 已对白名单放行正式 Alembic 目录。
- 身份：PyJWT 校验算法、`iss`、`aud`、`nbf`、`exp`、`type`、`sub`、`jti`、`kid`；支持当前和旧验证 key。
- 本地登录：创建/重置密码直接可用，历史 `must_change_password=true` 不限制登录、刷新或普通 API；主动改密入口保留；五次失败锁定十五分钟、停用/重置会话撤销、refresh 条件更新一次性消费及 replay family 撤销均保持。
- 单租户：授权、审计和下游转发忽略 `x-tenant-id`，使用服务端 `__default`。
- 当前项目：认证只加载当前项目角色/grant，新增 `/api/projects/{project_id}/access`，路由项目/header 冲突返回 `project_scope_mismatch`。
- 用户治理：拆分创建、资料、状态、凭据和角色权限；最后一个超级管理员保护；操作员矩阵已用真实权限路径验证。
- 项目治理：显式创建权限、初始管理员、归档/恢复/删除、管理员恢复、带原因接管、范围内候选人和最后管理员保护。
- 项目隔离：项目 repository 默认只返回活动项目，归档后 assistant/runtime/knowledge/testcase/operation 等共享查询链统一失效。
- 服务账号：grant 列表/新增或修改/删除，API key 只加载当前项目 grant；账号停用、token 撤销/过期、项目归档和 grant 删除均拒绝或清空项目访问。
- 审计：用户治理、项目生命周期/恢复/接管/成员和服务账号 grant 使用语义 action；接管仅允许 `reason` metadata；伪造租户头不改变事件归属。
- 前端：当前项目 access store/守卫、登录后正常工作区路由、可选安全页、用户权限 gate、项目治理/候选人、服务账号 grant 与 token 分区、删除确认及 loading/empty/error 状态。

## 本地与最短链路证据

### Platform API 聚焦测试

- 命令：`PYTHONWARNINGS=ignore uv run python -m unittest tests.test_identity_security tests.test_user_platform_roles_api`
- 输入覆盖：创建和重置密码写入 `must_change_password=false`、历史 `true` 标记用户正常访问项目清单并成功刷新、主动改密、登录锁定、停用和重置会话撤销。
- 结果：`12 tests`，`Ran 12 tests in 13.592s`，`OK`。

### Platform API 全量测试

- 命令：`PYTHONWARNINGS=ignore uv run python -m unittest discover -s "tests" -p "test_*.py"`
- 最终完整结果：`90 tests`，`Ran 90 tests in 26.914s`，`OK`。
- 说明：未屏蔽时既有测试使用 23/24 字节 HMAC key 会产生 PyJWT `InsecureKeyLengthWarning`，不是本次默认配置；默认 secret 已满足更长长度要求。

### 本地演示栈启动回归

- 根因：`app/bootstrap/lifespan.py` 仍向已移除的 `IdentityService` 构造器传入 `project_roles_reader_factory`，导致 bootstrap admin 开启时应用启动失败，2142 未监听。
- 修复：移除失效参数及无用 import，并新增 bootstrap admin 开启时的 lifespan 回归测试。
- `uv run python -m unittest tests.test_identity_security`：`6 tests`，`OK`。
- `bash scripts/dev-down.sh` 后执行 `bash scripts/dev-up.sh`：成功启动 runtime-service、interaction-data-service、LightRAG、platform-api、worker 和 platform-web；演示用户初始化完成。
- `bash scripts/platform-web-demo-health.sh`：platform-api `http://127.0.0.1:2142/_system/health` 返回 `200`，platform-web 返回 `200`，worker 状态为 `running`，其余依赖探针均通过。

### Graphify

- `graphify update .`：本轮成功更新图谱，`29,739 nodes`、`62,816 edges`、`1,204 communities`。

### Platform Web

- `pnpm test:run`：`33 files / 92 tests` 通过。
- `pnpm typecheck`：通过。
- `pnpm lint`：退出码 0；存在两个未由本变更修改的知识图组件共 68 条格式 warning，无 error。
- `pnpm build`：通过，`dist/` 已生成。
- 覆盖：权限映射、历史改密标记不限制工作区路由、可选安全页、路由项目 access 刷新、项目治理 service、成员候选人 service、服务账号 grant service 及现有页面/组件回归。

### 用户创建 422 回归

- 根因：后端 `CreateUserCommand.password` 明确要求至少 8 个字符，但创建页只写“建议至少 8 位”，仍会把短密码提交到后端，最终把 Pydantic 422 显示成通用请求失败。
- 修复：创建页改为“必须至少 8 位”，增加 `minlength=8`，并在请求前拒绝短密码；后端安全约束保持不变。
- 聚焦 Vitest：`UserCreatePage.spec.ts` 通过，证明 `test1 / test` 不会调用 `createUser`。
- Playwright 真实页面：使用 `test1 / test` 点击创建后显示“密码至少需要 8 个字符”；网络记录无 `POST /api/users`，未创建测试数据。
- 全量前端测试、typecheck、目标文件 ESLint 和生产构建均通过。

### 可选密码修改与工作区导航回归

- 根因：后端中间件、刷新流程、登录页、路由守卫和顶部栏共同把 `must_change_password=true` 当作强制访问限制，导致用户不能进入总览和项目页面。
- 修复：新建和重置写入 `false`；历史 `true` 标记不再参与授权、刷新或前端路由；安全页继续提供主动改密，主动改密和管理员重置仍撤销既有刷新会话。
- 路由聚焦测试：`guards.spec.ts` 与 `routes.spec.ts` 共 7 个测试通过，覆盖历史标记用户正常进入工作区及安全页仍可主动访问。
- Playwright 真实链路：使用既有 `test1` 登录且不提交密码修改，直接进入 `/workspace/overview`；点击“项目”进入 `/workspace/projects`，项目清单请求返回 200；从用户菜单进入 `/workspace/security`，安全设置正常渲染。
- 观测：普通成员在总览页对无权限的用户和审计摘要请求返回两个 403，页面按既有逻辑展示“部分概览数据加载失败”；不影响本次导航验收，后续可独立做概览权限裁剪。

### 最短正式 API 链

自动化集成测试已证明：

1. 管理员创建或重置用户后 `must_change_password=false`；历史 `true` 标记用户也可正常登录、刷新和访问其权限允许的普通 API。
2. 操作员可创建无平台角色用户并修改普通用户资料/状态，不能重置凭据或分配角色。
3. 项目创建要求平台权限并建立显式初始管理员；项目 A/B scope 替换被拒绝。
4. 非成员超级管理员不能读项目成员；填写原因接管后成为显式管理员并可访问。
5. 管理员恢复和最后一个项目管理员保护生效；归档后项目内容访问停止，恢复后重新按成员关系判定。
6. 服务账号无 grant 时无项目角色；授权后可访问，跨项目无角色，删除 grant 无需换 key 即失效。
7. 账号停用、token 撤销/过期、项目归档均拒绝或清空机器身份项目访问。
8. 成功接管事件保存可信租户/项目和 `reason`；拒绝的 grant 修改写入 failed 语义审计；敏感请求值未进入 metadata。

## 迁移证据

- 临时旧库测试：`test_iam_migration.py` 从旧 users/refresh schema 执行 `alembic upgrade head` 成功，字段、family 回填和 grant 表存在。
- 本地代表库：`apps/platform-api/.data/platform-api.db` 已升级到 `20260723_0001`。
- 代表库检查：`alembic_version = 20260723_0001`，`users = 2` 行，`_alembic_tmp_users` 不存在。
- 迁移事故记录：首次 `migrations/env.py` URL 优先级错误曾对代表库执行部分非破坏性 DDL，并遗留 0 行 `_alembic_tmp_users`；用户明确确认删除临时表后已执行删除，随后代表库成功升级且用户仍为 2 行。
- 回滚：回退应用与前端，保留新增列和 `service_account_project_grants`；不执行破坏性 downgrade，不恢复已消费/撤销 refresh token。

## 未覆盖边界与残余风险

- 未获得真实 PostgreSQL 测试数据库，因此未验证 PostgreSQL 默认隔离级别/行锁行为；SQLite 文件库双事务竞争仅证明条件 UPDATE 单一 winner，不能冒充 PostgreSQL 证据。
- 已执行取消强制改密的真实浏览器链路；接管、恢复和服务账号 grant 的完整 UI 体验仍沿用此前自动化证据，未在本轮重复人工操作。
- 不覆盖多租户、OIDC/SSO/MFA、邮件邀请/找回密码或分布式 IP 限流；网关/IP 限流仍由部署层负责。
- 仓库外是否存在读取旧 `project_roles` 响应的客户端无法由本地扫描证明，发布前需 owner 确认。

## 文档与 Runbook

已更新：

- `apps/platform-api/docs/standards/permission-standard.md`
- `apps/platform-api/docs/standards/audit-standard.md`
- `apps/platform-api/docs/handbook/project-handbook.md`
- `apps/platform-api/docs/delivery/postgres-baseline.md`
- `apps/platform-api/docs/delivery/runbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`

## 最终处置

Owner 于 2026-07-24 明确回复“验收通过”。5 份 delta specs 已同步到 `openspec/specs/`，严格校验全部通过；change 可以归档。未经明确授权不执行 commit 或 push。
