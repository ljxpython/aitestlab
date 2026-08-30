# test_case_service

文档类型：`Current Service Overview`

这份 README 说明当前 `test_case_service` 的服务边界、私有装配方式和真实联调入口。

如果你要确认当前正式持久化或平台链路，请同时参考：

- `../../docs/10-test-case-service-persistence-design.md`
- `../../../interaction-data-service/docs/README.md`
- `../../../platform-api/app/modules/testcase/presentation/http.py`

测试用例分析智能体服务。基于 `create_deep_agent` + 私有 Skills 体系，将模糊的产品需求转化为高质量、可执行、可量化的测试资产。

## 功能概述

| 能力 | 说明 |
|------|------|
| 需求分析 | PRD / 用户故事 / 功能描述解析，识别隐性需求与测试风险 |
| 测试策略 | 测试类型决策、优先级分层（P0-P3）、覆盖率目标制定 |
| 用例设计 | 六大设计技术（等价类、边界值、判定表、状态转换、场景法、错误猜测）|
| 质量评审 | 四维度自动评分（完整性、准确性、可执行性、规范性）|
| 数据生成 | 边界值、正常值、异常值完整测试数据集构造 |
| 格式化输出 | Markdown / JSON / CSV 多格式交付，可直接导入测试管理工具 |
| 多模态输入 | 图片 / PDF 通过 `MultimodalMiddleware` 自动解析后作为需求输入 |

## 架构说明

```
test_case_service/
├── graph.py          # static graph（LangGraph 入口）
├── prompts.py        # SYSTEM_PROMPT（角色定位 + Skills 激活协议）
├── schemas.py        # 服务配置 + 持久化工具入参模型
├── knowledge_mcp.py  # 服务私有知识库 MCP（SSE 装配）
├── tools.py          # 服务私有工具（persist_test_case_results）
├── __init__.py       # 延迟导入（避免 pytest collect 阶段 import 错误）
├── skills/           # 私有 Skills 知识库
│   ├── requirement-analysis/SKILL.md
│   ├── test-strategy/SKILL.md
│   ├── test-case-design/SKILL.md
│   ├── quality-review/SKILL.md
│   ├── output-formatter/SKILL.md
│   ├── test-data-generator/SKILL.md
│   └── test-case-persistence/SKILL.md
└── tests/
    ├── __init__.py
    └── ...           # graph / middleware / tools 回归统一放到 runtime_service/tests
```

### 核心技术选型

- **`create_deep_agent`**：DeepAgent 模式，内置任务规划（`write_todos`）、文件系统工具、Skills 机制
- **`FilesystemBackend(virtual_mode=True)`**：Skills 从磁盘加载，运行时中间产物保存内存不落盘
- **`skills=["/skills/"]`**：加载 backend root 下 `skills/` 目录中的所有 SKILL.md
- **`MultimodalMiddleware`**：横切多模态解析能力，解析结果写入 `state.multimodal_summary`
- **服务私有知识库 MCP**：通过 `MultiServerMCPClient(...).get_tools()` 以 `SSE` 接入远端知识库 MCP，仅在 `test_case_service` 内装配
- **服务私有持久化工具**：`persist_test_case_results` 负责把附件解析结果和正式测试用例写入 `interaction-data-service`
- **共享 Interaction Data HTTP Client**：抽取到 `runtime_service.integrations.interaction_data`
- **`RuntimeContext`**：通过 `context_schema` 注入运行时上下文

## 配置项

通过 `RunnableConfig.configurable` 传入，所有配置项均有默认值：

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `test_case_default_model_id` | `str` | `deepseek_chat` | 当调用方未显式传 `model_id` 时，`test_case_service` 的服务级默认主模型 |
| `test_case_multimodal_parser_model_id` | `str` | `.env -> MULTIMODAL_PARSER_MODEL_ID` 或 `iflow_qwen3-vl-plus` | 多模态解析模型（服务私有 override） |
| `test_case_multimodal_detail_mode` | `bool` | `False` | 启用详细解析模式 |
| `test_case_multimodal_detail_text_max_chars` | `int` | `2000` | 详细模式最大字符数 |
| `test_case_backend_root_dir` | `str` | 服务包目录 | FilesystemBackend 根目录覆盖 |
| `test_case_persistence_enabled` | `bool` | `True` | 是否允许调用正式持久化工具 |
| `test_case_knowledge_mcp_enabled` | `bool` | `True` | 是否启用服务私有知识库 MCP |
| `test_case_knowledge_mcp_url` | `str` | `http://0.0.0.0:8000/sse` | 服务私有知识库 MCP 的 SSE 地址 |
| `test_case_knowledge_timeout_seconds` | `int` | `30` | 知识库 MCP 连接超时 |
| `test_case_knowledge_sse_read_timeout_seconds` | `int` | `300` | 知识库 MCP SSE 读超时 |
| `interaction_data_service_url` | `str` | 环境变量/空 | interaction-data-service 基地址 |
| `interaction_data_service_token` | `str` | 环境变量/空 | interaction-data-service Bearer Token |

