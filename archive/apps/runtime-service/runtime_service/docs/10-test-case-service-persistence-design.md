# test_case_service 持久化设计

状态：`Current Local Design`

这篇文档描述当前 `test_case_service -> interaction-data-service` 的正式持久化设计。

当前代码真相源建议同时参考：

- `runtime_service/services/test_case_service/document_persistence.py`
- `runtime_service/services/test_case_service/tools.py`
- `runtime_service/services/test_case_service/middleware.py`
- `apps/interaction-data-service/app/api/test_case_service/**`

## 目标

为 `runtime_service/services/test_case_service` 增加一条最小但稳定的正式落库链路：

```text
多模态输入
  -> 需求分析 / 策略 / 用例设计 / 评审 / 格式化
  -> persist_test_case_results
  -> interaction-data-service HTTP API
  -> test_case_documents / test_cases
```

本设计明确不复用 `usecase_workflow_agent` 的 workflow / snapshot / review 编排模型。

## 设计原则

1. 只保留一个模型可见持久化工具：`persist_test_case_results`
2. 只保留两类远端资源：`documents` 和 `test-cases`
3. 共享 HTTP client 只抽传输层，不抽业务 payload
4. `project_id` 等受信参数以 `runtime.context` 为主，旧透传位置仅作为治理收口中的历史兼容参考
5. `project_id` 缺失时必须显式报错，不能再静默回退默认项目
6. `test_case_service` 在未显式传 `model_id` 时，服务级默认主模型使用 `deepseek_chat`

## runtime-service 侧结构

### 1. 服务私有工具

新增：

- `runtime_service/services/test_case_service/tools.py`

职责：

- 解析 `ToolRuntime`
- 读取 `project_id / thread_id / run_id / batch_id`
- 从 `multimodal_attachments` 构造文档持久化 payload
- 从最终测试用例构造测试用例持久化 payload
- 调用共享 HTTP client

实现注意：

- `persist_test_case_results` 的 `runtime` 参数必须使用标准 `ToolRuntime[...]` 注入形式
- 不要把 `runtime` 写成可选参数
- 不要再为这个工具显式绑定 `args_schema`
- 该工具应由函数签名自动推导 schema，否则 LangGraph 可能无法正确注入 `runtime`

### 1.1 二期职责调整

二期后 `persist_test_case_results` 不再承担“首次写入 document”的职责。

它只负责：

- 读取运行态里已经持久化成功的 `document_id`
- 对缺失 `document_id` 的附件做补偿写入
- 写入最终正式 `test_cases`
- 建立 `source_document_ids` 关联

### 1.2 服务专属即时持久化层

二期新增：

- `runtime_service/services/test_case_service/document_persistence.py`
- `runtime_service/services/test_case_service/middleware.py`

职责：

- 在 `test_case_service` 作用域内即时持久化已解析附件
- 基于附件 fingerprint 做幂等
- 将 `persisted_document_id / persist_status / persisted_at / persist_error` 回填到附件状态

约束：

- 通用 `runtime_service/middlewares/multimodal/*` 不耦合 testcase 落库逻辑
- 即时持久化逻辑只允许出现在 `test_case_service` 私有层

### 1.3 原始 PDF 资产持久化

三期前置能力放在本轮二期一并落地：

- 在 document 元数据写入前，先尝试保存原始 PDF 文件资产
- 成功后将 `storage_path` 回填到 document payload
- 失败时允许 document 元数据继续写入，但要明确标记“无原始资产”

实现原则：

1. 原始文件资产持久化只出现在 `test_case_service` 私有层
2. 通用多模态中间件仍不承载任何 testcase 专属落库逻辑
3. 不把 PDF 二进制塞进 graph state 或 document JSON
4. 上传原始 PDF 时，必须优先读取当前请求 `messages` 中的原始 `file` block，而不是依赖 `state["messages"]`

### 2. 共享 HTTP client

新增：

- `runtime_service/integrations/interaction_data.py`

抽象边界：

- 负责 base_url / token / timeout / headers / HTTP JSON 请求
- 不理解任何具体业务字段
- 不替各服务组装 payload

这样其他服务后续也能复用同一个 client，但不会被 `test_case_service` 的数据结构绑死。

二期补充：

- 同一 client 继续只抽 HTTP 传输层
- `documents/assets` 的 multipart 上传也统一经该集成层发出
- 业务层自己决定何时先传原始文件、何时再写 document 元数据

### 3. 项目上下文标准化策略

解析顺序：

1. `runtime.context.project_id`
2. `runtime.config.configurable.project_id`
3. `runtime.config.metadata.project_id`
4. `runtime.state.project_id`

标准约束：

