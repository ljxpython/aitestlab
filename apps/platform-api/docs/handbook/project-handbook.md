# Platform API Project Handbook

文档类型：`Current Handbook`

这份手册说明当前 `platform-api` 作为正式 control plane 的职责、使用方式和治理边界。

如果你要先理解仓库级主链，请同时看：

- `docs/development-paradigm.md`
- `docs/local-deployment-contract.yaml`
- `README.md`

这份文档是 `apps/platform-api` 的总手册。

如果你是第一次接手这套控制面，或者你已经看过代码但还是没搞清楚“这服务到底怎么用、为什么要这么拆、权限到底怎么判”，先看这份文档，不要一头扎进 `phase-*` 里迷路。

## 0. 建议先看的 6 张图

如果你想先用最短时间把业务骨架看明白，先按这个顺序看图：

1. [系统上下文图](../diagrams/system-context.svg)
2. [业务域边界图](../diagrams/business-domain-boundaries.svg)
3. [请求流转图](../diagrams/request-lifecycle.svg)
4. [Agent / Chat 业务流转图](../diagrams/agent-chat-flow.svg)
5. [权限模型图](../diagrams/permission-model.svg)
6. [Operation 生命周期图](../diagrams/operation-lifecycle.svg)

对应的 drawio 源文件也都在 `../diagrams/` 目录下，后续可以继续修改和复用。

## 1. 这套服务是干什么的

`platform-api` 是平台治理层后端，也就是 control plane。

它负责：

- 身份认证与平台权限
- 项目、成员、用户、Agent 等控制面主数据
- 平台配置、服务账号、公告、审计、操作中心
- 受控访问 `runtime-service`
- 给 `apps/platform-web` 提供稳定平台 API

它不负责：

- 智能体图执行本身
- MCP / tool 的真实装配与运行
- testcase 结果域真实存储
- 调试前端本身的交互逻辑

一句话说：

> `platform-api` 管“治理和边界”，`runtime-service` 管“运行和执行”。

## 2. 整体架构图

![系统上下文图](../diagrams/system-context.svg)

### 2.1 业务域边界图

![业务域边界图](../diagrams/business-domain-boundaries.svg)

## 3. 一次请求是怎么流转的

很多人看代码容易懵，不是因为代码多，而是因为不知道一条请求应该沿哪条路走。

正常流转应该是这样：

![请求流转图](../diagrams/request-lifecycle.svg)

### 3.1 用人话解释这条链

- 前端或调用方只和 HTTP API 说话
- handler 只做协议接入，不做复杂业务
- 真正的业务编排在 application/use case
- 权限和审计不是“想起来再补”，而是 use case 的组成部分
- 读数据库走 repository
- 调 runtime / interaction-data 走 adapter

### 3.2 哪些情况会改走 operation

如果这条链里的动作满足任一条件，就不应该同步死等：

- 超过 3 秒
- 需要取消
- 需要重试
- 需要保留历史
- 需要产出 artifact

这时候请求会变成：

1. 提交一个 operation
2. 立刻返回 `operation_id`
3. worker 或后台执行器继续跑
4. 前端通过 operation 状态更新 UI

## 4. 上层业务应该怎么使用这套平台

上层业务不要把 `platform-api` 当成一个“万能后端”。

正确使用方式是按职责走：

| 业务诉求 | 应该走哪层 | 说明 |
| --- | --- | --- |
| 登录、当前用户资料、修改密码 | `identity` | 属于平台身份域 |
| 用户、项目、成员管理 | `users` / `projects` | 属于平台治理主数据 |
| 公告、审计、平台配置、服务账号 | `announcements` / `audit` / `platform_config` / `service_accounts` | 属于平台治理能力 |
| Agent、graph、thread、chat、运行入口 | `agents`（当前由 `assistants` 兼容实现）+ `runtime_gateway` + `runtime_catalog` | 平台负责受控访问和上下文注入，不直接替代 runtime |
| testcase 管理、导出、预览 | `testcase` | 结果数据仍在 `interaction-data-service` |
| 长耗时刷新、导出、批处理 | `operations` | 通过 operation/job 跟踪状态，不在 HTTP 里硬等 |

### 4.1 前端如何用

`apps/platform-web` 是正式平台前端宿主。

它应该：

- 只调用 `platform-api`
- 不直接跨过控制面去乱打 `runtime-service`
- 通过项目上下文和用户身份访问平台资源
- 遇到长任务统一走 `operations`

### 4.1.1 当前 IAM 使用口径

