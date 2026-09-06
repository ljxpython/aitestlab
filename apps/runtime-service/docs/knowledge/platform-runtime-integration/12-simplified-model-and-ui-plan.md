# 模型目录与前端信息架构简化方案

- 文档类型：Harness planning record
- 状态：`Accepted by owner; 9.1-9.4/9.6-9.7 local-complete; 9.5 in-progress`
- 适用范围：`platform-web`、`platform-api`、Runtime model resolution、本地全链路测试
- 关联 OpenSpec：[`redesign-platform-runtime-integration`](../../../../../openspec/changes/redesign-platform-runtime-integration/)

## 1. 目标

将模型配置和 Agent 使用流程收敛为用户可以直接理解的产品对象：

```text
Models 页面录入模型
  -> Platform 加密保存连接信息
  -> 项目设置唯一默认模型
  -> Chat 选择默认模型或单次覆盖
  -> Gateway 签发短期 opaque model reference
  -> Runtime 通过内部端点读取已保存配置并执行
```

服务启动本身就是完整链路，不再要求用户理解 `RUNTIME_MODEL_PROFILE` 或
`RUNTIME_E2E`。GraphHarbor 继续是通用 Agent Server，不能把 Platform 的模型、权限或页面逻辑放入其中。

## 2. 当前问题

| 问题 | 当前表现 | 调整方向 |
| --- | --- | --- |
| 模型 profile | `RUNTIME_MODEL_PROFILE` 控制本地兼容目录和启动校验 | 删除 profile；模型目录成为唯一配置来源 |
| E2E 开关 | `RUNTIME_E2E` 只控制测试是否调用真实 Provider | 删除环境变量；用测试目录/pytest marker 区分 Provider smoke |
| 模型执行 | 页面可录入七字段，但 Runtime 仍主要读取 `.env` Provider 配置 | 将 Platform 保存的模型配置接入 Runtime resolver |
| Agent/Graph | 用户同时看到 Agent、Assistant、Graph 多套名称 | 产品只展示 Agent；Graph 保留为内部技术目录 |
| Runtime Hub | 聚合目录、策略和技术状态，入口重复 | 模型提升为独立一级入口，Runtime Hub 退为状态/兼容入口或重定向 |
| Runtime Policy | 独立页面包含模型、工具、图三类复杂策略 | 后端保留 deny-first 策略；模型控制合并到 Models，Agent 控制合并到 Agent |

## 3. 产品对象边界

### 3.1 Agent 与 Graph

产品层只保留 Agent：

```text
用户看到 Agent
Agent 内部绑定 graph_id
Gateway 使用 agent_key
GraphHarbor 使用 assistant_id/graph_id
Runtime 加载 graph
```

不删除 GraphHarbor 和 `langgraph.json` 中的 Graph 概念，因为它仍是可执行部署目录和发布事实源。
Graph 页面只作为管理员/开发排障入口；普通用户通过 Agent 页面完成创建、启用、配置和使用。

### 3.2 模型

模型是 Platform 的独立配置对象，最小字段保持：

`provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled`。

规则：

- API Key 只写不读，服务端加密保存。
- 一个项目最多一个默认模型；默认值属于项目，不属于 Runtime 进程。
- Chat 只能选择当前项目已启用的模型。
- 单次 Chat 可以覆盖模型；已开始的 Run 不被后续设置修改。
- 浏览器只提交 `model_id` 和生成参数，不提交 URL、API Key、Provider 凭据或 Tools。

### 3.3 Runtime Policy

策略不是可删除的安全逻辑。它负责模型 allowlist、启停、项目默认值和 Agent/Tool 的 deny-first 校验。
但不再要求用户操作三套独立策略表：

- Models 页面：启用/禁用、设为项目默认、凭据状态。
- Agent 页面：Agent 启用/禁用和默认模型覆盖。
- Tools 与 Graph 的可用范围：服务端策略和 Agent 实现决定，普通用户不配置。

## 4. 前端信息架构

### 4.1 推荐导航

```text
Agent
  - Agent 列表
  - 创建 Agent
  - Agent 详情

Models
  - 模型列表
  - 新增/编辑模型
  - 项目默认模型

Chat
Threads

Governance
  - Operations
  - Audit
```

### 4.2 删除或隐藏

| 页面/入口 | 处理 | 理由 |
| --- | --- | --- |
| `Assistants` 命名 | 改为 `Agents`；旧 URL 仅保留迁移重定向 | 消除第二套产品对象 |
| 独立 `Graphs` 页面 | 普通导航隐藏，保留管理员/开发诊断能力 | Graph 是部署技术对象，不是用户配置对象 |
| 独立 `Runtime Policies` 页面 | 从普通导航移除，控制项并入 Models/Agents | 避免模型策略、工具策略、图策略重复操作 |
| `Runtime Hub` | 保留兼容路由，首页只展示状态；主要入口改为 Models/Agents | Runtime 是执行层，不应成为复杂产品对象 |
| Runtime Tools 管理页 | 删除用户配置入口，保留服务端 catalog | Tools 由 Agent 和服务端策略决定 |
| Chat Debug 页面 | 删除 | 正式 Chat、测试工具和服务端 smoke 已覆盖调试需求 |

