# R6 验证 Harness 与问题处理规范

> 目的：把 R6 Durable Run 的问题处理从“反复重试”变成可审计的单次修复、单次验证流程。
>
> 适用范围：`apps/runtime-service` 与通用 GraphHarbor 发布物；不把 Runtime 专属业务逻辑写入 GraphHarbor。

## 1. 核心规则

### 1.1 证据优先级

结论必须按以下顺序取证：

1. 实际安装的包版本和来源；
2. 独立 API、Worker、PostgreSQL、Redis 进程；
3. `/ready` 和鉴权 readiness；
4. 真实 API/Worker 行为；
5. PostgreSQL 中的 Run、事件和终态记录；
6. 单元测试、静态检查和文档。

局部测试、跳过测试、本地 wheel、已有进程的偶然成功，都不能单独升级为生产完成。

### 1.2 一次修复、一次验证

每次问题处理必须建立一条记录：

```text
症状 -> 最小复现 -> 根因证据 -> 单次修复 -> 干净环境 -> 一次验证 -> 接受或阻塞
```

修复后验证失败时，不得立即重复执行。必须先回答：

- 验证是否真正进入了被修复的代码路径；
- 是否使用了目标包版本和目标配置；
- 是否存在环境污染、端口冲突、旧 Worker 抢任务或空密钥；
- 失败是否改变了根因，还是同一失败的重复输出。

没有新的根因证据，不允许重新跑同一命令。

### 1.3 停止条件

出现下列任一情况立即停止并记录 `blocked`，不通过重试掩盖：

- 目标公开包无法由锁文件解析；
- 发布 workflow 失败或包尚未在目标 index 可见；
- API/Worker 使用不同版本或不同配置；
- 鉴权密钥为空、来源不明或测试 token 与服务端不匹配；
- 验证环境存在第二套 API/Worker 可能消费同一 Run；
- `/ready` 未通过就开始业务测试；
- 失败日志被 `DEVNULL`、截断或未保存，无法区分产品失败和 Harness 失败。

### 1.4 Docker 资源生命周期

端口冲突和旧容器抢任务属于 Harness 缺陷，不能归咎于 Runtime。每个验收批次必须遵守：

1. 预先登记 `project name`、宿主 API 端口、PG/Redis 端口和 Redis prefix；启动前用
   `lsof -nP -iTCP:<port> -sTCP:LISTEN` 与 `docker ps --format ...` 检查，端口已占用就停止，不得直接换端口
   重跑同一批次。
2. 使用带时间戳的独立 Compose project；API、Worker、PG、Redis 只能从这一套 project 启动，禁止额外
   `docker run` 或复用旧 Worker。
3. 验收脚本必须在正常结束、失败和中断时执行
   `docker compose ... down --remove-orphans`。清理容器和网络时不加 `--volumes`，避免误删 Durable
   证据；只删除已确认属于该批次的临时镜像和 dangling build image。
4. 清理后再次扫描 project label、容器名、监听端口和目标镜像 tag，确认没有残留；禁止无范围执行
   `docker system prune -a`，因为它可能删除其他项目的镜像和缓存。

本次 `18123` 冲突就是违反第 1、3 条：旧 `runtime-service-post17-api` 没有在验收结束时释放端口。
以后只有“预检通过 -> 启动 -> 验收 -> finally 清理 -> 残留扫描”完整闭环，才允许记录验收结果。

### 1.5 基础设施测试环境门禁

涉及 PostgreSQL、Redis、API 或 Worker 的测试不得直接执行裸 `pytest`。执行前必须先选定且
记录下列三种环境之一：

| 测试类型 | 允许的环境 | 唯一入口 | 禁止事项 |
| --- | --- | --- | --- |
| 纯 Unit/Contract | 无外部服务 | 指定的 `pytest` 文件/标记 | 不得因本机恰好有 PG/Redis 而升级结论 |
| GraphHarbor 仓库生产测试 | 显式 `DATABASE_URI`/`REDIS_URI` 指向的专用测试库 | GraphHarbor `./scripts/test.sh` | 禁止依赖 `conftest.py` 的 `postgres:postgres@localhost/langgraph` 默认值 |
| Runtime R6 acceptance | 独立 Compose project 内的 PG/Redis/API/Worker | Runtime R6 smoke/acceptance 命令 | 禁止连宿主默认库、复用其他 Worker 或共享 Redis prefix |

正式测试不允许“未配置就回落到 localhost”。`localhost` 只有在它是已登记的专用测试
服务时才允许使用，且 URI 必须由当前 shell 或指定 env 文件显式提供。

每次启动测试前必须完成下列预检；任一项失败时测试数必须为 `0`：

