# test_case_service 设计文档

> 注：本文已同步到当前实现状态，包含私有知识库 MCP / RAG 接入后的装配方式。

## 1. 背景与目标

### 1.1 背景

在软件测试工作流中，测试用例设计是最耗时、最依赖经验的环节。测试工程师需要：
1. 深入理解 PRD、用户故事等需求文档
2. 运用多种测试设计技术（等价类、边界值等）系统化设计用例
3. 确保用例覆盖完整、质量达标
4. 输出符合团队规范的交付物

这一过程对经验要求高，且重复劳动多，是 AI 辅助的理想场景。

### 1.2 目标

构建一个「测试架构师级别」的 AI 智能体服务，能够：
- 接收任意形式的需求输入（文本、图片、PDF）
- 系统化执行需求分析 → 测试策略 → 用例设计 → 质量评审 → 格式化输出
- 输出专业、可执行、可量化的测试资产

---

## 2. 架构设计

### 2.1 技术选型决策

#### 为什么选 `create_deep_agent` 而非 `create_agent`？

| 对比维度 | `create_agent` | `create_deep_agent` |
|---------|---------------|---------------------|
| 任务规划 | 无内置规划 | 内置 `write_todos` 任务分解 |
| 文件系统 | 需手动集成 | 内置文件系统工具（读写、列目录）|
| Skills 机制 | 需手动实现 | 内置 `SkillsMiddleware` |
| 适用场景 | 简单问答、工具调用 | 多步骤复杂任务、需要规划的工作流 |

测试用例分析是典型的多步骤任务，需要规划（先分析需求，再制定策略，再设计用例），且需要 Skills 知识库驱动行为规范，因此选择 `create_deep_agent`。

#### 为什么使用 `FilesystemBackend(virtual_mode=True)`？

- **技能从磁盘加载**：SKILL.md 文件随代码部署，无需额外配置
- **运行时产物保存内存**：避免落盘权限问题，每次会话独立，天然隔离
- **中间产物无需落盘**：需求矩阵、策略文档、评审结果仍然保持会话态
- **正式结果单独持久化**：最终附件解析结果和正式测试用例通过服务私有工具写入 `interaction-data-service`

#### Skills 路径设计

```python
skills = ["/skills/"]
```

Backend root 指向服务包根目录（`get_service_root()`），`/skills/` 是相对于 root 的路径。
这样 Skills 文件与服务代码共处同一包，随代码版本管理，部署无需额外步骤。

### 2.2 组件依赖图

```
用户输入
    │
    ▼
MultimodalMiddleware          ← 图片/PDF 解析（横切）
    │
    ▼
create_deep_agent
    ├── model                 ← 通过 options.model_spec 解析
    ├── tools
    │   ├── 私有知识库 MCP tools ← MultiServerMCPClient(...).get_tools()，SSE 连接远端私有知识库服务
    │   │                         并在服务内把内容块结果归一化为字符串
    │   │   ├── query_project_knowledge
    │   │   ├── list_project_knowledge_documents
    │   │   └── get_project_knowledge_document_status
    │   └── persist_test_case_results（服务私有落库工具）
    ├── deep agent 内建文件系统工具 ← 由 backend + skills 自动提供（read_file / ls / glob / write_todos 等）
    ├── middleware
    │   └── MultimodalMiddleware
    ├── system_prompt         ← SYSTEM_PROMPT（含 Skills 激活协议 + 知识检索规则）
    ├── backend               ← FilesystemBackend(root=service_root, virtual_mode=True)
    ├── skills                ← ["/skills/"]（私有 SKILL.md，默认不共享）
    └── context_schema        ← RuntimeContext
```

### 2.3 数据流

```
RunnableConfig
    │
    ├── read_configurable()           → private_config
    ├── RuntimeContext                → 公共业务输入（project_id / model_id / prompt 等）
    ├── build_test_case_service_config() → service_config（默认主模型 + 多模态 + 持久化开关 + 私有知识库 MCP 配置）
    └── RuntimeRequestMiddleware      → resolve_runtime_settings()（model + system_prompt + tools）
```

### 2.3.1 知识检索调用链

```
Agent 推理
    │
    ├── 首选：query_project_knowledge
    │       ↓
    │   私有知识库 MCP server（SSE）
    │       ↓
    │   ProjectKnowledgeService
    │       ↓
    │   RAG Anything
    │
    ├── 辅助：list_project_knowledge_documents
    │       ↓
    │   用于查看项目文档清单、筛选 document_id
    │
    └── 辅助：get_project_knowledge_document_status
            ↓
        用于检查索引/解析状态、定位为什么查不到
```

设计原则：

