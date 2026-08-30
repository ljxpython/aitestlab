# runtime_service 多模态中间件实现说明（Phase 1）

## 1. 当前状态

当前多模态能力已经在仓库中落地，而不再只是设计草案。

核心实现目录：`runtime_service/middlewares/multimodal/`

已接入的 graph / agent 路径包括：

- `runtime_service/agents/assistant_agent/graph.py`
- `runtime_service/agents/deepagent_agent/graph.py`
- `runtime_service/agents/customer_support_agent/tools.py`
- `runtime_service/agents/personal_assistant_agent/tools.py`
- `runtime_service/agents/skills_sql_assistant_agent/tools.py`

对应测试：`runtime_service/tests/test_multimodal_middleware.py`

### 本地自测（devtools，开发期使用）

为了在不依赖前端的情况下复现/自测多模态输入，可以使用：

- `runtime_service/devtools/multimodal_frontend_compat.py`：构造/编码与前端一致形状的 content blocks（模拟 `{type,mimeType,data,metadata}`）。
- `runtime_service/devtools/dump_multimodal_fixtures.py`：从本地 fixtures 生成/导出可复用的多模态测试数据。

运行：

```bash
./.venv/bin/python -m runtime_service.devtools.dump_multimodal_fixtures
```

## 2. 已完成范围

当前 Phase 1 已完成：

- 前端附件 block 归一化
- 附件类型识别（image/pdf/doc/docx/xlsx/file/other）
- 多模态摘要注入 system prompt
- `multimodal_attachments` / `multimodal_summary` 写入 state
- fail-soft 解析路径与回归测试

## 3. 设计边界仍然有效

虽然实现已落地，但以下设计原则仍然成立：

- `create_agent(...)`
- `create_deep_agent(...)`

前端已经开始发送多模态消息块，例如：

- 图片：`{ type: "image", mimeType, data, metadata }`
- PDF：`{ type: "file", mimeType: "application/pdf", data, metadata }`

但当前执行层存在两个现实问题：

1. 运行时协议尚未与 Python LangChain 侧的多模态格式完全对齐。
2. 某些工具辅助路径会把 rich content 压成纯文本，只提取 `text`，非文本块会被忽略。

因此，这个问题的本质不是“某个 agent 不会看图”，而是：

> **执行层缺少一个统一的多模态输入适配与增强层。**

---

## 4. 当前仍然坚持的目标

这份设计稿的目标不是立刻实现视觉理解，而是先定义一条长期稳定的架构路线。

核心目标：

- 让 `create_agent` / `deepagent` 都能接入统一的多模态预处理能力。
- 保留前端原始附件输入，不做不可追溯的覆盖式改写。
- 将图片 / PDF / 未来 doc、docx 等类型统一纳入一个可扩展协议。
- 把“输入适配”与“业务推理”分层，避免每个 graph 自己重复处理附件。

一句话概括：

> **在 graph 执行前增加一个共享的多模态中间层，把附件转成“模型可理解、系统可追踪、后续可扩展”的标准化结果。**

---

## 5. 为什么选择中间件，而不是把逻辑塞进 graph

这是这份方案最核心的设计判断。

### 3.1 这是横切能力，不是单个 graph 的业务逻辑

多模态处理并不是 `assistant` 独有需求，也不是 `deepagent_demo` 独有需求。

它更像：

- 输入识别
- 预处理
- 协议适配
- 能力增强

这类能力天然属于“横切关注点（cross-cutting concern）”。

如果把它直接写进每个 graph：

- 每个 graph 都要自己判断 `image / pdf / doc`
- 每个 graph 都要自己调视觉模型
- 每个 graph 都要自己定义解析结果格式

最终会快速失控。

### 3.2 `create_agent` 天然支持 middleware 语义

当前仓库已经有明确证据表明：

- `assistant` 已预留 `middleware=[]`
- `assistant` 使用了 `HumanInTheLoopMiddleware`
- `customer_support` / `skills_sql_assistant` 已使用 `wrap_model_call` 风格 middleware

这说明：

> **“在模型调用前做统一处理”本来就是当前仓库接受的设计方式。**

### 3.3 对 deepagent 的结论

`deepagent` 当前代码里没有看到与 `create_agent` 完全相同的 `middleware=[...]` 挂载形式。