1. 确认 `DATABASE_URI`、`REDIS_URI`、Compose project、Redis prefix 和宿主端口均已显式设置；
2. 在不输出密码的前提下记录 PG/Redis 主机、端口、PG 用户、数据库名和 Redis DB；
3. PostgreSQL 建立真实连接并执行 `SELECT current_user, current_database(), version()`；
4. Redis 建立真实连接并执行 `PING`，确认 prefix 不与已运行批次重复；
5. 确认当前账号有 migration、建表和清理测试数据所需权限，且目标不是业务或生产数据库；
6. 只有 PG/Redis healthy、migration 成功且 API/Worker `/ready` 通过后，才允许创建测试数据。

GraphHarbor 仓库已有的 `scripts/test.sh` 是生产测试的 Harness：它在 pytest 之前用相同
`DATABASE_URI`/`REDIS_URI` 建立真实连接。直接运行
`pytest libs/langgraph-runtime-pg/tests` 只能用于已明确完成上述预检的快速循环，不得作为发布证据。

结果分类必须保持互斥：

- 连接、账号、权限、端口或 readiness 预检失败：`environment blocked / tests not executed`；
- fixture/setup 因 URI 或基础设施失败：`Harness failed`，不得记为代码回归失败；
- 预检通过后出现 assertion failure：才能记为 `product/test failure`。

`18 passed, 33 errors` 就是反例：执行者绕过 `scripts/test.sh` 的预检，pytest 又默认连接
`postgres:postgres@localhost:5432/langgraph`，而本机没有 `postgres` 角色。正确结论应是“Harness 环境
未对齐，基础设施测试未执行”，而不是“18 项生产能力通过、33 项代码失败”。

### 1.6 本轮 R6 的明确延期

本轮只验收 Durable Core、API/Worker 生命周期、Thread Workspace、事件 replay 和唯一终态。以下项目
由 owner 明确标记为 `deferred`，不在本轮追加测试：

| 项目 | 状态 | 责任边界 |
| --- | --- | --- |
| 真实 Sandbox Provider、任意远程 MCP 的生产恢复/cleanup/配额 | `deferred` | Runtime/Deep Agents 与外部 Provider；GraphHarbor 不实现具体 Provider |
| Langfuse/OTLP 生产服务故障矩阵和跨服务传播 | `deferred` | Runtime 观测适配与 Platform；GraphHarbor 只提供通用 correlation 传递 |
| Runtime 真实 rollback rehearsal | `deferred` | Runtime 部署与数据库 owner |
| Platform 灰度、route ownership 和 rollback | `deferred` | `platform-api` / Platform |
| 性能 SLO、queue lag、PG/Redis watermark | `deferred` | GraphHarbor 通用指标与部署观测 |

延期项仍是未实现能力，不能填 `✅`；但不应当成当前 R6 Durable Core 的失败。恢复某项时必须建立
独立批次、明确输入和 owner，再执行一次对应验收。

## 2. 配置契约：为什么宿主 `.env` 不会进入容器

本次反复失败的根因不是“没有配置模型凭据”，而是配置链路混用了两个职责不同的文件：

| 配置层 | 唯一职责 | 是否进入容器 |
| --- | --- | --- |
| `apps/runtime-service/.env` | 宿主机本地 Python 测试和脚本 | 否，`.dockerignore` 明确排除 |
| `apps/runtime-service/deploy/.env.runtime-service` | Compose API、Worker 的部署注入 | 是，必须显式存在 |
| `docker compose --env-file ...` | Compose 文件插值，例如镜像、端口、数据库地址 | 只影响插值，不替代服务 `env_file` |
| `environment` | 仅放容器内部生成的 `DATABASE_URI`、`REDIS_URI` | 会覆盖同名 `env_file` 值 |

标准启动方式只有这一种：

```bash
docker compose \
  -f apps/runtime-service/deploy/docker-compose.runtime-service.yml \
  --env-file apps/runtime-service/deploy/.env.runtime-service \
  config

docker compose \
  -f apps/runtime-service/deploy/docker-compose.runtime-service.yml \
  --env-file apps/runtime-service/deploy/.env.runtime-service \
  up -d
```

部署 env 文件必须由 secret store 或人工安全注入生成，不能提交 Git，也不能 bake 进镜像。至少要有：
`PLATFORM_RUNTIME_DELEGATION_SECRET`、`GRAPHHARBOR_RUNTIME_CONTEXT_SECRET`、两者对应的 issuer/audience，
以及 `reference_agent` 使用的模型 URL、API key 和默认模型。API、Worker、测试 token 必须使用同一组
secret；外部 delegation secret 与 API-to-Worker RuntimeContext secret 不是同一个配置项。

