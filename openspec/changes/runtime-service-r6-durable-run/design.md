## Context

R0～R5 已完成新 Runtime 包、标准 `get_agent(config)` 入口、Middleware、能力隔离和 Langfuse
观测。当前缺口不是新的 Agent 抽象，而是证明 LangGraph Agent Server 在真实持久化和多 Worker
条件下能够正确保存、恢复和收敛 Run。

本变更属于 `apps/runtime-service` 的 B2 Chain 规划，执行面只依赖 Agent Server；Platform API
仍不改动。测试需要隔离的 PostgreSQL、Redis、Worker 和本地 Delegation Token。锁定的 LangGraph
CLI/SDK 版本是实现和验证的唯一运行时依据。

## Goals / Non-Goals

**Goals:**

- 在真实 Agent Server 部署中验证 `durability="sync"`、Checkpoint、Interrupt/Resume 和 Worker
  重启恢复。
- 固化 Stream 的 `since` 游标补发、事件去重和“断线不取消”语义。
- 让 cancel、timeout、Tool failure、graceful shutdown 和 hard shutdown 最终只产生一个明确终态。
- 验证 Thread-scoped Backend 在重连、隔离和清理时不串线。
- 提供不依赖 Platform API 的本地 smoke test，并保留快速 fake-model 测试。

**Non-Goals:**

- 不修改 Platform API、Run Coordinator、Run Explorer 或跨服务生产协议。
- 不实现自定义 Checkpointer、事件总线、队列、SSE 路由或 Worker 调度器。
- 不迁移旧 Runtime/Platform 数据，不兼容旧 Graph、旧路由或旧字段。
- 不在本阶段引入新的 `engine/`、`builder/`、`factory/`、`registry/`、`orchestrator/` 等公共层。

## Decisions

### 1. 使用 Agent Server 原生 Durable Run

Runtime 通过标准 Graph/Thread/Run/Stream 接口传递 `durability="sync"` 和恢复所需的
`thread_id`/`checkpoint_id`，Checkpoint、lease、sweeper 和恢复由 Agent Server 负责。这样与
Open SWE 的 `dispatch.py`/`server.py` 借鉴边界一致，但不复制其业务调度代码。

备选方案：在 Runtime 内写自定义 Run 表和恢复循环。拒绝，因为会产生第二套状态机并与 Agent
Server 的事实源冲突。

### 2. 真实基础设施优先，内存实现只做快速反馈

R6 增加测试专用 PostgreSQL、Redis 和 Worker 启动方式。Unit/Composition 继续使用 fake model
和内存 Backend；Durable、重启和断线测试必须命中真实部署。

备选方案：全部使用 in-memory saver。拒绝，因为无法证明进程重启和跨 Worker 恢复。

### 3. Stream 是可重建的观察通道

客户端保存服务端事件游标，重连时以 `since` 请求补发；消费端按 `(run_id, seq)` 去重。SSE
断开只关闭观察连接，不改变 Run 状态。若游标过期或事件不可补发，返回明确错误并要求重新
查询 Run snapshot，不伪造成功事件。

### 4. Interrupt/Resume 使用同一 Thread 和可验证恢复点

每次 interrupt 都记录可关联的 Run/checkpoint 标识。resume 必须携带原 Thread 和有效恢复
输入；多次 interrupt 按顺序验证，禁止用新 Thread 或宿主机内存状态“恢复”。

### 5. 关闭交给 Agent Server，资源由拥有者释放

Runtime 不注册全局 signal handler，也不实现 Run 扫描器。测试通过 Agent Server 的 drain、
lease/sweeper 和容器 SIGTERM 验证 graceful/hard shutdown；Service 私有 MCP/Backend 只在其
资源所有者边界释放。

### 6. 本地 Smoke 使用本地签发 Token

R6 提供测试用 Delegation Token signer/fixture，claims 仍经过 Runtime Auth、Resolver 和
Capability Policy 校验。它只替代 Platform 的签发动作，不绕过权限边界，也不成为生产凭据。

## Risks / Trade-offs

- [真实容器测试较慢] -> 独立 durable/e2e job，默认 CI 仍运行 Unit、Composition 和契约测试。
- [Agent Server 版本改变 replay 或 shutdown 语义] -> 将 CLI/SDK/镜像版本写入锁文件和测试报告，升级必须重新跑 R6 门槛。
- [事件保留窗口导致 since 游标失效] -> 明确返回 cursor-expired，使用 Run snapshot 恢复，不无限延长事件存储。
- [Worker 被强杀时没有最新 super-step] -> 只承诺恢复到最近 sync checkpoint，未持久化的步骤按 Agent Server 终态规则处理。
- [动态 Backend 重连失败] -> fail-closed 并保留原始错误类别，禁止回退到其他 Thread 或宿主机目录。

## Migration Plan

1. 在 R6 change 内增加隔离基础设施启动脚本/配置、Durable 测试和本地 smoke 命令。
2. 先运行静态 `reference_agent`、`workflow_demo` 的 sync checkpoint、interrupt/resume 和 replay 测试。
3. 再注入 Worker restart、cancel、timeout、Tool failure 和 SIGTERM，收集真实事件与终态证据。
4. 最后验证动态 Backend 的 Thread 隔离、重连和清理。
5. R6 门槛全部通过后，保留当前部署配置；失败回滚只停止 R6 测试部署，不触碰生产流量和旧数据。

## Open Questions

- 锁定版本的 Agent Server 是否提供 `since` replay 和 `RunControl` 的完整 CLI/SDK 参数，需要在实现前用官方文档和 `/info` 能力探测确认。
- durable job 使用 Docker Compose 还是现有 CI service containers，取决于仓库 CI 环境；两者都不得改变生产 Runtime 代码责任边界。
- Checkpoint/事件 TTL 的具体配置字段以锁定版本 schema 为准，不能凭文档猜测字段名。