说明：

- 共享 `MultimodalMiddleware` 的默认 parser model 现在会优先读取 `.env` 中的 `MULTIMODAL_PARSER_MODEL_ID`
- 如果要在真实 graph 调用时临时覆盖，可通过 `RuntimeContext.multimodal_parser_model_id`
| `interaction_data_service_timeout_seconds` | `int` | `10` | interaction-data-service 请求超时 |

说明：

- 如果 `RuntimeContext.model_id` 已显式传入，则始终优先使用调用方指定模型
- 只有在调用方未显式传 `model_id` 时，服务才回落到 `test_case_default_model_id=deepseek_chat`
- `project_id` 是受信运行时上下文，平台真实链路必须由 `platform-api` 注入到 `context`
- `test_case_service` 只认 `RuntimeContext.project_id`，不再从 `configurable / metadata / state / system prompt` 反推项目上下文
- 未注入 `project_id` 时，`test_case_service` 会直接报错；不再提供默认项目 fallback
- 当前 `interaction-data-service` 的 `test-case-service` 相关接口要求 `project_id` 为 UUID 字符串；联调脚本里的 `--project-id` 也会前置校验这一点，避免把无效参数直接打成远端 `400`
- `test_case_service` 的文档即时持久化层和 `persist_test_case_results` 也会校验 `project_id` 是否为 UUID；无效时不会再把请求发到远端

## Skills 说明

Agent 通过 `SkillsMiddleware` 自动加载以下 Skills，按需激活：

| Skill | 激活场景 |
|-------|----------|
| `requirement-analysis` | 用户提供需求文档、PRD、用户故事、功能描述 |
| `test-strategy` | 需求分析完成后，制定整体测试方案 |
| `test-case-design` | 为具体功能点设计测试用例 |
| `quality-review` | 用例生成后自动执行质量自检 |
| `output-formatter` | 输出最终格式化测试用例交付物 |
| `test-data-generator` | 用户需要配套测试数据 |
| `test-case-persistence` | 输出正式测试资产并落库到 interaction-data-service |

## 知识库工具装配

`test_case_service` 不再默认继承公共 tools / 公共 MCP。当前 agent 的工具集合收敛为：

- deep agent 自带文件系统工具
- 服务私有知识库 MCP 的 3 个工具：
  - `query_project_knowledge`
  - `list_project_knowledge_documents`
  - `get_project_knowledge_document_status`
- `persist_test_case_results`

推荐接入方式：

- 默认推荐 **SSE**，而不是本地 `stdio`
- 原因很直接：后续知识库服务与 `runtime-service` 大概率不会部署在同一台机器上，SSE 更符合真实部署形态
- 当前 `test_case_service` 的私有知识库配置默认就是 `http://0.0.0.0:8000/sse`
- 若后续上正式环境，只改 `test_case_knowledge_mcp_url`，不需要改 graph 装配逻辑

知识工具使用约束：

- `query_project_knowledge` 是默认主入口
- `list_project_knowledge_documents` 只在需要确认文档范围时调用
- `get_project_knowledge_document_status` 只在排查索引状态或检索异常时调用
- 如果当前轮附件和 `multimodal_summary` 已足够支撑结论，不要机械补查知识库
- 如果用户直接要求“生成某类业务/模块/场景测试用例”，且当前轮没有提供附件，必须先查询私有知识库，再基于命中的业务片段生成用例
- graph 会把当前请求解析到的 `project_id` 注入系统提示词；若缺失则明确标记缺失，不能靠 prompt 反推项目 ID
- 服务内会把 MCP 工具返回的内容块归一化为字符串，避免当前模型链路在 tool message 回灌时发生 400 反序列化错误
- 服务内额外挂了 `TestCaseKnowledgeQueryGuardMiddleware`：无附件业务用例请求会先强制 `read_file(/skills/requirement-analysis/SKILL.md)`，再强制 `query_project_knowledge`，不是只靠 prompt 自觉
- 服务内新增了 `TestCaseKnowledgeQueryGuardMiddleware`，对“无附件生成业务测试用例”场景做代码级兜底：
  - 先强制读取 `/skills/requirement-analysis/SKILL.md`
  - 再强制调用 `query_project_knowledge`
  - `query_project_knowledge` 命中前，不放开正式用例生成链路

无附件生成用例约束：

- 输入示例：`生成支付业务测试用例`、`生成登录模块测试用例`
- 这类请求即使没有 PDF/图片，也不能直接按经验出用例
- 必须先调用 `query_project_knowledge`
- 必须基于命中的知识片段抽取规则、流程、边界条件，再生成正式测试用例
- 如果知识库无结果，应明确说明“知识依据不足”，而不是编造业务细节
- 代码层顺序是：`read_file(requirement-analysis) -> query_project_knowledge -> 正常策略/用例生成`