启动前的唯一配置检查命令：

以下命令均在 `apps/runtime-service` 目录执行。

```bash
uv run python scripts/validate_runtime_config.py \
  --env-file deploy/.env.runtime-service
```

检查器只报告 `present/empty` 和字段名，不打印 secret。它还会拒绝缺失文件、空必需值、短 secret、非法
URL、非正数限制和相对 Workspace 路径。检查器会模拟 shell 环境优先级；若 shell 中存在同名空变量，
它会按 Compose 的实际优先级失败，避免“文件里有值但进程实际拿到空值”的假通过。

## 3. 本轮错误分类

### 3.1 GraphHarbor 产品根因

历史版本 `0.13.0.post17` 的 `langhost.cli._resolve_port()` 预探测端口没有设置
`SO_REUSEADDR`。旧 API 关闭后进入 `TIME_WAIT` 后，CLI 预探测失败并静默选择随机端口，第二个 API
进程没有监听原端口。

GraphHarbor `post20` 已把端口复用修复带入正式 PyPI wheel，并在正式 `post20` 镜像内通过进程级
同端口探针。结论仍必须以 wheel 和镜像实测为准，不能只用 commit、tag 或版本号推断产物内容。

### 3.2 发布物状态错误

仓库 tag 是 `v0.13.0.post18`，但发布 workflow 失败时，目标 PyPI index 仍只有
`0.13.0.post17`。此时不能把源码、Dockerfile 或 lock 文件硬改成无法解析的 `post18`。

预防：发布后必须用目标 index 执行精确安装检查；仓库 tag、GitHub Release、PyPI simple index 和
Runtime `uv.lock` 四者不一致时，状态只能是 `blocked`。

### 3.3 鉴权配置错误

Compose 以空的 `PLATFORM_RUNTIME_DELEGATION_SECRET` 或
`GRAPHHARBOR_RUNTIME_CONTEXT_SECRET` 启动时，API 返回 `401 Runtime auth is misconfigured`，
这是 R1 fail-closed 的正确行为，不是绕过鉴权或修改服务逻辑的理由。

预防：测试环境使用单独的本地测试密钥，同时注入 API、Worker 和测试 token；禁止从生产 `.env` 猜测
空值含义，也禁止在日志中输出密钥。

### 3.4 共享进程污染

在已有 API/Worker 容器内再启动临时 API/Worker，会产生旧 Worker 抢 Run、不同环境消费同一队列和
错误密钥处理 Run 的风险。

预防：验收前只允许一套 API、Worker、PG、Redis；使用独立 Compose project、独立 Redis prefix、
独立端口和临时 Workspace。只停止测试服务，不删除 PG、Redis 或 Workspace volume。

本次实际复现：故障注入脚本启动的 Worker 与 Compose 常驻 Worker 共用 PostgreSQL；常驻 Worker
抢先完成了 Run，导致被测 `SIGTERM` Worker 没有写入 `shutdown_requeue`，但 Run 仍然显示
`success`。以后 Worker fault injection 必须先停止同一数据库上的其他 Worker，并在数据库中确认
没有第二个消费者；恢复跨网络 SSE 前则必须重新启动唯一 Worker 并确认其 ready。

### 3.5 端口与 readiness 时序错误

诊断 API 占用验收端口、API 重建后未等待 `/ready`、或者测试直接请求刚启动的容器，会分别产生
`bind`、连接拒绝和 `ReadError`。这些不能作为业务能力失败。

预防：端口分配表必须先确定；所有测试在 `/ready == true` 后开始；重建服务后重新等待 ready；启动
失败必须保留 stderr 和进程退出码。

脚本的 API 地址还必须区分宿主映射端口和容器内部监听端口：本次容器内 API 为 `8000`，我曾漏传
`RUNTIME_DURABLE_URL`，脚本按默认值访问 `8123` 并在业务请求前失败。容器内调用必须显式传
`RUNTIME_DURABLE_URL=http://127.0.0.1:8000`；跨网络客户端必须使用宿主映射地址，并在 API 和 Worker
均 ready 后再建立 SSE 连接。只看到 API ready 不能证明队列已有消费者。

bridge SSE 不再手工执行裸 `docker run`。统一使用
`apps/runtime-service/scripts/r6_network_sse_acceptance.sh`：脚本要求显式的 `r6-*` Compose project、
Compose env file、已发布 Runtime 镜像、宿主 API 端口和测试 Token；先停止并以 `--scale worker=1` 启动目标 project 的
唯一 Worker，检查 API `/ready`，再由客户端执行 `recovery_demo` 成功功能探针。功能探针通过后才创建
实际 SSE Run，客户端使用显式宿主映射 URL，所有 SSE 读取都有超时。默认退出执行
`docker compose ... down --remove-orphans`，不删除 volume；`R6_KEEP_SERVICES=1` 只用于排查，不作为
正式验收默认值。

