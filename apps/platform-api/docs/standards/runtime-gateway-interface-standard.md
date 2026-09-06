# Platform API Runtime Gateway / 管理接口标准

文档类型：`Current Standard`

这份文档定义 `platform-api` 在 **runtime gateway / formal platform management interface** 上的当前标准。

如果你要判断：

- 正式平台接口应该怎么暴露 runtime 能力
- 平台管理接口的边界应该落在哪
- runtime 公开契约经由 control plane 暴露时，先遵守哪条规则

先读本文。

如果你要看模块分层和代码结构，再读：

- `../handbook/project-handbook.md`
- `../handbook/development-playbook.md`

如果你要看治理三件套，再分别读：

- `permission-standard.md`
- `audit-standard.md`
- `operations-standard.md`

---

## 1. 适用范围

下面这些情况优先读本文：

- 变更 `platform-web -> platform-api` 的正式平台接口
- 变更 `platform-api -> runtime-service` 的 runtime gateway 暴露面
- 变更平台管理接口的 request / response / normalize / project scope 注入口径
- 变更会影响正式管理页、工作台入口、或受治理的 runtime 调用方式
- 判断某个字段应该留在 control plane，还是继续透传给 runtime

---

## 2. 核心边界

### 2.0 Agent Server 与产品 Agent 分离

Platform 的产品对象统一称为 Agent，稳定执行键为 `agent_key = graph_id`。GraphHarbor 是通用
LangGraph-compatible Agent Server，只持有 Thread/Run/Checkpoint/Event 执行事实；Platform API
不通过创建、更新或删除 upstream Assistant 来同步产品数据。历史 `assistant` 字段和 URL 仅在有
characterization fixture 的读取兼容边界保留。

Runtime delegation 的 `scope.operation` 只允许 `read` 或 `run-create`，按请求边界签发；缺失、
未知或越权 scope 必须在 Runtime Auth 处 fail closed。

### 2.1 control plane 负责治理，不吞 runtime 执行

`platform-api` 负责：

- 项目边界
- actor / permission 上下文
- 审计与 operation 接入
- 正式平台接口
- 对 runtime 的协议整形与受控访问

`platform-api` 不负责：

- graph 编排
- tool / MCP 选择
- runtime 内部 prompt / middleware 策略
- 结果域内部资源语义的 current-standard 定义

### 2.2 正式平台入口不绕过 control plane

正式平台链路固定为：

```text
platform-web -> platform-api -> runtime-service
```

所以：

- 正式平台前端不应直接打 `runtime-service`
- 正式平台读取结果域时也不应绕过 control plane

### 2.3 runtime gateway 优先保持 runtime contract 兼容

当 control plane 暴露 runtime 能力时：

- 优先在 adapter / normalize 层收差异
- 不要求前端理解两套平台私有协议
- 不把 control plane 的治理字段反向污染成 runtime business contract

### 2.4 正式管理接口变更属于 governed surface

下面这些一旦改变，默认按 governed surface 处理：

- 平台管理接口的输入/输出契约
- runtime gateway 对外公开的 contract 语义
- project scope 注入与项目边界行为
- 供 `platform-web` 正式消费的管理接口字段

### 2.5 formal interface 变更必须走真实验证

验证顺序固定为：

1. `platform-api` 本地契约 / 单测 / 集成证明
2. 最短相关真实链路
   - `platform-web -> platform-api`
   - 或 `platform-api -> runtime-service`
   - 或 `platform-api -> interaction-data-service`
3. 只有当公开 managed interface 本身被改动时，才要求正式平台链路验证

### 2.6 模型配置与运行目标

模型管理只提供七个字段：`provider`、`display_name`、`base_url`、`protocol`、`model`、
`api_key`、`enabled`。`api_key` 只写不读，由 Platform API 使用部署级 master key 加密；列表和
详情只返回 `credential_configured`。Gateway 只把已启用且有项目权限的逻辑 `model` 写入标准
Run `context`，不向浏览器、GraphHarbor、日志或审计详情暴露连接密钥，也不引入独立模型代理、
`execution_model_id` 或 Secret Store 编排。

运行目标统一使用 Agent 的 `agent_key = graph_id`。SDK 需要的 `assistant_id` 只是标准协议字段，
由 Gateway 从已校验的 Agent key 填充；Platform 不创建或同步 upstream Assistant。

---

## 3. leaf resolver rule

### Leaf A：control-plane module / ownership / code-shape

先读：

- `../handbook/project-handbook.md`
- `../handbook/development-playbook.md`

适用于：

- 这个能力应落在哪个模块
- handler / use case / repository / adapter 如何分工
- 哪层拥有该行为

### Leaf B：permission / audit / operation governance

分别读：

- `permission-standard.md`
- `audit-standard.md`
- `operations-standard.md`

适用于：

- 谁能做
- 如何追责
- 长任务是否必须进入 operation

### Leaf C：runtime gateway / formal management interface

先读本文。

适用于：

- 正式平台接口如何暴露 runtime 能力
- 项目边界与 runtime gateway 的治理边界
- 平台管理接口与 runtime public contract 的受管面判断

不适用于：

- `platform-api -> interaction-data-service` 一侧的结果域资源语义判断
- 结果域服务内部 API / payload / resource 的 current truth

这些问题应转到 `interaction-data-service` 的 result-domain boundary leaf。

### 组合规则

- 如果问题是 **“这个能力应该落在哪个模块、怎么分层？”**
  - 先读 **Leaf A**
- 如果问题是 **“谁能做、怎么记审计、是否必须走 operation？”**
  - 先读 **Leaf B**
- 如果问题是 **“这个正式管理接口 / runtime gateway 对外该怎么表现？”**
  - 先读 **Leaf C**

---

## 4. supporting evidence

当前这片受管面的 supporting docs 包括：

- `../decisions/chat-use-stream-contract.md`
- `../delivery/runtime-contract-three-wave-checklist.md`
- `../delivery/runtime-contract-manual-integration-checklist.md`

这些文档提供现行决策与验收事实，但不替代本文 current-standard 的角色。

模型连接配置由 Platform Catalog 唯一持有。Run 创建时 Gateway 只向 Agent Server 传递短期 opaque
`_runtime_model_ref`；Runtime 通过受控内部端点按项目校验引用并读取解密连接。API key 不得进入浏览器响应、Run
快照、GraphHarbor 持久化或普通日志。
