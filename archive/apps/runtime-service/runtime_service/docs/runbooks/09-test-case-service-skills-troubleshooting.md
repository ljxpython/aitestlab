# test_case_service skills 无法识别问题排查

## 问题现象

`test_case_service` 已经通过 `create_deep_agent(..., skills=["/skills/"])` 挂载了私有 skills，离线验证也能枚举出全部 `SKILL.md`，但在线对话时模型仍然直接开始输出测试分析或测试策略，没有先调用 `read_file` 读取 skill 文件。

典型表现：

- `_alist_skills` 能列出全部 skills
- `SkillsMiddleware.abefore_agent` 能把 skills 元数据注入进 state
- live 对话时模型回复里不提 skill，也没有 `read_file("/skills/.../SKILL.md")`
- 模型像“知道有 skills”，但实际没有按 skill 执行

## 影响范围

受影响服务：

- `runtime_service/services/test_case_service`

根因位于公共中间件：

- `runtime_service/middlewares/multimodal/prompting.py`

## 根因分析

这不是 `test_case_service` 的 skills 目录结构问题，也不是 `graph.py` 的 `backend` / `skills=["/skills/"]` 配置错误。

真实根因是 `SkillsMiddleware` 和 `MultimodalMiddleware` 在 `system_message` 表达形式上不兼容：

1. `SkillsMiddleware` 通过 `append_to_system_message(...)` 追加 skills prompt。
2. 追加后的 `SystemMessage` 使用的是 `content_blocks` 结构，而不是单纯的字符串 `content`。
3. `build_multimodal_system_message(...)` 旧实现只读取 `existing.content` 为字符串的情况。
4. 一旦请求链路经过 `MultimodalMiddleware`，前面注入的 skills prompt 会被丢失。
5. 模型最终拿到的 prompt 里看不到 skills 约束，于是直接凭模型先验知识作答。

最小复现思路：

```python
base = SystemMessage(content="BASE")
with_skills = append_to_system_message(base, "SKILLS")
result = build_multimodal_system_message(with_skills, None)
assert result is None  # 旧逻辑下这里会把 skills prompt 吃掉
```

## 修复方案

### 1. 修复公共中间件 prompt 合并逻辑

在 `runtime_service/middlewares/multimodal/prompting.py` 中新增 `_extract_system_message_text(...)`：

- 兼容 `SystemMessage.content` 为字符串
- 兼容 `SystemMessage.content_blocks` 中的文本块
- 在多模态 prompt 合并前先还原完整文本

这样 `MultimodalMiddleware` 不会再抹掉 `SkillsMiddleware` 注入的内容。

### 2. 收紧 test_case_service 的业务提示词

在 `runtime_service/services/test_case_service/prompts.py` 中补充强约束：

- 新任务或新阶段的第一件事必须是 `read_file`
- 在首个 `read_file` 完成前，不允许输出实质性分析内容
- 跨多个阶段的请求必须串行读取多个 skill
- 如果缺少当前阶段应有的 `read_file`，必须停止输出并补读

这一步不是修复根因，而是降低模型“偷懒跳过 skill”的概率，增强行为稳定性。

## 验证方式

### 离线验证

```bash
cd apps/runtime-service
.venv/bin/python runtime_service/tests/services_test_case_service_skills.py
```

预期结果：

- skills 枚举成功
- `SkillsMiddleware.abefore_agent` 注入成功
- static graph 能正常构建

### 精确测试

```bash
cd apps/runtime-service
.venv/bin/pytest runtime_service/tests/test_multimodal_middleware.py -k "preserves_content_blocks_text or preserves_skills_system_prompt_without_attachments or removes_stale_section" -q
.venv/bin/pytest runtime_service/tests/test_test_case_service_graph.py -q
```

### live 验证

```bash
cd apps/runtime-service
.venv/bin/python runtime_service/tests/services_test_case_service_skills.py --live --model deepseek_chat
```

修复后的关键判断标准：