### 3.6 Runtime Context 兼容性错误

唯一一次 post18 正式验收中，Workspace Run 进入 `runtime context contains unknown claims`。
这说明 GraphHarbor 生成的通用 Runtime Context envelope 与 Runtime 的严格 claim 白名单没有完成
契约对齐。fail-closed 是正确结果；不能直接放宽白名单，必须先记录 envelope 的字段集合、确认字段
归属，再由双方契约测试锁定。

### 3.7 模型凭据没有进入容器

宿主 `apps/runtime-service/.env` 中存在模型配置，但 `.dockerignore` 明确排除 `.env`，而部署目录的
`.env.runtime-service` 没有实际文件。因此镜像内 `DEEPSEEK_PROXY_*` 和 `GPT_PROXY_*` 为空，
`reference_agent` 只能返回 `runtime.model.initialization_failed`。

预防：`.env` 永远不能 bake 进镜像；部署时必须显式提供部署 env file 或 secret store，并在启动前
检查必需变量存在。凭据注入检查只能输出 `present/empty`，不能输出值。

## 4. R6 Demo 最小矩阵

Demo 是验收夹具，不是生产 Agent 数量。生产 `langgraph.json` 只注册正式生产 graph；
`langgraph.r6.json` 只用于 R6 专项验证。

| Demo | 是否需要 | 覆盖能力 | 说明 |
| --- | --- | --- | --- |
| `reference_agent` | 必须 | 真实模型、基本 Thread/Run/Checkpoint | R6 核心纵向链路 |
| `workflow_demo` | 必须 | 条件边、Interrupt/Resume、多次恢复 | R6 HITL 顺序与 checkpoint |
| `recovery_demo` | 必须 | Worker SIGTERM/SIGKILL 接管 | 确定性 checkpoint recovery |
| `failure_demo` | 必须 | 不可恢复 Tool failure | 唯一 error 终态 |
| `timeout_demo` | 必须 | Worker deadline/timeout | 独立于模型 Tool loop，避免假阳性 |
| `disconnect_demo` | 必须 | SSE 断线后 Run 继续与 replay | 网络验收和 cursor 语义 |
| `workspace_demo` | 必须 | Thread Workspace 恢复、隔离、fail-closed | R6 `30-R6-010` |
| `backend_demo` | R4 必须，R6 可复用 | Backend/Thread checkpoint 隔离 | 不是新增 R6 生产 Agent |
| `mcp_demo` | R4 必须 | 本地 MCP loader、冲突和 Tool Policy | 本地能力 Demo，不等于远程 provider |
| `mcp_probe` | 后续 hardening deferred | Streamable HTTP MCP 恢复 | 本地 provider 可复用；任意远程 provider 不在本轮门槛 |
| `sandbox_demo` | 后续 hardening deferred | Sandbox binding 和拒绝语义 | 没有真实 provider 时不得宣称生产通过 |

`failure_demo`、`timeout_demo`、`disconnect_demo`、`recovery_demo` 已共用一个模块中的确定性
graph factory，不是四套重复 Runtime。为了保持每个验收项单一职责和故障证据清晰，不建议合并成
一个通过 `operation` 分派的超级 Demo；那会让失败矩阵和 Run 终态难以定位。

## 5. 一次性 R6 验证流程

### 5.0 测试环境预检记录

每一次正式验收必须先保存一份以下记录；不允许用“ 大概能连上”代替：

```text
batch=<唯一批次 ID>
source=<PyPI version or explicit test build>
compose_project=<unique project name>
database_target=<host:port/database; no password>
database_probe=<current_user/current_database/SELECT 1 result>
redis_target=<host:port/db/prefix; no password>
redis_probe=<PING result and namespace>
api_target=<host port>
worker_target=<same image/version as API>
config_probe=<validate_runtime_config result>
readiness=<postgres/redis/migrate/api/worker results>
test_command=<exact command>
cleanup=<down --remove-orphans result>
residue_scan=<project/port/container/image scan result>
```

`DATABASE_URI` 和 `REDIS_URI` 必须在执行者环境中显式可见，且探针必须使用同一组值；不能先用一组 URI
预检，再让 pytest 通过 `conftest.py` 回落到另一组 URI。如果测试库账号不存在、连接权限不足，或任一
测试默认值指向未登记的 `localhost`，必须在 pytest 前停止并标记 `environment blocked`。

最小预检必须建立真实 PG/Redis 连接并输出非敏感身份信息：