- `test_case_service` 默认不再向 agent 暴露公共 tools / 公共 MCP
- 私有知识库 MCP 通过 `MultiServerMCPClient(...).get_tools()` 直接装配到本服务 graph
- 私有知识库 MCP 的接入方式默认推荐 `SSE`，而不是本地 `stdio`
- `query_project_knowledge` 是主查询入口
- `list_project_knowledge_documents`、`get_project_knowledge_document_status` 是辅助工具，不作为默认首选
- 如果当前轮附件与 `multimodal_summary` 已足够支撑结论，不应机械补查知识库
- 如果用户直接要求“生成某类业务/模块/场景测试用例”，且当前轮没有附件，则知识检索不是可选项，而是前置必选项
- 由于当前模型链路对 tool message 的 content 格式更严格，服务内对 MCP 返回值做字符串归一化，避免第二轮模型调用 400
- 当前真实联调已验证：同一轮 agent run 中可连续多次调用 `query_project_knowledge`
- 持久化阶段如果远端 `interaction-data-service` 已配置但请求失败，工具会返回结构化失败状态，而不是抛异常终止整条 graph

### 2.4 System Prompt 合并策略

```python
system_prompt = (
    f"{options.system_prompt}\n\n{SYSTEM_PROMPT}"
    if options.system_prompt
    else SYSTEM_PROMPT
)
```

**设计理由**：运行时覆盖（`options.system_prompt`）作为「前置补充」，服务自身的 SYSTEM_PROMPT 始终追加在后，保证 Skills 激活协议和行为约束不被覆盖。

---

## 3. Skills 设计

### 3.1 Skills 执行顺序

```
requirement-analysis
        ↓
test-strategy
        ↓
test-case-design ←──→ test-data-generator（按需）
        ↓
quality-review
        ↓
output-formatter
        ↓
test-case-persistence（按需）
```

### 3.2 各 Skill 职责边界

| Skill | 输入 | 输出 | 强制顺序 |
|-------|------|------|----------|
| `requirement-analysis` | 用户提供的需求文本/附件 | 需求矩阵（功能点、风险、优先级）| 必须首先执行 |
| `test-strategy` | 需求矩阵 | 测试类型决策、P0-P3 分层、覆盖率目标 | 需求分析后 |
| `test-case-design` | 测试策略 | 标准格式测试用例集 | 策略后 |
| `test-data-generator` | 字段规格 / 用例中的测试数据占位符 | 具体测试数据集 | 与用例设计并行或后置 |
| `quality-review` | 测试用例集 | 四维度评分报告 | 用例设计后（自动触发）|
| `output-formatter` | 所有阶段产出 | 格式化交付物（MD/JSON/CSV）| 最后执行 |
| `test-case-persistence` | 格式化后的正式测试用例 + 附件解析结果 | interaction-data-service 落库结果 | 仅正式落库时执行 |

### 3.3 SKILL.md 格式规范

```yaml
---
name: skill-name          # kebab-case，与目录名一致
description: 激活场景说明   # 供 Agent 判断何时激活此 Skill
---

# Skill 标题

## 激活场景     # 具体触发条件
## 执行流程     # Step by Step 操作规范
## 输出规范     # 期望的输出格式和内容
## 关键约束     # 必须遵守的规则
```

### 3.4 知识库 MCP 与 Skills 的配合策略

当前实现不新增独立 `knowledge-grounding` skill，而是通过 `SYSTEM_PROMPT`、现有核心 skills、以及服务内 `TestCaseKnowledgeQueryGuardMiddleware` 共同约束知识检索行为：

- `requirement-analysis`
  - 当用户问题依赖“已上传文档 / 项目知识库文档 / 历史沉淀资料”时，优先调用 `query_project_knowledge`
  - 如果需要限定文档范围，先调用 `list_project_knowledge_documents`
  - 如果用户只给出业务主题并要求生成测试用例，且没有上传附件，也必须先查知识库
- `test-strategy`
  - 当需求摘要不足、业务规则不清或用户要求“基于文档制定策略”时，再补一次知识查询
- `test-case-design`
  - 生成正式用例前，如果事实依据不足、字段约束不明确、接口规则不清，必须先查询知识库再继续
  - 无附件业务生成场景下，正式用例必须可回溯到知识库命中的业务片段
- `test-case-persistence`
  - 只负责最终保存，不负责知识检索

辅助规则：

- `query_project_knowledge` 是默认首选
- `list_project_knowledge_documents` 只在需要确认文档范围时调用
- `get_project_knowledge_document_status` 只在“查不到内容、怀疑索引未完成”时调用
- 对“无附件 + 直接生成业务测试用例”场景，middleware 会先卡一层硬顺序：
  - 第一步只允许 `read_file(/skills/requirement-analysis/SKILL.md)`
  - 第二步只允许 `query_project_knowledge`
  - 只有当前轮已经真实触发过 `query_project_knowledge`，才放开后续正常生成链路

---

## 4. 配置设计

### 4.1 TestCaseServiceConfig