1. `runtime.context.project_id` 升级为运行时标准字段
2. `platform-api` 必须把当前项目写入 `payload.context.project_id`
3. `platform-api` 不再把 `project_id` 注入 `payload.config.configurable / payload.config.metadata / payload.metadata`
4. `runtime-service` 只认 `runtime.context.project_id`
5. `runtime.state.project_id` 不再读取
6. `test_case_service` 不再保留 `test_case_default_project_id`

保留项：

- `test_case_default_model_id = deepseek_chat`

下线项：

- `test_case_default_project_id` 不再作为平台真实链路的隐式兜底

### 3.1 平台到运行时的可信传播链路

```text
platform-web WorkspaceContext.projectId
  -> x-project-id header
  -> platform-api LangGraph gateway
  -> payload.context.project_id
  -> runtime.context.project_id
  -> test_case_service document/tool persistence
  -> interaction-data-service.project_id
```

要求：

1. 前端只负责携带当前项目 header，不自己拼业务 `project_id`
2. `platform-api` 负责把 header 中的受信项目写入 LangGraph run payload
3. `runtime-service` 统一从标准运行时字段读取，不再各服务自己发明透传入口
4. `interaction-data-service` 只接收最终明确的 `project_id`

### 3.2 缺失项目上下文时的行为

平台真实链路下：

1. 上传 PDF 且进入 `test_case_service` 文档即时持久化时，若拿不到 `project_id`，直接返回显式错误
2. `persist_test_case_results` 若拿不到 `project_id`，直接返回结构化失败结果，不写 `test_cases`
3. 不能把数据写入 `00000000-0000-0000-0000-000000000001`

本地调试链路下：

1. 仍然要求显式传 `RuntimeContext.project_id`
2. 不提供 default project fallback

## interaction-data-service 侧结构

采用“每个服务一个专属接口前缀”的范式：

- `POST /api/test-case-service/documents`
- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`
- `POST /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

旧的 `/api/usecase-generation/*` 已退役，不再作为主路径。

## 数据落点

### 1. `test_case_documents`

存附件解析结果：

- `project_id`
- `batch_id`
- `filename`
- `content_type`
- `source_kind`
- `parse_status`
- `summary_for_model`
- `parsed_text`
- `structured_data`
- `provenance`
- `confidence`
- `error`
- `idempotency_key`（二期用于上传即落库幂等）
- `storage_path`（二期用于原始附件预览与下载）

二期约定：

- `provenance.runtime.thread_id`
- `provenance.runtime.run_id`
- `provenance.runtime.agent_key`

这些值统一由 `test_case_service` 在 document 即时持久化时补入，供平台页做追溯展示。

### 2. `test_cases`

存最终正式测试用例：

- `project_id`
- `batch_id`
- `idempotency_key`（三期前置能力本轮一并落地，用于正式 testcase 幂等覆盖）
- `case_id`
- `title`
- `description`
- `status`
- `module_name`
- `priority`
- `source_document_ids`
- `content_json`

其中完整业务结果和运行时元数据全部收敛到 `content_json.meta`。

三期前置能力本轮一并落地：

- `persist_test_case_results` 在写 `test_cases` 时自动生成稳定 `idempotency_key`
- 当前策略：
  - 优先使用 `case_id`
  - 若没有 `case_id`，退化到 `title + module_name + test_type`
  - 同一 bundle 内若出现相同逻辑身份，再追加出现序号区分
- `interaction-data-service` 在命中已有 `(project_id, batch_id, idempotency_key)` 时不再插入新行，而是覆盖旧 testcase 内容

边界：

- 这条幂等语义只用于 `test_case_service` 的自动正式保存
- 平台人工 CRUD 仍保持普通新增 / 编辑 / 删除，不强行做唯一约束

## 调试与验证要求

禁止 mock 持久化链路。

验证必须同时满足：

1. 使用真实附件或真实业务需求文本
2. 使用真实模型
3. 调用真实 `interaction-data-service`
4. 最终通过远端查询接口确认文档和测试用例已写入
5. 抓取并分析：
   - 流式输出内容
   - 工具调用记录
   - 远端返回结果
   - 最终异常或成功状态

二期额外要求：

1. 在不调用 `persist_test_case_results` 的前提下，上传真实附件后应立即能在 `test_case_documents` 中查到记录
2. 同一附件同一项目重复重试时，document 不得重复插入
3. 后续正式保存 testcase 时，必须复用既有 `document_id`
4. 若原始附件资产上传成功，document 记录中必须带有可用 `storage_path`
5. `provenance.runtime` 中必须能看到 `thread_id / run_id / agent_key`
6. 真实前端或真实 LangGraph run 请求中必须显式携带当前项目，最终落库不能再命中默认项目

推荐使用四个真实验证脚本：