所以这里要把概念说准：

- 对 `create_agent`，这层能力可以直接表现为 middleware。
- 对 `create_deep_agent`，如果官方挂点不完全一致，则应实现为**等价的共享输入增强层**。

也就是说，本方案强调的是：

> **中间件式职责边界**，而不是死扣某一个 API 参数名。

---

## 6. 为什么要“增强，不覆盖”

这是第二个核心判断。

我们明确不推荐这样做：

- 收到图片/PDF
- 直接调用视觉模型
- 用视觉模型生成的一段文本完全替换原始输入

因为这会带来三个问题：

### 4.1 原始输入丢失

一旦替换掉原始附件：

- 后续无法追溯用户真正传了什么
- 调试时无法区分“用户输入”和“模型推断”
- 视觉/OCR 误判会被伪装成用户原始意图

### 4.2 错误不可见

如果视觉模型看错了：

- 主 agent 会基于错误结果继续推理
- 但执行层很难知道这是“视觉解析错误”还是“用户原始输入本就如此”

### 4.3 不利于后续升级

未来一旦支持：

- doc / docx
- xlsx
- 更复杂 PDF
- 视频 / 音频

如果今天就走覆盖式改写，后面很难演进为更精细的协议。

因此本方案采用：

> **增强（augment），而不是覆盖（overwrite）。**

即：

- 原始附件块保留
- 解析结果作为附加信息加入系统状态
- 只把“短摘要”投影给主模型

---

## 7. 为什么要把结果“回填”

这里需要特别解释，因为这一步最容易被误解。

“回填”不是指把所有 OCR 文本和结构化结果一股脑塞回 `context`。

更准确地说，是：

> **把多模态处理结果分层回填到不同位置，让不同消费者看到自己需要的信息。**

### 5.1 原始附件块

保留在原始消息中，作为事实来源（source of truth）。

作用：

- 审计
- 追溯
- 二次处理
- 后续 tool/node 再消费

### 5.2 结构化解析结果

放入 graph state 中。

作用：

- 给后续节点 / tool / specialized agent 使用
- 保存 OCR / 文档解析 / 表格抽取 / 页面信息
- 记录错误、置信度、来源、耗时等系统级数据

### 5.3 给主模型看的短摘要

只把一小段适合推理的文本，投影到模型可见上下文。

例如：

- `用户上传了 1 张后台报错截图，OCR 提取到 “Internal Server Error /api/orders”。`
- `用户上传了 1 个 3 页 PDF，摘要为：这是 2026 Q1 营收报告。`

作用：

- 让主模型知道“用户发了什么附件”
- 让主模型可以基于附件信息继续推理
- 避免把庞大解析结果直接塞进 prompt，导致成本和噪声上升

所以“回填”的真实目的不是存档，而是：

> **让原始输入、系统解析结果、模型可见摘要三者分层存在。**

---

## 8. 分层设计

推荐把整个多模态处理链拆成 4 层。

### Layer 1：Attachment Detection（附件识别层）

职责：

- 扫描用户消息中的 `content` block
- 识别是否包含附件
- 判断附件类型

当前重点支持：

- `image/*`
- `application/pdf`

未来扩展：

- `application/msword`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `application/vnd.ms-excel`
- `text/csv`

### Layer 2：Attachment Parser Router（解析路由层）

职责：

- 根据附件类型选择处理器

例如：

- 图片 -> 视觉模型 / OCR
- PDF -> 文档解析 / OCR / 视觉模型
- DOC/DOCX -> 文档解析器

这层只负责“选路由”，不负责业务推理。

### Layer 3：Normalized Artifact Store（标准化产物层）

职责：

- 把不同解析器的结果统一整理成稳定的数据结构
- 存入 graph state

这是后续系统扩展的关键。

### Layer 4：Model Projection（模型投影层）

职责：

- 只把短小、稳定、适合推理的摘要暴露给主模型

这层解决的是：

- 模型需要“知道附件内容”
- 但不应该直接吞整份 OCR 全文或 PDF 全文

---

## 9. 统一数据契约

这是整个设计最重要的长期资产。

建议为每个附件产出统一结构：