## 排障记录

### PDF 已上传，却被误判成“无附件业务测试用例生成”

现象：

- `platform-web` 前端真实请求体已经带了 `content[].type=file` 的 PDF block
- agent 仍返回：`当前请求是无附件业务测试用例生成，但服务未挂载 query_project_knowledge，因此不能基于臆测继续生成。`

根因：

- `MultimodalMiddleware` 会先解析附件，并把结果写进 `state.multimodal_attachments` / `state.multimodal_summary`
- 同时，模型看到的最新用户消息会被重写为“文本 + 附件摘要”
- `TestCaseKnowledgeQueryGuardMiddleware` 旧实现只检查 `request.messages` 里是否还存在 `file/image` block
- 结果就是：附件已经进入多模态状态，但 guard 误以为“当前轮无附件”，从而错误触发 `query_project_knowledge` 强制分支

修复：

- guard 现在除了检查消息内容，还会检查 `request.state["multimodal_attachments"]`
- 只要多模态状态里已经有附件，就不再把本轮请求判成“无附件业务用例生成”

验证结论：

- 前端附件上传链路正常，不是 `platform-web` 把 PDF 弄丢
- `MCP` 开关不应影响“有没有识别到上传附件”，它只影响无附件/证据不足时能不能查知识库
- 修复后，真实新线程已验证能命中 `read_multimodal_attachments`，并继续生成正式测试用例

## 在 LangGraph 中的注册

```json
"test_case_agent": {
  "path": "./runtime_service/services/test_case_service/graph.py:graph",
  "description": "测试用例分析智能体：..."
}
```

## 运行测试

```bash
cd apps/runtime-service
pytest runtime_service/services/test_case_service/tests/ -v
```

## 真实联调验证

```bash
cd apps/runtime-service

# 先在知识库仓库启动 SSE MCP
# cd /path/to/light_anything_test
# MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8000 uv run python src/mcp_server.py

uv run python runtime_service/tests/services_test_case_service_document_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --model-id deepseek_chat

uv run python runtime_service/tests/services_test_case_service_knowledge_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --knowledge-mcp-url http://0.0.0.0:8000/sse \
  --model-id deepseek_chat \
  --require-query-tool

uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --model-id deepseek_chat

uv run python runtime_service/tests/services_test_case_service_project_scope_live.py \
  --project-id 5f419550-a3c7-49c6-9450-09154fd1bf7d \
  --platform-token <platform_api_bearer_token> \
  --model-id deepseek_chat
```

说明：

- `services_test_case_service_document_live.py`：验证“上传即落库”的 document 链路
- `services_test_case_service_knowledge_live.py`：验证 agent 在真实对话中会调用私有知识库 MCP 工具；加 `--require-query-tool` 可强制断言必须命中 `query_project_knowledge`
- `services_test_case_service_persistence_live.py`：验证正式 testcase 保存与 `source_document_ids` 关联
- `services_test_case_service_project_scope_live.py`：验证 `platform-api` 项目作用域注入、缺失项目时的显式失败、以及默认项目不被脏写入
- 所有 live 脚本的 `--project-id` 都要求传 UUID；不要再用 `test-case-persist-123456` 这种普通字符串
- `services_test_case_service_project_scope_live.py` 需要 `platform-api` 的 Bearer token；可显式传 `--platform-token`，也可通过环境变量 `PLATFORM_API_TOKEN` / `PLATFORM_ACCESS_TOKEN` 提供

当前已验证事实：

- `test_case_service -> 私有 SSE MCP -> RAG Anything` 主链路可真实跑通
- 同一轮 agent 对话里可连续多次调用 `query_project_knowledge`
- 知识库验证场景下不会误调用 `persist_test_case_results`
- 当 `interaction-data-service` 已配置但暂时不可达时，`persist_test_case_results` 会返回结构化失败结果，而不是直接打崩整条 agent 链路

## 典型使用场景

1. **输入 PRD 文档** → Agent 依次执行：需求分析 → 测试策略 → 用例设计 → 质量评审 → 格式化输出 → 持久化
2. **上传原型图/截图** → MultimodalMiddleware 解析图片 → 触发需求分析流程
3. **上传已有用例集** → 直接触发 quality-review 评分
4. **指定导出格式** → output-formatter 输出 JSON/CSV 供工具导入
5. **需要正式保存** → `persist_test_case_results` 把附件解析结果和最终测试用例写入 interaction-data-service

## 私有化约束

- 该服务默认不把知识库能力注册进公共 `runtime_service/mcp/servers.py`
- 该服务默认不继承公共 `tools/registry.py` 的工具集合
- 私有知识库 MCP、私有 skills、私有持久化工具都由 `test_case_service/graph.py` 显式装配
