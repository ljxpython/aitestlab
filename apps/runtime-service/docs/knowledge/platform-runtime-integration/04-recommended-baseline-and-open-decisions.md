# Platform Runtime Integration 推荐基线与决策记录

- 文档类型：`Supporting Decision Register`
- 状态：`owner-confirmed; implementation-partial`
- 阶段口径：当前实施使用 `L1/L2/L3`；历史 `P1` 仅作为 OpenSpec 变更范围标识。
- 规范真源：[`redesign-platform-runtime-integration`](../../../../../openspec/changes/redesign-platform-runtime-integration/)

## 1. 当前方案

平台链路固定为：

```text
platform-web -> platform-api Gateway -> GraphHarbor API/Worker -> runtime-service
```

GraphHarbor 是通用 LangGraph-compatible Agent Server，不承载 Platform 业务对象。Platform API 负责
登录、项目权限、Agent、模型连接配置、运行参数决议、审计和 Gateway；GraphHarbor 负责 Thread、Run、
Checkpoint、Event 的执行事实；Runtime Service 负责 Graph、Prompt、Tools 和模型调用。

模型管理采用 V1 最小字段：

```text
provider       Provider 标识
display_name   页面显示名称
base_url       Provider API 根地址
protocol       请求协议
model          Provider 接受的模型名
api_key        创建/轮换时写入的密钥
enabled        是否允许新 Run 使用
```

API key 只写不读。服务端保存时使用部署级 master key 加密，查询只返回 `credential_configured` 和可选
的脱敏摘要。密钥不进入浏览器响应、Thread、Run、Context、GraphHarbor、日志或审计详情。Runtime 调用
模型时由服务端读取并解密，失败即拒绝，不回退到其他模型或环境变量。

## 2. 已确认决策

| ID | 决策 | 状态 |
| --- | --- | --- |
| D01 | 产品统一使用 Agent；`agent_key = graph_id = assistant_id` 的值 | Accepted |
| D02 | Thread 首次 Run 绑定 Agent，之后不可切换 | Accepted |
| D03 | Gateway 消费不可信运行偏好，向 Agent Server 传标准 Context | Accepted |
| D04 | GraphHarbor 是 Thread/Run/Checkpoint/Event 执行事实源 | Accepted |
| D05 | 所有 Run create 入口使用同一个治理用例和幂等/reconciliation | Accepted |
| D06 | SSE 断开不取消；显式 Stop 才取消；HITL Run 仍占 active 槽位 | Accepted |
| D07 | Gateway 只开放正式 Chat 所需 allowlist | Accepted |
| D08 | 模型配置使用上述七字段；API key write-only，服务端加密保存 | Accepted |
| D09 | 生产级 model proxy、revision registry、JWKS/workload identity、Secret Store 编排 | Superseded/Rejected |

> D09 旧方案已废弃，不是“以后必须补齐”的 Deferred 任务。若未来需要外部 Secret Store，另立 change，
> 且只替换凭据存储实现，不恢复 `execution_model_id`、revision 或统一代理契约。

## 3. 模型配置行为

### 创建/编辑

Platform API 校验 `provider`、`base_url`、`protocol`、`model` 非空，URL 只允许 `http`/`https`，协议只
接受服务端支持的值。创建和轮换请求可以携带 `api_key`；不携带表示保持原值。服务端先校验配置，再将
密钥加密写入数据库，响应永不包含原文。

### 查询/列表

返回非敏感字段和：

```json
{"credential_configured": true}
```

不得返回密钥、完整 Authorization header、连接调试响应或内部文件路径。

### 启停和运行

`enabled=false` 的模型不能被新 Run 选择。已开始的 Run 使用其 Run Context 中的逻辑 `model`，配置被
编辑或禁用不改写历史执行事实。连接失败、解密失败和不支持的协议在 Provider 请求前 fail closed。

## 4. 已废弃的复杂方案

以下内容不属于当前本地 P0/L2/L3，也不作为模型录入完成门槛：

- `execution_model_id`、`model_revision` 和 revision registry；
- 独立统一模型代理及 Provider allowlist/SLO/DRI/runbook；
- 四接口 Secret Store（`create_or_rotate/resolve/get_status/disable`）和复杂权限矩阵；
- RS256/JWKS、`kid` overlap、Worker workload identity、mTLS；
- Provider 审批 smoke、固定 revision 和 capability probe。

真实生产需要这些能力时，另立治理变更；不得把它们偷偷塞回 V1 API。

## 5. 功能点、落点和验证

| 功能点 | 代码落点 | 完成标准 | 当前 |
| --- | --- | --- | --- |
| 模型字段校验 | `apps/platform-api/app/modules/runtime_catalog/application/service.py` | 空字段、坏 URL、未知协议被拒绝 | 已实现；定向回归通过 |
| API key write-only | `runtime_catalog` HTTP/repository | 创建/更新可写，GET/list 只返回 `credential_configured` | 已实现；定向回归通过 |
| 服务端加密 | `runtime_catalog/application/credentials.py` + DB | master key 缺失、无效或解密失败 fail closed | 已实现；定向回归通过 |
| 启停 | `runtime_catalog` service | disabled 模型不能创建新 Run | 代码已实现；完整链路待验证 |
| Runtime 使用配置 | Gateway/Runtime model construction | 请求使用服务端保存配置，不读取浏览器 key | 未完成；L2 待验证 |
| 泄漏防护 | API、Gateway、Runtime 日志/审计 | 响应、payload、日志无明文 key | 部分完成；链路/日志断言待补 |

验证记录统一写入 OpenSpec `verification.md`，任务勾选不能替代命令和结果。