```json
{
  "attachment_id": "att_xxx",
  "kind": "image",
  "mime_type": "image/png",
  "status": "parsed",
  "summary_for_model": "一张后台报错截图，包含 500 错误与 /api/orders 路径。",
  "parsed_text": "Internal Server Error ... /api/orders ...",
  "structured_data": {
    "entities": ["500", "/api/orders"]
  },
  "provenance": {
    "processor": "vision-ocr-v1"
  },
  "confidence": 0.86,
  "error": null
}
```

### 关键字段建议

- `attachment_id`：稳定引用
- `kind`：`image | pdf | doc | docx | xlsx | other`
- `mime_type`：真实 MIME
- `status`：`unprocessed | parsed | unsupported | failed`
- `summary_for_model`：给模型的短摘要
- `parsed_text`：抽取文本
- `structured_data`：表格、字段、实体等
- `provenance`：由哪个处理器生成
- `confidence`：置信度（可选）
- `error`：失败时的结构化错误

### 为什么这份契约重要

因为以后新增类型时，只要新增：

- 一个识别规则
- 一个解析器
- 一条路由

而不需要重新发明整套协议。

---

## 8. 图片与 PDF 为什么必须分开处理

这个判断是明确的。

### 8.1 图片

图片更接近：

- UI 截图
- 图表
- 证件照片
- 纯视觉信息

典型处理：

- 视觉描述
- OCR
- 图表理解
- 页面结构识别

### 8.2 PDF

PDF 更像“文档容器”，它可能是：

- 文本型 PDF
- 扫描型 PDF
- 图文混排 PDF
- 含表格的报告

典型处理：

- 文本抽取
- 分页解析
- OCR（扫描件）
- 表格抽取
- 文档摘要

也就是说：

> **PDF 不是一张大图片。**

所以不应该简单复用图片处理路径。

### 8.3 未来 doc / docx

未来 `doc` / `docx` 也应该走独立分支。

原因：

- 它们的结构与 PDF 不同
- 文本抽取路径不同
- 页概念也不一定一致

因此推荐统一原则是：

- `image` 一类
- `pdf` 一类
- `office/doc` 一类

而不是所有文件全塞进一个“file processor”。

---

## 9. 推荐的落点：state / context / message / metadata 怎么分工

### 9.1 message

保留原始附件块。

用途：

- 原始事实
- 会话追溯
- 二次处理输入

### 9.2 state

作为多模态处理结果的主要承载位置。

用途：

- 全量解析结果
- OCR 文本
- 结构化抽取
- 解析失败信息
- 后续节点消费

这是本方案推荐的**主存储位置**。

### 9.3 context

只建议放简短、稳定、对主模型推理有帮助的摘要。

不要放：

- 大段 OCR 文本
- 全文档全文
- 大量中间诊断信息

### 9.4 metadata

放调试/观测信息，例如：

- 解析器名称
- 处理耗时
- MIME 检测来源
- 失败原因码

一句话总结：

- `message`：原件
- `state`：全量解析结果
- `context`：给模型的短摘要
- `metadata`：系统观测信息

---

## 10. 失败策略（必须 fail-soft）

多模态中间层不应该把所有解析失败都升级成 graph 整体失败。

推荐策略：

### 10.1 不支持的类型

- 标记 `unsupported`
- 保留原始附件
- 不中断主流程

### 10.2 视觉 / OCR / 文档解析失败

- 标记 `failed`
- 写入结构化错误
- 主流程继续

### 10.3 低质量解析

- 允许存在低置信度结果
- 但不要把它伪装成高可信事实

### 10.4 超大文件

- 不要把全文直接推给主模型
- 只保留摘要进模型可见上下文
- 全量结果留在 state

总原则：

> **多模态增强默认是增益能力，不应轻易变成图执行的单点故障。**

---

## 11. 与当前仓库风格的契合点

这份方案不是空中楼阁，它和当前仓库风格是对齐的。

### 11.1 与 `create_agent` 对齐

当前仓库已使用 middleware 模式：

- `HumanInTheLoopMiddleware`
- `wrap_model_call`

说明：

> 在模型调用前后做统一处理，是当前代码风格允许且认可的方式。

### 11.2 与 `deepagent` 对齐

`deepagent_demo` 当前走的是官方薄封装风格。

因此这里不建议把多模态逻辑散落进每个 subagent，而是应保持：