- 第一阶段先 `read_file("/skills/requirement-analysis/SKILL.md")`
- 当用户要求“分析需求并制定测试策略”时，后续继续 `read_file("/skills/test-strategy/SKILL.md")`
- 工具调用记录中出现 `read_file`
- 回复内容能体现对应 skill 的阶段边界

## 排查 checklist

遇到“skills 不能识别”时，按这个顺序查：

1. 检查 `graph.py` 是否传入了 `backend` 和 `skills=["/skills/"]`
2. 检查 `FilesystemBackend.root_dir` 是否真的指向包含 `skills/` 目录的父目录
3. 运行 `_alist_skills` 或 `services_test_case_service_skills.py`，确认 skills 能被枚举
4. 检查 `SkillsMiddleware.abefore_agent` 是否把 `skills_metadata` 注入进 state
5. 检查请求链路中是否有后续 middleware 改写了 `system_message`
6. 重点核对后续 middleware 是否兼容 `SystemMessage.content_blocks`
7. 最后再看业务 prompt 是否足够强，是否明确要求先 `read_file`

## 结论

这次问题本质上是公共 middleware 的 prompt 合并 bug，导致 `test_case_service` 的 skills prompt 在模型调用前被覆盖掉。`test_case_service` 的架构本身没有根本性错误；修复公共中间件兼容性，再配合更强的业务 prompt 约束后，skills 已能被稳定识别并实际读取。

---

## 补充问题：前端上传 PDF 后报 `No generations found in stream`

### 问题现象

当前端上传 PDF 到 `test_case_agent` 时，后端日志表面报错为：

```text
ValueError: No generations found in stream.
```

但继续下钻后，可以看到真正触发点并不是“模型没有返回 token”，而是主模型收到了原始前端附件 block：

```text
openai.BadRequestError: ... messages[1]: unknown variant `file`, expected `text`
```

### 真正根因

这次不是 `skills` 配置错，也不是 `graph.py` 的服务架构错，而是公共多模态中间件在 **LangGraph 实际链路** 下漏掉了“当前轮附件重写”：

1. `before_model` 先把当前轮 PDF 注册进 `state["multimodal_attachments"]`，状态为 `unprocessed`
2. 后续 `wrap_model_call/awrap_model_call` 再次扫描当前消息时，旧逻辑按 `len(existing_artifacts) + 1` 重新编号
3. 由于 state 里已经有同 fingerprint 的 `att_1`，当前轮新扫出来的 block 会变成 `att_2`
4. `_merge_session_artifacts(...)` 用 fingerprint 去重后，只保留 state 里的 `att_1`
5. 结果：
   - 当前轮 `parse_pairs = []`
   - `rewrite_count = 0`
   - 原始 `{"type": "file", ...}` 没有被替换成文本摘要
6. 主模型最终直接收到前端 `file` block，于是 OpenAI 兼容接口报 400，最外层再被包装成 `No generations found in stream`

换句话说，**真正的问题是公共 `MultimodalMiddleware` 没有兼容“before_model 已经登记过当前轮附件”的场景。**

### 修复方案

修复位于：

- `runtime_service/middlewares/multimodal/middleware.py`

核心改动：

1. 把“当前轮附件映射”与“会话级附件汇总”拆开
2. 当前轮扫描时，优先按 fingerprint 复用 state 中已登记的 artifact，而不是重新生成错位的 `attachment_id`
3. 重写消息时，不再从全量 session artifacts 里按前 N 个硬截，而是只使用“当前轮附件列表”
4. 即使 `before_model` 已经登记过当前轮 PDF，`wrap_model_call/awrap_model_call` 仍会：
   - 继续解析该 PDF
   - 把原始 `file` block 改写为 `text` 摘要 block

### 回归验证

新增回归测试：

- `runtime_service/tests/test_multimodal_middleware.py`

重点覆盖两类场景：

1. `before_model` 已先登记当前轮 PDF，后续 `wrap_model_call` 仍能正确解析并改写
2. 会话里已有历史附件时，新一轮请求只重写“当前轮附件”，不会误把上一轮附件摘要塞进当前消息

执行命令：