```bash
DATABASE_URI="<explicit-test-uri>" REDIS_URI="<explicit-test-uri>" \
  uv run python - <<'PY'
import asyncio
import os
import asyncpg
import redis.asyncio as redis

async def main():
    uri = os.environ["DATABASE_URI"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(uri)
    try:
        print(await conn.fetchval("SELECT current_user || '/' || current_database()"))
    finally:
        await conn.close()
    client = redis.from_url(os.environ["REDIS_URI"])
    try:
        print(await client.ping())
    finally:
        await client.aclose()

asyncio.run(main())
PY
```

正式测试还必须证明 Compose 内 API、Worker 与 migration 使用同一镜像和同一组内部 URI；容器内不得把
宿主 `localhost` 当作 PG/Redis 地址。GraphHarbor 仓库的 `scripts/test.sh` 是其正式生产测试 Harness，
因为它会在 pytest 前用同一 `DATABASE_URI`/`REDIS_URI` 建立连接。直接运行其 runtime pytest 只能作为已完成
预检后的快速循环，不能作为发布证据。

结果分类必须互斥：

- 连接、账号、权限、端口或 readiness 预检失败：`environment blocked / tests not executed`；
- fixture/setup 因 URI 或基础设施失败：`Harness failed`，不得记为代码回归失败；
- 预检通过后出现 assertion failure：才记为 `product/test failure`。

本次 `18 passed, 33 errors` 的正确结论是“ Harness 环境未对齐，基础设施测试未执行”：pytest 绕过了
`scripts/test.sh` 的预检，回落到 `postgres:postgres@localhost:5432/langgraph`，而本机没有 `postgres`
角色。以后没有预检记录就没有正式测试结论。

readiness 响应必须用 JSON 解析并断言 `ready is true`，禁止用 `grep '"ready":true'` 之类依赖空格和
序列化格式的文本匹配。容器配置审计也禁止执行全量 `docker inspect` 环境枚举；只允许读取镜像、启动
命令等非敏感字段，secret 和模型凭据只能通过白名单检查器报告 `present/empty`。一旦诊断输出意外包含
secret，应立即停止传播和记录该输出，并按凭据管理策略评估轮换。

### 发布前

```bash
uv build --package graphharbor-runtime --package graphharbor
uv run python scripts/check_versions.py
```

使用 `~/.my_best/.env` 中的发布凭据时，只从 shell 环境读取，不打印 token。双包发布后，先检查目标
index 是否同时可见，再进行 Runtime 变更。

### Runtime 切换前

1. `pyproject.toml`、`uv.lock`、Dockerfile、镜像内 metadata 必须是同一版本；
2. 使用全新 Compose project 和独立数据边界；
3. API、Worker、测试客户端使用同一组测试密钥；
4. API 和 Worker 均 ready 后才创建 Assistant/Thread/Run；
5. 保存版本、容器、端口、Redis prefix、Run ID 和 PostgreSQL 终态证据。

### 修复后

只执行一次完整 acceptance，至少覆盖：

- Thread 连续 Run 与 checkpoint；
- Worker replacement；
- API 同端口 restart；
- interrupt/resume 与 SSE replay；
- cancel、timeout、Tool failure 唯一终态；
- Workspace Thread/tenant 隔离和不可用根 fail-closed；
- PostgreSQL 事件中 terminal event 数量为 1。

结果只能写成 `passed`、`failed` 或 `blocked`。`blocked` 不允许被改写成 `passed`，也不允许用
另一次相同环境重试替代根因修复。

本轮 owner 明确延期的生产 hardening 项目使用 `deferred` 单独记录，不纳入上述一次性 acceptance：
真实 Sandbox/远程 MCP Provider、Langfuse/OTLP 服务故障、真实 rollback、Platform 灰度和性能 SLO。
本地 MCP、Langfuse smoke、rollback dry-run 和性能 baseline 只能证明局部能力，不能替代未来验收。

## 6. 历史 R6 状态（post18 验证批次）

- GraphHarbor `post18` 双包已直接发布到 PyPI，Runtime lock、Dockerfile 和无缓存镜像均使用 `post18`；
- 唯一一次修复后完整 acceptance 已执行，结果为 `durable 7 failed, 6 passed, 2 skipped`，Workspace
  acceptance 也失败；
- 模型凭据和部署 env 注入修复已通过本轮配置检查，但尚未取得 API `/ready` 的容器证据；
- 该 post18 批次仍受 Runtime Context claim 契约阻塞，运行验证另外被宿主端口 `18123` 占用阻断；
- 该批次结论为 `durable-core-partial / production-cutover-blocked`，后续修复后必须重新建立新的验证批次。
- 当前可安装版本以 Runtime `uv.lock`、目标 PyPI index 和 30 号文档记录的 `post20` 预检为准，不能从本节历史结果推断当前包状态。