- 一个部署实例只对应一个服务端租户，不提供租户选择或切换。
- 管理员创建或重置的密码可直接用于正常登录；用户需要时可在账户安全页主动修改。
- 登录和当前资料响应不返回完整 `project_roles`，前端切换项目时调用
  `GET /api/projects/{project_id}/access`。
- 平台超级管理员治理项目元数据和生命周期，但只有显式接管成为
  `project_admin` 后才能访问项目内容。
- 项目可通过 `POST /api/projects/{project_id}/archive` 归档，并通过
  `POST /api/projects/{project_id}/restore` 恢复。
- 服务账号项目授权使用 `/api/service-accounts/{id}/project-grants/*`，与 API key
  令牌生命周期分开管理。

如果你想确认“当前哪些后端能力已经真正被前端用起来，哪些只是 internal 或弱接入”，继续看：

- `../decisions/platform-capability-reconciliation.md`

如果你想看后续前端收口和能力对齐怎么执行，继续看：

- `../delivery/platform-web-gap-closure-checklist.md`

### 4.2 业务方如果要接入新的平台能力

推荐顺序：

1. 先确认能力属于平台治理还是运行时执行
2. 如果属于平台治理，在 `platform-api` 新增模块或 use case
3. 如果需要调用智能体、graph、thread，优先经由 `runtime_gateway`
4. 如果结果是业务域数据，不要塞进控制面库，放进专门结果域服务
5. 如果动作超过 3 秒，优先建 operation

### 4.3 典型业务接入场景

#### 场景 A：做一个新的平台治理页面

比如你要做“平台 API Key 治理页”。

正确做法：

1. 在 `platform-api` 定义新模块或收进已有治理模块
2. 先定接口契约和权限码
3. 补审计动作
4. 如果有批量刷新或导出，接进 `operations`
5. 再由 `platform-web` 接 service 和页面

不正确做法：

- 前端直接绕过控制面打底层服务
- 先把页面拼出来，再回头补权限
- 把批量任务塞进一个同步 POST 里硬跑

#### 场景 B：做一个新的 Agent 调用入口

![Agent / Chat 业务流转图](../diagrams/agent-chat-flow.svg)

比如你要让平台用户在工作台里跑一个新的 graph。

正确做法：

1. graph 真实执行逻辑仍在 `runtime-service`
2. `platform-api` 只负责项目边界、身份上下文、错误映射和受控转发
3. 前端调用 `platform-api` 的 gateway 接口，而不是直打 runtime

#### 场景 C：要保存 AI 运行结果

比如 testcase 跑完后要保存批次、结果、文档。

正确做法：

1. 结果域放进 `interaction-data-service`
2. `platform-api` 负责项目权限、聚合视图、导出、下载、预览整形
3. 前端只认 `platform-api` 暴露的治理接口

## 5. 为什么要这样拆

如果不拆，平台侧最后一定会烂成一锅：

- 登录和项目权限混在一起
- 页面直接打 runtime，边界失控
- 长任务塞在 HTTP 里，超时和重试全靠运气
- 审计只有 access log，出了事查不到人
- 后续接 Redis、PostgreSQL、对象存储时只能推翻重写

现在这套拆法的目标很直接：

- 前端有稳定宿主
- 控制面有稳定边界
- runtime 继续专注执行
- 结果域继续专注业务结果
- 后面接队列、中间件、对象存储时不需要重做目录结构

## 6. 代码结构分别负责什么

```text
apps/platform-api/
├── app/
│   ├── adapters/
│   ├── bootstrap/
│   ├── core/
│   ├── entrypoints/
│   └── modules/
├── tests/
├── docs/
├── deploy/
└── scripts/
```

### 6.1 `app/core`

放全局共享能力：

- settings
- request / actor context
- db session
- shared error
- normalization
- observability
- security primitives

### 6.2 `app/modules`

放业务模块，每个模块都按下面四层收：

```text
module/
  domain/
  application/
  infra/
  presentation/
```

每层职责：

- `domain`：领域模型、枚举、纯业务语义
- `application`：use case、command/query、policy、service
- `infra`：repository、SQLAlchemy、外部依赖落地
- `presentation`：HTTP DTO 与 router

### 6.3 `app/adapters`

放外部系统接入：

- `langgraph`
- `interaction_data`
- 后续可扩展 `redis`、`object_storage`、`notification`

### 6.4 `app/entrypoints`

放协议入口：

- `http/`
- `worker/`

这里只做接入，不做复杂业务编排。

### 6.5 `tests`

用于放权限、审计、模块行为、operation、adapter 回归测试。

### 6.6 `docs`

