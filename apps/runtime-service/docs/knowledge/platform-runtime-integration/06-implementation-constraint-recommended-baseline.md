# 模型配置实施约束（V1 最小方案）

- 适用范围：Platform API 模型管理、Runtime Gateway、Runtime 模型构造。
- 状态：`Accepted by owner; implementation-partial`。

## 1. 边界

Platform API 是模型配置的唯一写入方；Platform Web 只提交表单和展示脱敏状态；GraphHarbor 只接收标准
Run/Context，不保存 Platform 模型密钥；Runtime 在服务端调用边界使用已保存连接配置。

模型记录字段固定为：`provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled`。
不增加 revision、execution reference、credential version 或代理身份字段。

## 2. 凭据保护

当前没有可复用 Secret Store，因此使用 Platform API 部署级 `PLATFORM_API_MODEL_CONFIG_MASTER_KEY`：

1. API key 仅在 POST/PUT 请求体出现；
2. 服务端用现有依赖加密后写数据库；
3. GET/list 只返回 `credential_configured`，当前不返回末四位摘要；
4. Runtime 请求时服务端解密，绝不把 key 放进 Context、Thread、GraphHarbor 或日志；
5. master key 缺失、密文损坏或解密失败立即 fail closed。

以后接入 Secret Store 只替换第 2/4 步，不改变模型管理 API。

## 3. 输入校验

- `provider`、`base_url`、`protocol`、`model` 必填；
- `base_url` 当前只实现 `http`/`https` 和非空 host 校验；在开放任意管理员 URL 前，还需补嵌入凭据和本地/私网地址拒绝测试。
- `protocol` 使用已有 Provider adapter 支持的枚举；
- `enabled=false` 禁止新 Run 使用；
- 客户端不得提交 `tools`、身份、project、secret_ref 等字段；未知字段 fail closed。

## 4. 功能点记录

| 功能点 | 代码落点 | 验证 |
| --- | --- | --- |
| DTO/校验 | `apps/platform-api/app/modules/runtime_catalog` | unit + HTTP 422 |
| 加密/解密 | 同模块 credential helper/repository | key 不出现在响应、日志、异常 |
| CRUD/启停 | 同模块 service/http | 权限、disabled、轮换测试 |
| Run 使用 | `runtime_gateway`/Runtime model construction | 服务端读取最新配置 |
| 文档/审计 | 本目录 + OpenSpec verification | 命令、结果、未覆盖边界齐全 |

## 5. 已废弃项

生产统一代理、Provider allowlist/SLO、DRI/runbook、Secret Store API、RS256/JWKS、workload identity、
mTLS、revision registry 和 capability probe 均已废弃（`Superseded/Rejected`）。它们不属于本轮实现；未来
若有真实需求必须另立 change。
