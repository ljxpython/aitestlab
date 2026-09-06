# DeepSeek Harness 模型录入借鉴与最小方案

- 文档类型：Harness Supporting Design Record
- 状态：`Accepted; minimal V1 baseline`
- 适用范围：Platform 模型管理、Runtime 模型连接配置、模型凭据保护
- 参考项目：外部研究仓库 `deepseek-harness`（本机研究目录，不作为项目依赖）
- 更新时间：2026-09-04

## 1. 结论

当前不建设复杂的生产模型代理治理系统。本轮已确认以下最小闭环，并已同步 OpenSpec contract：

```text
录入 provider / URL / protocol / model
              +
           写入 API key
              -> 服务端保存并保护 key
              -> Runtime 请求时读取连接配置
              -> key 不进入浏览器、Run、GraphHarbor、日志和审计详情
```

`DRI`、`JWKS`、复杂 `Secret Store` 接口、`execution_model_id` 版本路由和 Provider 审批 smoke
属于已废弃的旧方案，不应进入本 change。未来若出现明确需求，另立 change 重新评审。

## 2. DeepSeek Harness 的实际做法

### 2.1 DeepSeek 原生 Provider

`llm-deepseek` 的连接配置核心字段是：

| 字段 | 用途 |
| --- | --- |
| `apiKeyEnv` | 凭据引用，不是明文 key；默认 `DEEPSEEK_API_KEY` |
| `baseURL` | Provider API 根地址，可省略并使用默认地址 |
| `models` | 可选择的模型列表；每个模型至少有 `id` |
| `thinking`、`reasoningEffort` | DeepSeek 特有的可选能力，不是连接必需字段 |

### 2.2 自定义 Provider

`llm-pi-ai` 的自定义 Provider 表单要求：

| 字段 | 是否必需 | 说明 |
| --- | --- | --- |
| Provider ID | 是 | 稳定路由键，创建后不建议直接改名 |
| Display name | 否 | 仅用于页面展示 |
| Base URL | 是 | 自定义网关或自托管服务地址 |
| API protocol | 是 | 例如 `openai-completions` |
| API key | 通常是 | 页面只接收写入，不回显旧值 |
| Models | 是，至少一个 | 每个模型至少有 `id`，名称和能力信息可选 |

其关键设计是：已安装 Provider 可以继承默认 endpoint、protocol 和 catalog；自定义 Provider
才要求用户明确填写 URL、protocol 和 model。凭据通过引用解析，模型请求时重新读取，因此换 key
不需要重启。

### 2.3 凭据保护

DeepSeek Harness 的页面行为值得直接借鉴：

- API key 输入框是 write-only；
- 保存后只返回 `configured`、来源或脱敏描述，不返回原值；
- settings 只保存 credential reference；
- Provider 每次请求按 reference 解析最新值；
- key 不进入普通配置、模型选择器、请求日志或会话记录。

## 3. 本项目采用的最小模型录入字段

### 3.1 V1 建议字段

Platform 模型配置建议只包含以下字段：

| 字段 | 类型 | 说明 | 暴露范围 |
| --- | --- | --- | --- |
| `provider` | string | Provider/网关标识，例如 `openai-compatible` | API、页面、Runtime 连接配置 |
| `display_name` | string | 页面展示名称 | API、页面 |
| `base_url` | URL | API 根地址 | 管理页面和受信 Runtime，不进入 Run |
| `protocol` | enum | 请求协议，例如 `openai-chat`、`openai-responses`、`anthropic-messages` | 受信 Runtime |
| `model` | string | Provider 接受的模型名 | API、页面、Runtime Context |
| `api_key` | string | 创建或轮换时输入的密钥 | 只写入服务端，禁止读回 |
| `enabled` | boolean | 是否允许新请求使用 | API、页面、策略校验 |

`display_name` 和 `enabled` 可以有默认值；URL、protocol、model 是自定义连接的真正最小集合。

### 3.2 V1 暂不加入

以下字段先不做，避免为了未来场景制造第二套配置系统：

- `execution_model_id` 和 revision registry；
- Provider allowlist、SLO、DRI、runbook；
- RS256/JWKS、workload identity、mTLS；
- `compat`、vision modality、reasoning budget、复杂 retry policy；
- Provider 自动发现和完整模型 catalog；
- 多层 Secret Store API、credential version 编排。

模型确实需要这些能力时，再按真实故障和部署边界增加，不预留空字段。

## 4. 存储方案

### 4.1 配置与密钥分离

模型表保存非敏感连接配置：

```text
provider
display_name
base_url
protocol
model
encrypted_credential
enabled
```