## 7. 历史配置修复验证记录（post18 批次）

验证批次：`2026-09-02 / r6-config-verify-20260902`。本轮只执行一次，使用独立 Compose project、独立
PG/Redis/Workspace volume 和一次性本地测试 secret；secret 内容未写入日志或文档。

执行的检查及结果：

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 部署 env 完整性 | ✅ | `uv run python scripts/validate_runtime_config.py --env-file deploy/.env.runtime-service` |
| Compose 插值与必需 `env_file` | ✅ | `docker compose ... config -q` |
| post18 镜像构建与包版本 | ✅ | Dockerfile metadata assertion；API/Worker 使用同一镜像 |
| PostgreSQL / Redis | ✅ | 独立容器 healthy |
| migration | ✅ | `migrate` 退出码 `0` |
| API `/ready` | ❌ blocked | 宿主 Docker Desktop 已监听 `18123`，Docker 返回 `port is already allocated` |

因此本轮结论是：**部署配置链路通过；运行时容器验收被 Harness 端口冲突阻断；R6 不能因此标记为
通过。** 按一次验证规则，不换端口重复执行；下一批验收必须先登记端口占用并重新创建全新的验证批次。

## 8. 本地基础设施、发布和回滚的固定路径

### 8.1 PostgreSQL/Redis 使用模式

本地 PostgreSQL/Redis 可以使用，账号也可以由执行者提供，但必须满足“专用数据边界 + 显式 URI
预检”两个条件。不要把“本机有 PostgreSQL/Redis”当成测试环境可用。

| 模式 | 是否支持 | 规则 |
| --- | --- | --- |
| 宿主 API/Worker + 宿主 PostgreSQL/Redis | 支持，最快 | API、Worker、migration 使用同一组显式 `DATABASE_URI`/`REDIS_URI`；不构建 Docker，不复用默认 `postgres:postgres@localhost/langgraph` |
| Docker API/Worker + 宿主 PostgreSQL/Redis | 当前 Compose 尚不支持 | 必须新增独立 host-infra Compose 文件或 profile，移除 `postgres`/`redis` 服务及其 `depends_on`，并把容器地址配置成 `host.docker.internal`；未完成前不得声称已切换 |
| 当前 `docker-compose.runtime-service.yml` | Docker PG/Redis | 文件会启动自己的 `postgres`/`redis`，API、Worker、migration 依赖它们并在容器内合成 URI；只修改 `RUNTIME_POSTGRES_HOST` 或 `RUNTIME_REDIS_HOST` 会留下错误依赖链 |

宿主进程模式的最小运行形态如下，真实 URI 只能从受控环境注入，不能写入文档：

```bash
cd apps/runtime-service
export DATABASE_URI="postgresql://<dedicated-user>:<password>@127.0.0.1:<pg-port>/<dedicated-db>"
export REDIS_URI="redis://127.0.0.1:<redis-port>/<dedicated-db>"
uv run graphharbor migrate upgrade
uv run graphharbor serve --host 127.0.0.1 --port <free-api-port> --config langgraph.json --n-jobs-per-worker 0
uv run graphharbor worker --config langgraph.json --n-jobs-per-worker 1
```

上面三个命令应在独立终端或受控进程管理器中使用同一组环境变量；启动前仍必须完成第 1.5 节
预检和 readiness。宿主 URI 中的 `<dedicated-user>`、`<dedicated-db>` 和 Redis DB/namespace
必须事先登记，不能使用业务库，也不能为了清理验收数据执行无范围 `DROP` 或 volume 删除。

数据库 owner 还必须确认：PostgreSQL 版本和所需 extension 与 GraphHarbor migration 兼容，测试
账号有 migration 所需权限；Redis 的 logical DB 或 key prefix 不与其他批次重叠。Docker 容器访问
宿主资源时禁止使用容器内的 `127.0.0.1` 指向宿主机。

### 8.2 GraphHarbor 发布门禁

GraphHarbor 的两个包 `graphharbor` 与 `graphharbor-runtime` 必须锁步发布。可以使用
`~/.my_best/.env` 中的 `UV_PUBLISH_TOKEN`，但只能在发布终端安全加载并通过 `uv publish`
传入，任何日志、命令回显和文档都只能记录 `present/empty`。`UV_TEST_PUBLISH_TOKEN` 只用于
TestPyPI 或等价测试 index。

