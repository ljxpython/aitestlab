# test_case_service_v2

文档类型：`Current Service Overview`

`test_case_service_v2` 是一个独立的 `create_deep_agent` 业务服务，面向测试用例生成与落库场景。

当前实现已经完成从旧知识库 provider 到 LightRAG project-scoped MCP 的迁移，并保持 `runtime_service` 的核心范式不变。
这里的 LightRAG 按当前仓库文档口径被视为**仓库内知识服务**（`apps/lightrag-service`，默认本地一键启动脚本会拉起）或兼容外部服务：

- 静态 `graph = create_deep_agent(...)`
- `RuntimeContext.project_id` 是唯一可信项目上下文
- 服务私有 MCP adapter，不进入公共 `runtime_service/mcp/servers.py`
- 工具契约保持为：
  - `query_project_knowledge`
  - `list_project_knowledge_documents`
  - `get_project_knowledge_document_status`
  - `persist_test_case_results`

## 服务边界

- `graph.py`
  静态 graph 导出，统一装配模型、middleware、服务私有 MCP 和服务私有工具
- `schemas.py`
  服务私有配置和持久化入参模型
- `knowledge_mcp.py`
  LightRAG SSE MCP 适配层
- `middleware.py`
  文档即时持久化中间件
- `knowledge_query_guard_middleware.py`
  无附件业务主题生成场景的强制知识查询 guard
- `tools.py`
  正式测试资产持久化工具
- `skills/`
  服务私有技能库

## 运行时约束

- `project_id` 只读 `RuntimeContext.project_id`
- 不从 `state / configurable / metadata / prompt` 反推项目上下文
- LightRAG 内部 `workspace`、存储路径、实例管理细节不泄露到 `runtime_service`
- 当前轮附件足够时优先基于附件分析，不机械补查知识库
- 无附件且直接生成业务主题测试用例时，必须先调用 `query_project_knowledge`
- 没有知识命中时不得编造业务规则、接口约束或流程细节

## 配置项

`test_case_service_v2` 迁移期使用独立的 `test_case_v2_*` 前缀，不与 `v1` 共享 `test_case_*` 配置键。

| 配置键 | 默认值 | 说明 |
|---|---|---|
| `test_case_v2_default_model_id` | `deepseek_chat` | 服务级默认主模型 |
| `test_case_v2_multimodal_parser_model_id` | `.env` 默认 parser model | 多模态解析模型 |
| `test_case_v2_multimodal_detail_mode` | `False` | 是否启用详细解析 |
| `test_case_v2_multimodal_detail_text_max_chars` | `2000` | 详细模式字符上限 |
| `test_case_v2_persistence_enabled` | `True` | 是否允许正式落库 |
| `test_case_v2_knowledge_mcp_enabled` | `True` | 是否启用 LightRAG MCP |
| `test_case_v2_knowledge_mcp_url` | `http://127.0.0.1:8621/sse` | LightRAG MCP SSE 地址；默认本地一键启动脚本拉起的 repo-local `apps/lightrag-service` 使用该默认口径，若 `runtime-service` 跑在容器中则改用 `http://host.docker.internal:8621/sse` |
| `test_case_v2_knowledge_timeout_seconds` | `30` | MCP 连接超时 |
| `test_case_v2_knowledge_sse_read_timeout_seconds` | `300` | SSE 读超时 |

## LightRAG MCP 适配

`knowledge_mcp.py` 当前做的事情很薄：

- 仅按 SSE spec 连接远端 LightRAG MCP
- 默认文档口径按 repo-local 默认本地脚本地址 `http://127.0.0.1:8621/sse` 组织；容器场景再切换到 `host.docker.internal`
- 要求服务端完整暴露 3 个项目级知识工具
- 保持工具名和显式 `project_id` 参数契约不变
- 把 MCP tool 返回值归一化成字符串，避免 tool message 回灌格式问题

`runtime_service` 侧不处理 LightRAG 的 `workspace`、`storage_root`、项目目录映射等内部语义。
如果 future LightRAG 增加通用 metadata-aware retrieval 能力，服务侧优先学习 `project_id + metadata_filters`，而不是学习 `workspace_key`。

## Skills 与行为

服务私有 skills 位于 [skills](./skills)：

- `requirement-analysis`
- `test-strategy`
- `test-case-design`
- `quality-review`
- `output-formatter`
- `test-data-generator`
- `test-case-persistence`

当前行为约束：

- 有附件时优先基于 `multimodal_summary` 和 `read_multimodal_attachments`
- 无附件业务主题生成时，先 `read_file(requirement-analysis)`，再 `query_project_knowledge`
- 只有知识命中后才放开后续策略和正式用例生成

## 验证状态

本次迁移已完成并验证通过：

- `uv run python -m compileall runtime_service`
- `uv run pytest runtime_service/services/test_case_service_v2/tests -q`
  结果：`12 passed`
- `uv run pytest runtime_service/tests/harness/test_runtime_contract_tightening.py runtime_service/tests/harness/test_static_runtime_graph_contract.py -q`
  结果：`18 passed`
- 真实 LightRAG SSE 联调：
  - 在独立端口临时启动 LightRAG MCP SSE
  - `test_case_service_v2` adapter 成功发现 3 个工具
  - 真实调用 `query_project_knowledge` 返回符合 contract 的 empty-project 响应

## 迁移完成状态

- [x] 文档收敛
- [x] 基线与边界盘点
- [x] 服务去耦
- [x] LightRAG MCP 替换
- [x] 行为对齐
- [x] 验证
- [x] 收尾