```python
@dataclass(frozen=True)
class TestCaseServiceConfig:
    default_model_id: str             # 服务级默认主模型（仅在未显式传 model_id 时生效）
    multimodal_parser_model_id: str   # 多模态解析模型
    multimodal_detail_mode: bool      # 是否启用详细解析
    multimodal_detail_text_max_chars: int  # 详细模式字符上限
    persistence_enabled: bool         # 是否允许正式落库
    knowledge_mcp_enabled: bool       # 是否启用私有知识库 MCP
    knowledge_mcp_url: str            # 私有知识库 MCP 的 SSE 地址
    knowledge_timeout_seconds: int    # MCP 连接超时
    knowledge_sse_read_timeout_seconds: int  # SSE 读超时
```

使用 `frozen=True` 确保不可变性，避免运行时意外修改。

### 4.1.1 服务级默认模型策略

- `test_case_service` 默认主模型固定为 `deepseek_chat`
- 只有在调用方没有显式传 `model_id`，且环境变量 `MODEL_ID` 也未覆盖时，才注入这个服务级默认值
- 这样可以保证：
  - 当前 testcase 业务默认走工具遵循性更稳定的 DeepSeek
  - 其他 graph 仍然可以继续使用 runtime 全局默认模型
- 调用方如果明确指定模型，仍然可以覆盖这个服务级默认值

### 4.1.2 私有知识库 MCP 配置

建议全部使用 `test_case_*` 前缀，并保持“服务私有、显示启用”：

- `test_case_knowledge_mcp_enabled`
- `test_case_knowledge_mcp_url`
- `test_case_knowledge_timeout_seconds`
- `test_case_knowledge_sse_read_timeout_seconds`

如后续远端知识库 MCP 需要鉴权，再补充服务私有 header/token 配置；不建议把这类配置塞进公共 `mcp/servers.py`。

### 4.2 Backend Root 解析逻辑

```python
def _resolve_backend_root_dir_path(private_config, *, agent_name) -> Path:
    override = private_config.get("test_case_backend_root_dir")
    if isinstance(override, str) and override.strip():
        return Path(override).expanduser()
    return get_service_root()  # 默认：服务包根目录
```

优先级：显式覆盖 > 服务包目录。覆盖机制用于测试和特殊部署场景。

---

## 5. 测试策略

### 5.1 测试层次

| 层次 | 文件 | 覆盖内容 |
|------|------|----------|
| 单元测试 | `runtime_service/tests/test_test_case_service_graph.py` 等 | schemas、prompts、graph 静态装配 |
| 集成测试 | 暂无（需真实模型）| static graph 端到端执行 |

### 5.2 Graph 测试策略

静态 graph 通过 resolver 单测 + harness 合同测试验证：
- graph 是否顶层静态导出
- 是否显式声明 `context_schema=RuntimeContext`
- 是否接入 `RuntimeRequestMiddleware`
- required tool / system prompt resolver 是否符合 contract

这样可以在不依赖真实模型和网络的情况下验证装配逻辑的正确性。

### 5.3 新增测试点

- 验证 `test_case_service` 不再默认继承公共 `build_tools(options)`
- 验证私有知识库 MCP 的 3 个工具被正确装配
- 验证 `persist_test_case_results` 仍与知识工具共存
- 验证 prompt / skill 文案包含“先查知识再生成”的约束
- 验证在 mock `MultiServerMCPClient` 场景下，可稳定拿到远端 3 个工具

---

## 6. 已知限制与后续优化方向

| 限制 | 影响 | 优化方向 |
|------|------|----------|
| `virtual_mode=True` 不持久化 | 会话结束后中间产物丢失 | 支持 `virtual_mode=False` + 配置化存储路径 |
| 无流式输出进度反馈 | 长任务用户体验差 | 集成 LangGraph streaming |
| Skills 无版本管理 | SKILL.md 变更无法灰度 | 引入 skills 版本号机制 |
| 平台真实链路缺失 project_id 时会显式失败 | 运行时项目上下文必须由 platform-api 注入 | 不做默认项目 fallback，直接暴露配置错误 |
| 平台人工 CRUD 仍允许重复 testcase | 自动保存已支持幂等覆盖，但人工录入仍可能录入相似记录 | 后续如有需要再评估平台侧提示或弱校验 |
| 旧 `usecase-generation` 结果域已退役 | 历史引用可能残留在外部系统 | 保持新服务独立，不再恢复旧 workflow 服务 |
| 私有知识库 MCP 依赖外部 SSE 服务 | 本服务私有装配链路正常，但远端服务不可达时知识工具不可用 | 生产环境接入统一发布地址，并按需增加健康检查 / 降级策略 |

## 7. 当前落地结论

- `test_case_service` 当前已经实现“服务私有 tools + 服务私有 MCP + 服务私有 skills”三者显式装配
- 知识库能力保持私有，不进入公共 `runtime_service/mcp/servers.py`
- 推荐接入姿势是：调用方把 `project_id` 放进 `RuntimeContext`，服务私有配置仍走 `RunnableConfig.configurable`
- `project_id` 只认 `RuntimeContext.project_id`，服务内部不再从 `state/configurable/system prompt` 反推业务项目上下文
- 对接方如果要做真实验收，优先使用 `services_test_case_service_knowledge_live.py --require-query-tool`，这样能直接断言 agent 确实命中了知识主查询工具