当前仓库的 Trusted Publishing/OIDC workflow 是另一条发布路径。选择 token 发布后，不能把它
描述成 OIDC 已通过；选择 OIDC 后，不能再用本地 token 绕过 workflow 的审批和 CI 门禁。

发布顺序固定为：

1. 在 GraphHarbor 仓库确认两个包版本相同，`uv.lock --check`、版本脚本、lint、完整测试、build、wheel import smoke 全部通过。
2. 先发布 `graphharbor-runtime`，再发布 `graphharbor`；记录版本、wheel hash 和目标 index。
3. 用目标 index 做隔离安装，确认两个包同时可见且不是本地 editable/source 安装。
4. 再更新 Runtime 的 lockfile、镜像和部署记录；不能在目标 index 未出现时提前改依赖版本。

PyPI 版本不可覆盖。一个包成功、另一个包失败时，禁止重传同版本或直接删除已成功包；先保存
发布证据，修复发布流程后递增版本重新发布，并在 Runtime 侧继续保持旧的可安装版本。

### 8.3 回滚门禁

GraphHarbor 包发布是不可变的，回滚不是重传旧 wheel，而是把 API/Worker 回退到已验证的旧镜像
或虚拟环境，并保留 PostgreSQL、Redis 和 Workspace 数据。回滚前必须确认旧镜像对应的 lockfile、
GraphHarbor 双包版本和 migration 兼容矩阵。

回滚顺序固定为：停止新版本流量 -> 保留数据 -> 切换已验证旧 API/Worker -> readiness -> 最小
Run/Checkpoint/SSE replay -> 记录结果。migration 不可逆或备份恢复失败时停止切换，由数据库
owner 按备份恢复；验收脚本不得自动 downgrade、drop 库或删除 volume。Platform 的灰度比例、
route ownership 和 legacy upstream 切换另由 Platform change 管理。

### 8.4 一次验证后的清理

Docker 验收必须使用唯一 Compose project。正常结束、失败和中断都执行：

```bash
docker compose -p <unique-project> -f <compose-file> down --remove-orphans
```

清理不带 `--volumes`；只删除已确认属于该批次的临时容器、网络和 dangling build image。清理后
扫描 project label、容器名、监听端口、目标镜像和 Worker 进程；禁止执行无范围
`docker system prune -a`。宿主 PostgreSQL/Redis 不属于 Docker 验收资源，不能被清理脚本误杀。

这样每次验证都遵循同一闭环：配置来源 -> PG/Redis 预检 -> migration -> API/Worker 版本一致性
-> readiness -> 一次业务验收 -> `finally` 清理 -> 残留扫描。缺任何一步，结果只能是
`blocked/Harness failed`，不能靠重新跑测试把环境问题改成产品通过。

## 9. 历史前置 R6 closure 批次记录（2026-09-02）

本批次修复目标是 GraphHarbor 与 Runtime 的 `6.2/6.3/6.4` closure gate。GraphHarbor 当前源码
已包含严格 RuntimeContext claim 校验、通用 correlation 透传和显式端口拒绝/复用逻辑；两个
`0.13.0.post19` wheel 由该源码重新构建，安装在一次性容器中验证。该 wheel 不是 PyPI artifact，
不能改变 Runtime `uv.lock` 的正式来源判断。

唯一一次修复后进程验证使用：

```text
network=r6-verify-post19-20260902_default
database=postgres://runtime_service@postgres:5432/runtime_service (密码不记录)
redis=redis://redis:6379/0
image=aitestlab-runtime-service:r6-config-verify
temporary_container=--rm，未发布宿主端口
probe=apps/runtime-service/scripts/r6_api_restart_probe.py --port 18124 --timeout 120
```

探针先启动 API、等待 `/ready == true`，发送 SIGTERM，再用同一个显式端口启动第二个 API；结果为：

```json
{"status":"passed","port":18124,"first_exit_code":-15,"second_exit_code":null}
```

临时容器由 `--rm` 自动移除，没有启动第二套持久化 Compose 服务，也没有触碰现有 PG/Redis
volume。根据一次验证规则，本批次不再重复跑同一探针或宽泛回归测试。

| Gate | 结果 | 证据 | 当前边界 |
| --- | --- | --- | --- |
| `6.2` RuntimeContext producer/consumer | ✅ | GraphHarbor `langgraph_runtime_pg/auth.py`、`graph_executor.py`；`test_production_contract.py` | 未知 top-level/nested claims 拒绝；仍需正式发布物验收 |
| `6.3` explicit-port SIGTERM/restart | ✅（本地源码 wheel） | GraphHarbor `langhost/cli.py`、`test_cli.py`；`scripts/r6_api_restart_probe.py` | 本地修复通过；已发布 PyPI `post19` 尚不能视为包含修复 |
| `6.4` correlation/exporter fail-soft | ✅（focused） | GraphHarbor `test_observability.py`、`test_production_contract.py`；Runtime `tests/observability/` | focused contract 通过；生产 exporter 服务端故障仍是独立缺口 |
| `6.5` 正式 R6 acceptance（当时） | ❌ pending | OpenSpec `verification.md` | 该历史批次必须先发布包含修复的双包，再执行一次完整 acceptance；当前结果见第 11 节 |