API key 不放在 Runtime Context、GraphHarbor Run payload、Thread metadata、Platform Web
状态或日志中。

当前仓库尚未发现可直接复用的 Secret Store。为完成本地 L2/L3，建议先采用最小的服务端保护方案：

1. 服务端接收 API key，只在写入/轮换接口出现一次；
2. 使用部署级 master key 对数据库中的 key 做加密存储；
3. 普通读取只返回 `credential_configured: true`，当前不返回末四位摘要；
4. Runtime 调用时在服务端解密，使用后尽快释放，不把 key 复制到请求 Context；
5. master key 缺失或解密失败时 fail closed，不回退到其他环境变量。

生产环境将来可以把第 2 步替换为真正的 Secret Store，不改变模型配置接口。若当前部署已有文件型凭据
存储，也可以像 DeepSeek Harness 一样保存 `credential_ref`，但不得让浏览器直接读取该文件。

### 4.2 API 行为

建议接口语义：

| 操作 | 请求 | 响应 | 规则 |
| --- | --- | --- | --- |
| 创建 | provider、URL、protocol、model、API key | 非敏感模型记录 | key 只写入，不回显 |
| 编辑 | 非敏感字段，可选新 API key | 非敏感模型记录 | 不提交 key 表示保持原 key |
| 查看 | 模型 ID | 非敏感字段 + `credential_configured` | 永不返回 key |
| 启停 | enabled | 非敏感模型记录 | 禁用后新 Run 拒绝 |
| 连接验证 | 暂不提供独立接口 | 不计入当前最小闭环；未来另立功能 | 如新增必须沿用脱敏和 fail-closed 规则 |

## 5. 从 DeepSeek Harness 借鉴、但按本项目简化

### 直接借鉴

- 连接配置和凭据分开；
- API key write-only；
- 读取返回 redacted/configured descriptor；
- 自定义 Provider 明确要求 URL、protocol、model；
- 统一一个模型连接构造入口；
- 请求时读取最新凭据，不要求重启；
- Provider 不可用时在模型调用前给出明确错误。

### 不直接照搬

- DeepSeek Harness 的 settings namespace、插件注册和多层 credential provider 是其产品内部机制；
- 它的模型 catalog、图片能力、reasoning 和 compat 选项不属于当前 L2 最小需求；
- 它允许环境变量作为本地凭据来源，本项目生产配置不能因此把任意环境变量隐式暴露给租户请求。

## 6. 本项目落点与验证

### 当前代码事实

- `apps/platform-api/app/modules/runtime_catalog` 已增加七字段模型写入、更新和启停接口；
- `runtime_catalog_models` 保存非敏感字段、`enabled` 和 `api_key_ciphertext`；读取只映射为 `credential_configured`；
- `POST /api/runtime/models`、`PATCH /api/runtime/models/{model_id}` 和列表接口已实现；
- Runtime 从 Platform 配置动态读取并实际调用 Provider 的完整链路尚未验证；
- `apps/runtime-service/.env` 的真实模型只用于 owner 已授权的 `local-compat` L2 smoke，不作为平台模型录入功能。

### 后续最小实施落点

1. 补齐 Runtime 使用 Platform 保存配置的最短受信链路；
2. 为禁用模型、解密失败和连接失败补齐真实 Run 前置拒绝证据；
3. 通过 L2 真实 `.env` 链验证正常 Run，不把真实 key 写进测试输出。

### 验收标准

- 创建、编辑、启停和查看模型配置通过；
- GET、列表、审计和错误日志均没有 API key 明文；
- Run/Thread/GraphHarbor payload 只携带模型标识或非敏感 Context，不携带 URL credential 或 key；
- 禁用模型、协议不支持、连接失败在 Provider 调用前或连接边界明确失败；
- 替换 API key 后下一次请求使用新值，无需重启；
- L2 只证明本地进程链和已授权 `.env` 模型调用，不证明生产 Secret Store 或生产身份体系。

## 7. 决策状态（owner 已确认）

| 决策 | 状态 |
| --- | --- |
| V1 字段采用 provider、display_name、base_url、protocol、model、api_key、enabled | `Accepted` |
| API key write-only，读取只返回 configured/redacted | `Accepted` |
| 配置与凭据分离；本地使用部署级 master key 加密 | `Accepted` |
| 先完成本地 L1/L2/L3，再单独讨论生产治理 | `Accepted` |
| Secret Store、统一生产模型代理和复杂权限 | `Superseded/Rejected` |
| 是否引入 execution_model_id/revision、JWKS/workload identity | `Superseded/Rejected`；未来只能另立 change |