```bash
cd apps/runtime-service
uv run python runtime_service/tests/services_test_case_service_document_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --model-id deepseek_chat \
  --timeout 900 \
  --interaction-timeout 60

uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --model-id deepseek_chat \
  --timeout 900

uv run python runtime_service/tests/services_test_case_service_case_idempotency_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d

uv run python runtime_service/tests/services_test_case_service_project_scope_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --model-id deepseek_chat
```

含义：

1. `services_test_case_service_document_live.py`
   - 真实上传附件
   - 不允许调用 `persist_test_case_results`
   - 验证 `TestCaseDocumentPersistenceMiddleware` 是否完成“上传即落库”
   - 同一 `batch_id` 连续跑两次，验证 document 幂等
2. `services_test_case_service_persistence_live.py`
   - 真实生成正式测试用例
   - 调用 `persist_test_case_results`
   - 验证 `test_cases` 写入以及 `source_document_ids` 关联
3. `services_test_case_service_case_idempotency_live.py`
   - 不依赖模型随机输出
   - 使用真实 `interaction-data-service` 和真实业务字段构造两轮 testcase 写入
   - 第二轮命中同一逻辑身份时必须覆盖旧记录而不是新增脏数据
4. `services_test_case_service_project_scope_live.py`
   - 强制经过 `platform-api` LangGraph 网关
   - 正向验证 `x-project-id -> platform-api -> runtime-service -> interaction-data-service` 的真实注入链路
   - 负向验证缺失 `x-project-id` 时必须返回 `400 test_case_project_id_required`
   - 同时确认默认项目不会被脏写入

## 实现陷阱与修复点

### 1. middleware 阶段不能假设 `runtime.config` 一定存在

`persist_test_case_results` 工具里拿到的是 `ToolRuntime`，它有 `config/state`。

但 `wrap_model_call` 中间件里拿到的是 `langgraph.runtime.Runtime`，默认只有：

- `context`
- `store`
- `stream_writer`
- `previous`

没有 `config`。

因此 `test_case_service` 的文档即时持久化层必须这样取配置：

1. 优先读 `runtime.config`
2. 若不存在，则回退到 `langgraph.config.get_config()`

否则中间件阶段会拿不到：

- `interaction_data_service_url`
- `project_id`
- `batch_id`

最终表现为“即时落库没有真正发生”。

### 2. `wrap_model_call` 里的 `request.override(state=...)` 不等于 graph state 已更新

`wrap_model_call` 内改过的 `request.state` 只保证“本次模型调用能看到”。

如果希望后续工具节点也能读到这些状态，例如：

- `persisted_document_id`
- `persist_status`
- `persisted_at`

就必须额外返回：

- `ExtendedModelResponse`
- `Command(update=...)`

把附件状态显式写回 graph state。

否则会出现：

1. 文档即时落库已经成功
2. 但后续 `persist_test_case_results` 仍看不到 `persisted_document_id`
3. `source_document_ids` 为空
4. testcase 与 document 无法关联

当前修复方案：

1. `document_persistence.py` 在 middleware 阶段回退使用 `get_config()`
2. `TestCaseDocumentPersistenceMiddleware` 在 `wrap_model_call/awrap_model_call` 返回 `ExtendedModelResponse + Command(update=...)`
3. 工具阶段复用 graph state 中已回填的 `persisted_document_id`

### 3. 原始 PDF 下载不是页面问题，而是资产链路问题

如果平台要支持：

- 在线预览原始 PDF
- 下载原始 PDF

则 `runtime-service` 不能只写：

- `summary_for_model`
- `parsed_text`
- `structured_data`

还必须补一条真实资产链路：

```text
frontend upload
  -> multimodal attachment
  -> test_case_service private persistence
  -> interaction-data-service /documents/assets
  -> storage_path
  -> documents metadata
```

否则页面只能看到解析结果，无法回看原始文件。

补充约束：

- `TestCaseDocumentPersistenceMiddleware` 必须使用当前 `ModelRequest.messages` 回溯原始附件 payload
- 不能假设 `request.state` 内一定保留了原始 `messages`

### 4. 运行时追踪字段必须写入 provenance.runtime

平台二期需要展示：

- 当前 document 来自哪个 thread
- 当前 document 来自哪个 run
- 当前 document 属于哪个 agent

最小实现不新增表字段，统一写入：

```json
{
  "provenance": {
    "runtime": {
      "thread_id": "...",
      "run_id": "...",
      "agent_key": "test_case_service"
    }
  }
}
```

这样 `interaction-data-service` 与 `platform-api` 都能直接复用。

## 已完成真实验证

已通过以下命令完成一轮真实落库验证：

```bash
cd apps/runtime-service
uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --model-id deepseek_chat \
  --timeout 900
```

验证结果：

1. `persist_test_case_results` 已被真实调用
2. `interaction-data-service` 远端查询确认：
   - `documents_total = 1`
   - `test_cases_total = 4`
3. 退出码为 `0`

说明当前最小持久化架构已经可用。
