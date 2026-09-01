# R5 Observability Closure Verification

- Status：Pending
- Disposition：Pending acceptance
- Pre-apply review：Approved，Owner 已明确同意按本 change 实施与验证。

## Scope

- Locus：`apps/runtime-service`
- Chain：`langgraph.json -> Agent Server application lifespan -> Graph entrypoint -> RuntimeConfigMiddleware -> Model/Tool/Subagent -> Langfuse exporter`
- Band：B3 Governed。原因是本变更修改 Agent Server 生命周期、可信身份 metadata、外部 exporter 故障语义和生产部署配置。
- Authority loaded：根级 `AGENTS.md`；Runtime knowledge 文档 16、24、28、31；`openspec/specs/runtime-observability/spec.md`；`openspec/specs/runtime-agent-service-integration/spec.md`。当前 `apps/runtime-service/docs/standards/` 没有可读取的叶子规范。

## Pre-Apply Review

- Decision：Approved。Owner 已明确要求继续实现与验证，本轮按 proposal/spec/design/tasks apply。
- Required boundary decisions：接受 `http.app` 作为只承载 lifespan 的入口；接受 caller metadata allowlist 和 trusted metadata 两阶段边界；接受真实 Langfuse smoke 缺资源时必须明确 skip/block，不以 fake callback 冒充真实证据。
- Not approved as completed：跨服务 OpenTelemetry parent/baggage、Run Explorer、Run Event、Durable Run/Checkpoint/Queue、完整正文采集和自定义观测 Provider。

## Verification Plan

| Boundary | Check | Required evidence | Status |
| --- | --- | --- | --- |
| Local contract | adapter allowlist、脱敏、callback 合并、Counter | `uv run pytest tests/observability -q` | passed：25 passed |
| Runtime chain | 五个 Service + Auth/Resolver + Graph 执行 | `uv run pytest tests -q` | passed：146 passed；12 个外部资源测试 skipped，不计通过证据 |
| Lifecycle | startup validation、client reuse、shutdown flush/timeout | lifespan tests + Agent Server `/info` | local passed；目标镜像加载 custom app，但 entitlement `403` 阻断 application startup；生产 SIGTERM 未证明 |
| Real Graph | Model、Tool、Subagent、并发和原始异常语义 | `tests/observability/test_graph_tracing.py` | passed：Model/Tool/Subagent、并发隔离和 Model/Tool/interrupt/cancel/timeout 原语义均通过 |
| External exporter | 真实 Langfuse Trace ingestion | `RUNTIME_R5=1 uv run pytest tests/e2e/test_langfuse_real.py -m e2e -q` | passed：1 passed，包含 `auth_check()` 和 flush |
| Real model | 真实 DeepSeek reference Agent | `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q` | passed：1 passed |
| Production image | Dockerfile 真源、镜像构建和目标 startup | CLI 生成物对照、build、PostgreSQL/Redis、`/info`、SIGTERM | partial：镜像构建和 app import 通过；entitlement `403`，容器退出码 `3` |
| Artifact integrity | OpenSpec、差异、图谱 | strict validate、`git diff --check`、`rtk graphify update .` | passed：OpenSpec strict valid、diff check clean、33,680 nodes / 67,624 edges / 1,493 communities |

## Required Commands And Inputs

```bash
cd apps/runtime-service
uv run pytest tests/observability -q
uv run pytest tests -q
RUNTIME_R5=1 uv run pytest tests/e2e/test_langfuse_real.py -m e2e -q
cd ../..
uv run langgraph dockerfile -c ./langgraph.json /tmp/runtime-service-r5.Dockerfile
docker build -f deploy/Dockerfile -t runtime-service:r5-harness .
openspec validate "runtime-service-r5-observability-closure" --strict --no-interactive
git diff --check
rtk graphify update .
```

真实 smoke 只从现有环境读取 `LANGFUSE_ENABLED`、`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、
`LANGFUSE_BASE_URL` 及项目已有模型凭据；不得在日志、测试输出、verification 或提交中写入 secret。

## Results

本轮已完成 Runtime 生命周期、可信 metadata、真实 Graph callback、结构化诊断和真实 Langfuse smoke。
专项 `25 passed`，Runtime 全量 `146 passed, 12 skipped`，真实 Langfuse 与真实 DeepSeek 各 `1 passed`。
12 个 skip 属于未提供 Durable/集成资源的测试，不作为完成证据。

`rtk graphify update .` 完成，当前图谱为 `33,680 nodes / 67,624 edges / 1,493 communities`。

锁定 CLI 生成的 Dockerfile 已与仓库 `deploy/Dockerfile` 对照，仓库文件包含生成物要求的
`LANGGRAPH_AUTH`、`LANGGRAPH_HTTP` 和 `LANGSERVE_GRAPHS`。目标镜像构建成功，image ID 为
`d44956945b33`，完整镜像 digest 为
`sha256:d44956945b334a17535c8fd68a9265d52b1c32ff59b35d0d8d300f1ff20dfa71`。构建器报告
`SecretsUsedInArgOrEnv: ENV "LANGGRAPH_AUTH"`；该值是 auth 配置 JSON，不包含真实凭据，但 warning
保留为 Docker 静态检查结果。

生产容器尝试使用隔离的 PostgreSQL/Redis，二者均通过健康检查。Agent Server 成功加载 custom auth、
`/deps/runtime-service/src/runtime_service/webapp.py:app` 并连接两项依赖；随后访问 LangSmith entitlement
endpoint 得到 `403 Forbidden`，combined lifespan 在 application startup 完成前失败，容器退出码为 `3`，
`/info` 未能返回。由于进程未进入 ready，不能继续把 SIGTERM、custom lifespan shutdown、bounded flush
或 drain 标记为通过。

## Uncovered Boundaries And Residual Risk

- 目标镜像已证明 custom app import，但当前 LangGraph Cloud entitlement `403` 阻断完整 async lifespan；
  取得有效 Agent Server 资格后必须重跑 startup、`/info`、SIGTERM、bounded flush 和退出码验证。
- Langfuse SDK 的 callback 异常与真实 endpoint smoke 已覆盖；SDK queue saturation 仍未接入 Runtime
  稳定 `event_dropped` Counter，因此 tasks 3.1/3.2 保持开放。
- 结构化 logging `extra` 是否被部署平台转换为可查询字段，属于基础设施配置；Runtime 只提供稳定字段契约。
- Langfuse Trace 不证明 Run、SSE、Checkpoint、Audit 或权限成功；这些事实源仍由 Agent Server/Platform 负责。
- 跨服务 parent/baggage 传播和 Durable Run 生产恢复不属于 R5 closure。

## Docs / Runbook Impact

knowledge 16、24、28、31、`apps/runtime-service/README.md` 和 deployment README 已同步当前证据。
R5 Harness 表逐项记录 `是否实现`、源码、测试和命令；未通过的 queue drop 与生产生命周期继续标记
`❌` 或 partial，不能因本地测试通过而写成 R5 完成。

## Disposition

当前：`runtime local-complete / production-exporter partial`。不归档；等待 queue drop Counter 与目标生产
容器 lifecycle 证据后再完成剩余任务。
