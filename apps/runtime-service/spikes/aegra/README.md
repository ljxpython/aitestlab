# Aegra Compatibility Spike

这是一个可删除的兼容性试验，不是正式 Runtime 部署。它验证 Aegra 是否能承接当前
`async def get_agent(config: RunnableConfig) -> Pregel` 入口和 R6 Durable 语义。

## 前置条件

- Docker、Docker Compose（仅用于 PostgreSQL/Redis）、Python 3.13 和 `uv`
- `~/.my_best/.env` 中的真实 DeepSeek、豆包多模态和 Langfuse 配置，或显式设置
  `AEGRA_SPIKE_ENV_FILE`
- 不要把密钥写入本目录、测试输出或 OpenSpec 文件
- Spike 默认使用本地测试 token `aegra-spike-token`；可用 `AEGRA_SPIKE_AUTH_TOKEN` 覆盖

## 启动

```bash
./scripts/up.sh
```

默认服务地址：`http://127.0.0.1:2026`。
PostgreSQL 和 Redis 由 Compose 启动，Aegra API 在宿主机的 uv 隔离环境中运行。
当 `LANGFUSE_ENABLED=true` 时，启动脚本会将其映射为 Aegra 所需的
`OTEL_TARGETS=LANGFUSE`，两套 Langfuse 凭证变量仍只从私有 env 文件读取。

## 运行测试

```bash
AEGRA_SPIKE_E2E=1 ./scripts/test.sh
```

没有真实模型或 Langfuse 配置时，相关测试会报告 `blocked`/跳过；跳过不等于通过。

## 停止和清理

```bash
./scripts/down.sh
```

默认会停止本地 Aegra 进程并删除 PostgreSQL/Redis 容器，但保留 volume 以便排查。需要清理 volume 时：

```bash
./scripts/down.sh --volumes
```

## 版本

当前 Spike 固定 Aegra `0.10.4`，完整版本和运行命令见 `VERSIONS.md`。Aegra 通过
`aegra.json` 加载 `reference_agent`、HITL 和多模态夹具；正式 Runtime 的
`langgraph.json`、`pyproject.toml` 和 Docker 路径不会被这个 Spike 修改。