## 5. 配置与测试调整

### 5.1 删除 `RUNTIME_MODEL_PROFILE`

代码和文档需要删除：

- Runtime 配置校验中的 profile 必填和枚举检查。
- Platform API 的 local-compat 静态模型分支。
- `.env` 中的 profile 注释和启动命令前缀。
- 依赖 profile 的单元测试、OpenSpec 场景和 runbook。

替代方案：服务启动不预置模型。模型目录为空时，Models 页面提示先录入模型；录入成功后刷新项目策略并可用于 Chat。

### 5.2 删除 `RUNTIME_E2E`

代码和文档需要删除测试对该环境变量的判断。测试分类改为：

- 默认 integration/chain smoke：验证 Platform、GraphHarbor、Worker、Runtime、PostgreSQL、Redis 的真实本地链路。
- `provider` 测试目录或 pytest marker：明确调用真实 Provider，缺少凭据时失败并给出原因，不降级 fake。

`local-stack.sh start` 不读取或要求该变量；启动五个本地应用进程的行为保持不变。

## 6. Runtime 模型解析最小实现

模型页面录入的连接配置必须真正参与执行：

1. Platform API 根据项目策略校验 `model_id` 是否启用。
2. Gateway 将已授权的 `model_id` 和生成参数传入受信 Runtime 请求。
3. Runtime/Worker 使用服务端可访问的模型配置构造 Provider 客户端。
4. 浏览器、Thread、Run、SSE、GraphHarbor payload 和日志不得出现 API Key。
5. 未知、禁用、配置损坏或 Provider 连接失败在上游 Provider 调用前 fail closed。

本地版本不新增独立模型代理、Secret Store、revision、JWKS 或 workload identity；如未来需要，另立 change。

## 7. 实施顺序

| 阶段 | 功能点 | 代码落点 | 验证 | 状态 |
| --- | --- | --- | --- | --- |
| M1 | 文档、配置和测试契约移除两个环境变量 | `validate_runtime_config.py`、测试、`.env`、OpenSpec | 配置测试通过，服务启动不依赖开关 | `local-complete` |
| M2 | Platform 模型目录成为唯一来源 | `runtime_catalog`、`runtime_gateway`、credentials、migration | 模型 CRUD、权限、加密、disabled/invalid negative | `local-complete` |
| M3 | Runtime 消费 Platform 模型配置 | `runtime_service/runtime/modeling.py`、Gateway context | HMAC opaque reference、`/api/runtime/internal/model-config`、Runtime 构造连接；定向测试通过，真实录入后 Run 待执行 | `in-progress` |
| M4 | 前端导航和页面收敛 | `AppSidebar.vue`、routes、Runtime/Models/Agents pages | Models 一级入口、策略默认操作、typecheck 和组件测试 | `local-complete` |
| M5 | 清理旧入口和兼容层 | legacy route/module、旧文档 | 静态引用检查、OpenSpec strict validate、owner UAT | `pending` |

## 8. 验收标准

- 不设置 `RUNTIME_MODEL_PROFILE` 和 `RUNTIME_E2E` 也能启动五个本地服务并完成基础全链路 smoke。
- 用户可从独立 Models 页面录入多个模型，API Key 不在任何读取响应中出现。
- 项目只能有一个默认模型；Chat 可使用默认模型或单次选择已启用模型。
- 实际 Run 使用页面录入的模型连接配置，而不是隐式回退 `.env` Provider 配置。
- 普通用户导航只看到 Agent、Models、Chat、Threads；Graph/Policy 作为内部或管理员能力。
- Agent、Graph、Runtime、Policy 不再分别维护重复的执行状态机。
- integration、provider、浏览器页面和 owner UAT 的结果分别记录在 OpenSpec `verification.md`。

## 9. 未决边界

- Provider 配置通过短期 HMAC opaque reference 到达 Runtime；Runtime 使用 `PLATFORM_RUNTIME_MODEL_CONFIG_URL`
  调用 Platform 内部端点，按 project/model 校验后读取解密配置。API key 只存在于该内部响应和 Provider
  初始化内存中，不写入浏览器、Run、GraphHarbor 或日志。
- 是否保留管理员 Graph 诊断页，取决于 owner UAT；普通用户入口不受影响。
- 旧 Assistant/Graph URL 的重定向保留期限，需要在清理阶段根据访问日志决定。