放长期有效的手册、标准、交付文档和阶段归档。

## 7. 目前主要模块怎么理解

| 模块 | 作用 | 不该干什么 |
| --- | --- | --- |
| `identity` | 登录、刷新、当前用户 | 不直接承接项目权限 |
| `iam` | 平台级 / 项目级权限模型 | 不让 handler 自己硬编码角色 |
| `projects` | 项目与成员治理 | 不替代全局用户管理 |
| `agents`（实现目录 `assistants`） | Agent 平台主数据和治理字段；旧目录仅作迁移兼容 | 不直接执行 runtime run |
| `runtime_catalog` | graph/model/tool 的受控目录视图 | 不篡改 runtime 真相源 |
| `runtime_gateway` | 受控代理 runtime upstream | 不承接平台主数据 |
| `testcase` | testcase 控制面接口、导出聚合 | 不持有结果域真实数据 |
| `announcements` | 公告管理与可见性 | 不碰权限主逻辑 |
| `audit` | 审计查询与事件模型 | 不只记 access log |
| `operations` | 长任务、重试、取消、artifact | 不在 HTTP 中直接把任务跑完 |
| `platform_config` | 平台级配置治理 | 不让页面绕开配置直接写死行为 |
| `service_accounts` | 服务账号与 token 管理 | 不混入普通用户登录链路 |
| `tenants` | 未来组织/租户边界预留 | 不在当前阶段强行半成品上线 |

## 8. 权限规则到底是什么

![权限模型图](../diagrams/permission-model.svg)

这块是最容易被写烂的，所以单独说透。

### 8.1 权限分两层

平台级角色：

- `platform_super_admin`
- `platform_operator`
- `platform_viewer`

项目级角色：

- `project_admin`
- `project_editor`
- `project_executor`

### 8.2 最核心的铁律

- 项目级角色永远不能自动变成平台级角色
- 平台级角色也不能绕过项目归属校验直接乱操作项目资源
- handler 不允许手写一堆 `if role == "admin"` 散装判断
- 所有权限判定统一基于 `ActorContext`

### 8.3 你可以这样理解

平台级权限管的是：

- 用户管理
- 平台配置
- 全局审计
- 服务账号
- 全局 operation 治理

项目级权限管的是：

- 项目资源读写
- 项目成员
- Agent project scope
- testcase project scope
- runtime gateway 的项目边界

### 8.4 典型例子

- 某人是 `project_admin`
  - 可以管理自己项目里的成员和资源
  - 不能管理全局用户
  - 不能改平台配置
- 某人是 `platform_operator`
  - 可以看平台治理页和全局运维能力
  - 如果要操作某个项目资源，仍然需要项目归属与对应权限
- 某人是 `platform_viewer`
  - 只能看，不应该拿到写权限

详细规则见：

- `../standards/permission-standard.md`

### 8.5 常见角色场景表

| 场景 | `platform_super_admin` | `platform_operator` | `platform_viewer` | `project_admin` | `project_editor` | `project_executor` |
| --- | --- | --- | --- | --- | --- | --- |
| 查看平台配置 | 可以 | 可以 | 可以 | 不可以 | 不可以 | 不可以 |
| 修改平台配置 | 可以 | 视策略开放 | 不可以 | 不可以 | 不可以 | 不可以 |
| 查看全局审计 | 可以 | 可以 | 可以 | 不可以 | 不可以 | 不可以 |
| 管理服务账号 | 可以 | 视策略开放 | 不可以 | 不可以 | 不可以 | 不可以 |
| 查看项目成员 | 需要项目归属或额外授权 | 需要项目归属或额外授权 | 不可以 | 可以 | 可以 | 只读或受限 |
| 修改项目成员 | 不自动拥有，仍需项目归属/授权 | 不自动拥有，仍需项目归属/授权 | 不可以 | 可以 | 一般不可以 | 不可以 |
| 运行项目内 Agent / runtime 能力 | 不自动拥有，仍需项目归属/授权 | 不自动拥有，仍需项目归属/授权 | 不可以 | 可以 | 可以 | 受限执行 |

这里有个非常关键的原则：

> 平台角色解决“有没有资格管理平台”，项目角色解决“能不能碰这个项目”。

两者不是互相替代关系。

### 8.5.1 人类用户怎么赋权

当前正式口径已经不是只看 `is_super_admin` 这个老字段了，而是看用户绑定的 `platform_roles`。

实际操作入口分两层：

