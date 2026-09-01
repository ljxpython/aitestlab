# Aegra Spike Versions

| Component | Pin / source |
| --- | --- |
| Aegra API | `aegra-api==0.10.4` |
| LangGraph | `langgraph==1.2.11` |
| LangGraph SDK | `langgraph-sdk==0.4.3` |
| Runtime Agent source | `apps/runtime-service/src` at test checkout |
| Config | `aegra.json` |
| Server command | `uv run --project spikes/aegra --env-file ~/.my_best/.env uvicorn aegra_api.main:app --host 127.0.0.1 --port 2026` |
| Database | PostgreSQL `pgvector/pgvector:pg16` |
| Queue | Redis `redis:7-alpine` (Compose dependency only) |

Aegra 不构建 Docker 镜像；使用 Spike 目录的 `pyproject.toml`/`uv.lock` 在宿主机隔离环境中启动。

Aegra 仓库调研提交：`392a5457b25754cdc828f14b0053abdefe8b6766`（2026-08-22）。
包版本和源码提交必须在升级时一起更新并重新执行 Spike。