- 共享输入增强层
- deepagent 只消费增强后的标准化结果

### 11.3 与 runtime context 设计对齐

`RuntimeContext` 已经是当前系统的统一运行时上下文入口。

多模态摘要如果需要暴露给主模型，应尽量保持：

- 小
- 稳定
- 清晰

而不是把复杂解析结果直接塞满上下文。

---

## 12. 推荐实施顺序（不涉及具体代码）

### Phase 1：协议先行

先定义清楚：

- 输入块格式
- 归一化附件结构
- 状态存放位置
- 模型可见摘要规则

当前仓库 Phase 1 已落地的范围：

- 在 `runtime_service/middlewares/` 新增共享 `MultimodalMiddleware`
- 在模型调用前把前端 `image/file + mimeType/data` 归一化为 Python LangChain 兼容字段（`mime_type/base64`）
- 为附件生成统一的结构化 contract，并写入 agent state
- 为主模型注入紧凑的附件摘要（只做存在性与状态说明，不做 OCR/视觉/文档语义解析）
- `create_agent` 与 `create_deep_agent` 入口统一接入这层 middleware

Phase 1 仍然**不会**做：

- 真实视觉模型调用
- PDF 文本抽取
- OCR
- doc/docx 语义解析
- file_id / object storage 上传链路

### Phase 2：真实解析（当前仓库已开始落地 image/pdf）

当前仓库 Phase 2 已落地的范围：

- 共享中间件默认优先读取 `.env` 中的 `MULTIMODAL_PARSER_MODEL_ID`；未设置时回退到 `iflow_qwen3-vl-plus`
- 仅对 `image` / `pdf` 触发真实解析
- PDF 当前使用 `pymupdf4llm` 做单一路线文本/结构抽取，不引入 OCR 与其他 fallback
- `doc/docx/xlsx` 暂不进入真实解析链路，仍保持后续阶段再扩展
- 解析结果会写回附件 contract：
  - `status=parsed | failed`
  - `summary_for_model`
  - `parsed_text`
  - `structured_data`
  - `confidence`
  - `provenance.processor`
- 解析失败默认 `fail-soft`，不会中断主 agent 推理

当前 Phase 2 设计仍然保持两个原则：

- 原始附件块不覆盖
- 主模型只看到紧凑摘要，不直接吞整份原始抽取结果

### OCR 决策（当前规划）

当前阶段**不引入 OCR**。

原因很明确：

- OCR 会显著增加运行时依赖、部署复杂度与资源消耗。
- 当前优先目标是先把图片与文本型 PDF 的主链路做稳。
- 现阶段的 PDF 方案先聚焦：
- 文本型 PDF：优先高质量文本抽取 / 结构化抽取
- 图片：优先视觉模型解析

因此，OCR 在当前规划中的定位是：

- **暂缓引入**
- **保留为后续可选增强项**

后续只有在以下条件明确成立时，才重新评估 OCR：

- 扫描型 PDF 占比高
- 现有 PDF 解析结果频繁为空或质量不足
- 业务上明确需要处理图片型文档 / 扫描件

如果未来确实需要 OCR，当前建议优先评估 `PaddleOCR` 路线，而不是在当前阶段提前引入复杂运行时。

### Phase 2：先支持 image + pdf

不要一开始就做所有文件类型。

先聚焦：

- 图片
- PDF

把主链路跑通。

### Phase 3：补工具辅助链路

处理 rich content 被静默压成文本的问题。

目标不是“所有地方都支持多模态”，而是：

- 至少不要悄悄丢失信息
- 无法保留时要显式降级

### Phase 4：扩展 doc/docx 等更多类型

等前 3 步稳定后，再扩展更多文件类型。

---

## 13. 结论

最终设计判断如下：

- **方向正确**：多模态处理应优先作为中间件式能力来设计。
- **原则正确**：增强，不覆盖。
- **边界清晰**：中间层负责输入适配与增强，主 agent 负责业务推理。
- **扩展路径明确**：图片、PDF、未来 doc/docx 都应走统一契约下的分流处理。

一句话总结这份设计：

> **不要让每个 graph 自己学会看附件，而是给整个执行层增加一个共享的“多模态翻译官”。**

它保留原始输入，生成结构化理解结果，并只把适合推理的摘要交给主模型。