- 平台级角色：
  - 在 `apps/platform-web/src/modules/users/pages/UserCreatePage.vue` 选择单个平台角色
  - 在 `apps/platform-web/src/modules/users/pages/UserDetailPage.vue` 调整平台角色与状态
  - 当前 UI 采用单选模型：`无平台角色 / platform_viewer / platform_operator / platform_super_admin`
- 项目级角色：
  - 统一去项目成员页分配，不放在用户创建页混着管
  - 入口在项目成员治理页面，由 `project_admin / project_editor / project_executor` 控制项目内权限

这样设计的原因很直接：

- 平台角色决定“能不能治理平台”
- 项目角色决定“能不能进入某个项目并修改项目内容”
- 平台管理员不会因为有平台角色就自动拿到所有项目写权限
- 项目管理员也不会因为能管项目就自动变成平台管理员

### 8.6 服务账号和普通账号的区别

服务账号是给系统集成、脚本或平台内部自动化调用准备的，不是给人登录页面用的。

它的特点：

- 不走普通用户名密码登录 UI
- 通过 token 调平台 API
- 权限仍然受平台角色约束
- token 要支持创建、展示、撤销和审计

所以不要把它理解成“另一个用户体系”，它更像“受控的机器身份”。

## 9. 审计规则是什么

审计不是 access log 美化版，它要回答：

- 谁做的
- 对哪个资源做的
- 成功还是失败
- 属于哪个 plane
- 花了多久

必须落的关键字段：

- `request_id`
- `plane`
- `action`
- `target_type`
- `target_id`
- `actor_user_id`
- `project_id`
- `result`
- `status_code`
- `duration_ms`

动作命名统一是：

`{domain}.{resource}.{verb}`

例如：

- `identity.session.created`
- `project.member.removed`
- `operation.failed`

详细规则见：

- `../standards/audit-standard.md`

## 10. Operation 是怎么用的

![Operation 生命周期图](../diagrams/operation-lifecycle.svg)

不是所有动作都该同步执行。

这些典型动作应该优先走 `operations`：

- refresh
- export
- batch sync
- 大文件导入
- 需要重试 / 取消 / 历史追踪的任务

典型调用方式：

1. 页面或业务入口提交一个动作
2. 后端返回 `operation_id`
3. 前端轮询或订阅 operation 状态
4. 完成后查看结果、错误或 artifact

这套模式的好处：

- 请求不会卡死
- 可重试、可取消、可审计
- 后续可平滑切到 Redis / 独立 worker

详细规则见：

- `../standards/operations-standard.md`

### 10.1 一条典型 operation 链路

比如“导出 testcase 文档包”：

1. 前端点击导出
2. 控制面创建一个 `testcase.export` operation
3. 返回 `operation_id`
4. worker 异步执行导出
5. 导出完成后写 `artifact`
6. 前端轮询 operation，拿到下载入口

这比同步导出好太多，因为它至少具备：

- 可重试
- 可取消
- 可审计
- 可追踪失败原因
- 后续可平滑切队列

## 11. 新功能应该怎么开发

标准顺序不要乱：

1. 先确认这是平台治理能力还是 runtime 执行能力
2. 确认归属哪个模块
3. 先定义 request / response / command / query
4. 补权限边界
5. 补审计动作
6. 判断是否要进入 operation
7. 再写 `domain -> application -> infra -> presentation`
8. 补测试
9. 补文档和验收说明

### 11.1 不该怎么做

- 不要直接在 handler 里写业务
- 不要直接跨模块乱读 repository
- 不要为了快先跳过权限和审计
- 不要把结果域数据直接塞进控制面
- 不要让前端绕过控制面直打底层服务

### 11.2 新模块最小交付清单

如果你要做一个新模块，最低应该交出这些东西：

- 模块边界说明
- request / response DTO
- 权限码与角色映射
- 审计动作命名
- repository 或 adapter 落点
- 最小测试
- 前端 service 或明确的落点
- 文档与验收说明

## 12. 给新同事和协作者的推荐阅读顺序

1. `README.md`
2. `project-handbook.md`
3. `architecture.md`
4. `development-playbook.md`
5. `../standards/permission-standard.md`
6. `../standards/audit-standard.md`
7. `../standards/operations-standard.md`
8. `../delivery/change-delivery-checklist.md`
9. `../delivery/module-delivery-template.md`
10. `../archive/phases/`

## 13. 这份手册的定位

这份文档不是阶段纪要，也不是 release note。

它是 `platform-api` 的稳定认知入口，用来回答三件事：

- 这套服务现在是什么
- 上层业务应该怎么用它
- 后续开发应该怎么在这套边界内继续往前推