```bash
cd apps/runtime-service
.venv/bin/pytest -q runtime_service/tests/test_multimodal_middleware.py -k "before_model or current_turn or augments_request or accumulates_pdf_artifacts_across_turns"
```

### 调试脚本

为了直接复现“前端上传 PDF”的真实链路，新增调试脚本：

- `runtime_service/tests/services_test_case_service_debug.py`

用途：

1. 先单独跑 `MultimodalMiddleware` 预检，确认 `file` block 已被改写为 `text`
2. 再跑 `test_case_service` 真 graph
3. 抓取：
   - 流式输出内容
   - `SkillsMiddleware` 注入摘要
   - `MultimodalMiddleware` 状态摘要
   - 工具调用记录
   - 最终异常和 traceback

示例：

```bash
cd apps/runtime-service
.venv/bin/python runtime_service/tests/services_test_case_service_debug.py \
  --model-id deepseek_chat \
  --pdf runtime_service/test_data/12-多轮对话中让AI保持长期记忆的8种优化方式篇.pdf
```

---

## 当前持久化设计说明

在修复 skills 和多模态问题后，`test_case_service` 已继续向“正式测试资产服务”收敛：

- 不再复用 `usecase_workflow_agent` 的 workflow/snapshot/review 设计

---

## 补充问题：工具节点出现 `PydanticSerializationUnexpectedValue(Expected \`none\`)`

### 问题现象

当 `test_case_agent` 通过 LangGraph API / `langgraph dev` 在线运行，并且模型触发 tools 节点时，日志会出现：

```text
Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected `none` - serialized value may not be as expected [field_name='context', input_value=RuntimeContext(...), input_type=RuntimeContext])
```

典型位置：

- `langgraph_node=tools`
- 发生在 skills 读取阶段最常见，也就是 `read_file` / `write_file` / `edit_file` 一类文件系统工具被调用时

### 真正根因

这次也不是 `test_case_service` 自己的 `persist_test_case_results` 工具有问题，而是 **Deep Agents 自带 filesystem tools 的 runtime 签名与我们的 `RuntimeContext` 组合不兼容**：

1. `test_case_agent` 图通过 `context_schema=RuntimeContext` 为整条运行链路注入真实上下文
2. `deepagents.middleware.filesystem` 内部创建的 `read_file` / `write_file` / `edit_file` 等工具，签名是 `ToolRuntime[None, FilesystemState]`
3. `langchain_core.tools.base._parse_input()` 在校验工具参数后，会对结果执行 `result.model_dump()`
4. 当 runtime 里真实带着 `RuntimeContext`，但工具 schema 声明“context 应该是 `None`”时，Pydantic 在 `model_dump()` 阶段发出 serializer warning
5. 在线 `langgraph dev` / LangGraph API 会把这个 warning 打到日志里；如果把 warning 提升成 error，整个 run 会在 tools 节点失败

### 修复方案

新增服务私有中间件：

- `runtime_service/services/test_case_service/tool_runtime_context_middleware.py`

核心做法：

1. 在 `wrap_tool_call/awrap_tool_call` 里读取当前工具的 input schema
2. 如果工具的 `runtime` 字段注解是 `ToolRuntime[None, ...]`
3. 说明这个工具明确声明“不接受 context”
4. 只在这种场景下，把 `request.runtime.context` 置空后再继续执行工具
5. 对 `persist_test_case_results` 这类真正需要 runtime context 的工具，不做改写

这属于 **服务侧边界适配**，不去改三方 `deepagents` 包，也不把“落库/项目作用域”逻辑耦合进公共 middleware。

### 为什么这样修

这次问题本质上不是业务逻辑错，而是“三方工具签名声明过窄”：

- 我们不能改 LangGraph API 的序列化路径
- 也不应该为了迁就第三方 filesystem tools，把整条 `test_case_agent` 图退回到“没有 `RuntimeContext`”
- 最稳的方式就是：
  - 保留真实 `RuntimeContext`
  - 只对“明确声明 `context=None`”的工具做最小边界适配

### 验证方式

#### 单测

```bash
cd apps/runtime-service
PYTHONPATH=. .venv/bin/pytest -q runtime_service/tests/test_test_case_tool_runtime_context_middleware.py
```

