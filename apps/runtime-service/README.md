# langgraph-agent-studio

文档类型：`Current App Overview`

`apps/runtime-service` 是当前正式架构里的 runtime 执行层，也是仓库总哲学 `AI Harness` 下的智能体开发主战场。

当前正式主链里，它的位置是：

```text
platform-web -> platform-api -> runtime-service
runtime-service -> interaction-data-service
runtime-web -> runtime-service   (optional debug path)
```

如果你要先理解仓库级正式链路与本地 bring-up 口径，先看：

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/deployment-guide.md`
- `docs/development-paradigm.md`

如果你要理解 `runtime-service` 自己的内部范式和 graph/runtime 资料，再回到本目录与 `runtime_service/docs/**`。

## 开发范式入口

跨应用统一开发方式先看根文档：

- `docs/development-paradigm.md`

对 `runtime-service` 来说，最重要的执行原则是：

1. 智能体开发主战场在这里，先把 graph / prompt / tools / middleware 做通
2. 先在低依赖层做真实验证，再决定要不要接平台页面
3. 关键链路优先用真实模型、真实文件、真实下游服务验证，不要用 mock 掩盖问题
4. 如果模型会口头声称成功，必须再查真实 tool call 和远端结果，不能只信最终回复
5. 平台真实链路下，受信上下文由 `platform-api` 注入，运行时服务不再自己发明透传规则

## 0) 前置说明（必读）

本项目运行前需要先把两处配置准备好：

- `runtime_service/.env`：运行时环境变量（由 `runtime_service/langgraph.json` 自动加载）
- `runtime_service/conf/settings.yaml`：模型组配置（模型 provider / model / base_url / api_key）

### 0.1 配置 `runtime_service/.env`

1) 从模板复制：

```bash
cp runtime_service/.env.example runtime_service/.env
```

2) 至少确认以下变量已填写：

- `APP_ENV`：环境名（如 `test` / `production`），用于选择 `settings.yaml` 的环境块

`MODEL_ID` 使用规则：

- 留空或不设置：使用 `runtime_service/conf/settings.yaml` 当前环境块里的 `default_model_id`
- 显式设置：覆盖默认模型；值必须在 `runtime_service/conf/settings.yaml` 的 `models` 中存在

建议默认先留空，只有明确要覆盖默认模型时再填写，避免本地 `.env` 长期残留旧的 model id。

可选（按需启用）：

- `SYSTEM_PROMPT`：运行时覆盖 prompt。若未设置，则由各个 graph 自己回退到业务默认提示词
- `MULTIMODAL_PARSER_MODEL_ID`：共享 `MultimodalMiddleware` 的附件解析模型默认值；未显式覆盖 `parser_model_id` 的 graph 会使用它
  - 当前容器化基线默认值：`gpt_5.4-ccr`
- `ENABLE_TOOLS`：公共工具池总开关
- `TOOLS`：公共工具白名单（逗号分隔，支持本地工具与 `mcp:<server>`）

若你需要 OAuth 鉴权（Supabase），还需在 `.env` 中准备：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- 可选：`SUPABASE_TIMEOUT_SECONDS`

并使用带鉴权配置启动：`--config runtime_service/langgraph_auth.json`。

### 0.2 配置 `runtime_service/conf/settings.yaml`

配置加载逻辑在 `runtime_service/conf/settings.py`：会先读 `settings.yaml`，再叠加 `settings.local.yaml`（本地覆写）。

建议从模板开始：

```bash
cp runtime_service/conf/settings.yaml.example runtime_service/conf/settings.yaml
```

最小可运行要求：

- `default.default_model_id`：默认模型组 id
- `default.models.<model_id>`：每个模型组必须包含以下四个字段：
  - `model_provider`
  - `model`
  - `base_url`
  - `api_key`

说明：运行时可以显式传/设置 `MODEL_ID`，也可以直接使用 `default_model_id`；模型四元组由 `settings.yaml` 统一映射。

安全建议：真实 `api_key` / 内网 `base_url` 建议放在 `settings.local.yaml` 做本地覆写，避免提交到仓库。

### 0.3 更多文档（推荐）

推荐按下面顺序阅读：

1. `runtime_service/docs/README.md`
2. `runtime_service/docs/02-architecture.md`
3. `runtime_service/agents/assistant_agent/graph.py`

更完整的开发/验证说明见：`runtime_service/docs/README.md`。

## 本地启动

在当前仓库中，推荐以前台方式启动，便于联调和排错：

```bash
# from repo root
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser --allow-blocking
```

如果你已经在 `apps/runtime-service` 目录内，直接执行最后一行 `uv run ...` 即可。

注意：`runtime_service/langgraph.json` 会自动加载 `runtime_service/.env`。如果 `.env` 中保留了旧的 `MODEL_ID`，它会覆盖 `settings.yaml` 的默认模型；排查模型配置问题时，先检查这里有没有陈旧值。

如果启用了 `research_demo`、`deepagent_demo`、`test_case_agent` 这类依赖 Deep Agents 文件后端/skills 的 graph，本地 `langgraph dev` 调试请显式带上 `--allow-blocking`。这套依赖链内部仍有同步文件 IO（如 `resolve` / `readlink` / `stat`），可能被 `blockbuster` 拦成 `BlockingError`。实际 Agent Server 版本以锁文件、固定镜像 digest 与 `/info` 为准，详见 `runtime_service/docs/knowledge/09-langgraph-runtime-upgrade-and-event-migration.md`。

同时建议在 `.env` 中保留 `BG_JOB_ISOLATED_LOOPS=true`。它对托管/后台 worker 仍然有价值，但单独配置它并不能替代当前本地 dev 的 `--allow-blocking`。

如果是部署环境，可以直接在配置或容器环境变量中声明：

```json
{
  "graphs": {
    "agent": "./graph.py:graph"
  },
  "env": {
    "BG_JOB_ISOLATED_LOOPS": "true"
  }
}
```

容器环境也可以直接在启动前导出：

```bash
export BG_JOB_ISOLATED_LOOPS=true
```

这两种方式都适合部署侧注入环境变量；当前仓库本地联调仍以 `.env` + `--allow-blocking` 为准。

启动后建议先做最小健康检查：

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

如果你需要查看当前仓库统一的本地联调口径，参考根级文档：

- `docs/local-dev.md`
- `docs/env-matrix.md`
- `docs/deployment-guide.md`

## 本应用的开发与验证要求

如果本轮只改 `runtime-service`，推荐顺序是：

1. 先明确：
   - 这是新 graph、已有 graph、还是某个服务内部能力调整
   - 输入是什么
   - 工具链路是什么
   - 是否需要持久化
2. 直接在本层做真实验证：
   - 真实模型
   - 真实 PDF / 图片 / 文本
   - 真实 `interaction-data-service`
   - 真实流式输出和 tool call 记录
3. 验证通过后，再接 `runtime-web` 或 `platform-web`

推荐优先使用：

- 服务级 debug/live 脚本
- `runtime_service/tests/*`
- `runtime_service/docs/*` 中沉淀的真实排查命令

关键约束：

- 没有真实 tool call 和真实远端结果，不算真正成功
- 中间件不要乱耦合业务落库逻辑
- 默认先把服务层闭环跑通，再决定是否进入平台层联调
