# Open SWE 模型配置借鉴与本项目 V1 方案

## 1. 借鉴结论

Open SWE 的有用做法是：模型构造入口集中、Provider 协议明确、凭据只写不读、请求时读取最新凭据、
错误在模型调用边界返回。它的团队模型设置、复杂 fallback、Sandbox 和多层 credential provider 不属于
本项目当前需求。

参考：`docs/user/guide/providers.zh.md`、`docs/subsystems/credentials.zh.md`、ProviderEditor 和
`packages/llm/llm-pi-ai/src/config.ts`。

## 2. 本项目 V1

模型录入只需要：`provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled`。
其中 `api_key` 只出现在创建/轮换请求，读取接口返回 `credential_configured`，不返回密钥。

```text
管理员 -> Platform API 校验字段 -> 加密保存配置和 key
用户   -> Platform API 查询脱敏模型列表
Run    -> 服务端按 enabled 模型读取并解密 key -> Provider
```

数据库中的密钥使用部署级 master key 加密。master key 不写入仓库；缺失、解密失败、协议不支持或连接
失败时直接返回安全错误，不能换模型、读任意环境变量或回退其他 Provider。

## 3. 不照搬的设计

当前不实现 `execution_model_id`、`model_revision`、动态 Provider catalog、capability probe、生产模型
代理、JWKS/workload identity/mTLS、Secret Store 编排、复杂能力声明和跨 Provider fallback。这些旧方案均
已标记为 `Superseded/Rejected`；出现真实部署边界时另立变更，不能回填本 V1 契约。

## 4. 验证矩阵

| 场景 | 预期 |
| --- | --- |
| 合法 URL/协议/模型/key | 保存成功，响应无 key |
| 缺 URL/协议/模型 | 422，Provider 调用数为 0 |
| GET/list | 只有非敏感字段和 configured 状态 |
| disabled 模型 | 新 Run 在 Provider 前拒绝 |
| master key 缺失/解密失败 | fail closed，不换模型 |
| 错误 key/连接超时 | 安全错误，不记录 key 或响应正文 |
| 更新 key 后下一次请求 | 使用新值，无需重启 |

代码和命令结果记录在 OpenSpec `verification.md`；本文件不把本地 `.env` smoke 写成生产代理证据。