预期：

- `ToolRuntime[None, ...]` 工具会收到 `runtime.context=None`
- context-aware 工具仍能收到真实 `RuntimeContext`

#### 真实联调

1. 启动独立 dev server：

```bash
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8124 --no-browser
```

2. 用真实 `test_case_agent` 发起一次会触发 skills 读取的 run
3. 观察 8124 日志

修复前：

- tools 节点会出现 `PydanticSerializationUnexpectedValue(Expected \`none\`)`

修复后：

- `test_case_agent` 仍会正常读取 skill
- tools 节点不再出现该 warning
- run 正常完成
- 正式持久化只保留一个工具：`persist_test_case_results`
- 远端只保留两个结果域：
  - `documents`
  - `test-cases`
- `interaction-data-service` 当前主路径为：
  - `/api/test-case-service/documents`
  - `/api/test-case-service/test-cases`

完整设计见：

- `runtime_service/docs/10-test-case-service-persistence-design.md`

---

## 补充问题：持久化工具已被调用，但落库时报 runtime 注入异常

### 问题现象

在 `skills` 已能正确识别、模型也已经实际调用 `persist_test_case_results` 之后，真实链路仍然报错，且报错分两次暴露：

第一次错误：

```text
RuntimeError: runtime is required
```

修正后第二次错误：

```text
TypeError: persist_test_case_results() missing 1 required positional argument: 'runtime'
```

### 真正根因

根因不在 `interaction-data-service`，也不在 `test_case_service` 的整体架构，而是在工具定义方式：

1. `persist_test_case_results` 最初把 `runtime` 写成了 `ToolRuntime | None = None`
2. 这会破坏 LangGraph 对 `ToolRuntime` 的自动注入识别
3. 同时该工具又显式传入了 `args_schema=PersistTestCaseResultsArgs`
4. `langchain_core.tools.tool(...)` 在显式 `args_schema` 分支下，不会再按函数签名过滤 injected args
5. 结果模型 schema 虽然看起来正常，但实际执行时 `runtime` 没有被框架注入

一句话总结：

- `ToolRuntime` 注入要依赖“函数签名推导 schema”
- 不要把 `runtime` 写成可选参数
- 这类工具尽量不要再显式绑定 `args_schema`

### 修复方案

修复位于：

- `runtime_service/services/test_case_service/tools.py`

核心改动：

1. 把工具签名改回标准注入形式：

```python
def persist_test_case_results(
    bundle_title: str,
    runtime: ToolRuntime[...],
    bundle_summary: str = "",
    ...
) -> str:
```

2. 删除显式 `args_schema=PersistTestCaseResultsArgs`
3. 交给 `tool(...)` 按函数签名自动推导业务参数 schema
4. 这样 `runtime` 会被正确识别为 injected arg，不暴露给模型，同时执行期可正常注入

### 真实验证命令

```bash
cd apps/runtime-service
uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --model-id deepseek_chat \
  --timeout 900
```

### 真实验证结果

验证时间：2026-03-30  
验证方式：真实模型 + 真实 PDF + 真实 `interaction-data-service` + 远端查询校验

关键结果：

- `Graph Report.ok = true`
- 工具调用包含：
  - 6 次 `read_file`
  - 1 次 `persist_test_case_results`
- 远端查询结果：
  - `documents_total = 1`
  - `test_cases_total = 4`
- 退出码：
  - `EXIT_CODE=0`

本次真实写入批次：

- `project_id = 00000000-0000-0000-0000-000000000001`
- `batch_id = test-case-service:de4a20f6-0d34-4f0f-9911-459117563bd7`

### 额外观察

虽然持久化链路已打通，但本次测试 PDF 首页几乎只有二维码，多模态摘要长期停留在：

- `image contains only a QR code`

因此当前生成的测试用例本质上更多依赖文档主题推断，而不是高质量正文解析。  
这不影响“skills 识别 + 工具调用 + 落库链路”已经成功，但说明后续若要提升内容质量，还需要继续增强 PDF 语义解析阶段。