本批次的正确状态是：`6.2/6.3/6.4 local-verified`，`formal-release-acceptance pending`。
任何文档、镜像或汇报都必须同时写明 artifact 来源；“本地 wheel 通过”不能升级为“PyPI
正式包通过”。

## 10. 历史 post20 正式验收记录（Harness 修复前，2026-09-02）

本次使用已发布 `graphharbor==0.13.0.post20`、`graphharbor-runtime==0.13.0.post20`，镜像
`aitestlab-runtime-service:r6-post20`，Compose project `r6-verify-post20-20260902`，API 宿主端口
`18134`，独立 PostgreSQL、Redis 和 Workspace 数据边界。readiness 返回 graph、PostgreSQL、schema、
Redis、queue 全部 `true`。

验收结果：

| 边界 | 结果 | 证据说明 |
| --- | --- | --- |
| Durable smoke | ✅ | 容器内显式设置 `RUNTIME_DURABLE_URL=http://127.0.0.1:8000`；真实 Run `success`，checkpoint 存在 |
| Worker `SIGTERM` | ✅ | 停止常驻 Compose Worker 后执行；从 `marker=checkpointed` 恢复，`shutdown_requeue=1`，terminal event=1 |
| Worker `SIGKILL` | ✅ | lease/reaper 接管，从 checkpoint 恢复，`success`，terminal event=1 |
| Thread Workspace | ✅ | Worker replacement、API restart、Thread/tenant 隔离、不可用根 fail-closed 均通过 |
| MCP | ✅ | discovery/call、Worker replacement、provider restart、missing/unavailable fail-closed 均通过 |
| API same-port restart | ✅ | `r6_api_restart_probe.py` 返回 `status=passed` |
| 独立 bridge SSE | ❌ blocked | 客户端建连时 Worker 尚未恢复，未收到 cursor；脚本未重试，不能形成正式证据 |

本批次还有两次被丢弃的 Harness 尝试：第一次漏传容器内 API URL，脚本默认访问错误的 `8123`；
第二次没有停止常驻 Worker，产生了错误消费者。它们不是产品通过证据。正确结论是：post20
已发布包的 Durable、Worker takeover、Workspace、MCP 和 API restart 原子能力通过，但 R6 formal
acceptance 因 bridge SSE 编排缺陷保持 `blocked`，OpenSpec `6.5/6.6` 不得勾选。

本批次已执行：

```text
docker compose -p r6-verify-post20-20260902 -f apps/runtime-service/deploy/docker-compose.runtime-service.yml down --remove-orphans
```

命令未带 `--volumes`；临时容器和网络已移除，`post20` 镜像和命名卷保留，旧 `post19/18123` 环境
未触碰。后续正式验收必须使用新增的 `r6_network_sse_acceptance.sh` 门禁；在新的单次验收完成前，
禁止把本次历史 blocked 结果改写为 pass；修复后的正式结果单独记录如下。

## 11. 修复后 post20 正式验收记录（2026-09-02）

修复后的 `r6_network_sse_acceptance.sh` 作为唯一入口执行了一次正式 bridge SSE 验收。脚本先通过
API `/ready`、唯一 Compose Worker 和真实 `recovery_demo` 功能探针，再使用独立 Docker bridge namespace
中的两个 SDK 客户端验证断线、游标恢复和最终 Run 终态。

```json
{
  "status": "passed",
  "api_readiness": "passed",
  "worker_readiness": "passed",
  "initial_cursor": 4,
  "resumed_event_count": 2,
  "run_status": "success"
}
```

清理结果为 `project_containers=0`、`project_networks=0`、`port_18135_listeners=0`，保留 3 个验收
数据卷，旧 `post19` 环境未触碰。此次结果闭合 `30-R6-008` 和 OpenSpec `6.5`；随后 owner acceptance、
spec sync 和 archive 已完成，OpenSpec `6.6` 已闭合。

这不改变生产状态：外部 Sandbox/远程 MCP、观测服务端故障、真实发布回滚和 Platform route ownership
仍未通过，生产切流继续保持 `not_ready`。后续不得再次执行同一 bridge SSE 验收；只有新的根因和新的
验收批次，才允许重新开启验证。
