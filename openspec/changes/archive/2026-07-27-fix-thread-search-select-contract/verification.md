# Verification

## Pre-apply review

- Decision: Approved
- Owner approval or waiver: Owner approved implementation in this conversation.
- Scope: platform-web 线程搜索字段与 platform-api/runtime-service runtime gateway 浏览器联调。

## Baseline evidence

- 本地四服务健康检查均为 200，platform-api worker 正常。
- 浏览器路径“登录 -> Runtime -> Graphs -> 打开 Chat”可复现首个 `POST /api/langgraph/threads/search` 返回 422。
- 失败请求含 `select: ["thread_id", "metadata", "status", "created_at", "updated_at", "error"]`；runtime-service 返回 `error` 不在支持字段枚举中。

## Evidence

- `cd apps/platform-web && rtk pnpm test:run`: 34 test files, 93 tests passed.
- `cd apps/platform-web && rtk pnpm typecheck`: passed with no TypeScript errors.
- `cd apps/platform-web && rtk pnpm build`: passed.
- `rtk graphify update .`: completed after code changes.
- 浏览器路径“登录 -> Graphs -> assistant -> 打开 Chat”：首个 `/api/langgraph/threads/search` 返回 200，request body 的 `select` 仅包含 `thread_id`、`metadata`、`status`、`created_at`、`updated_at`；浏览器控制台 0 errors / 0 warnings。
- 实际 Agent 执行：创建 thread、`runs/stream`、history、thread detail 与 state 均返回 200；最小消息收到 `OK` 响应。

## Results

- platform-web 不再在首个线程搜索请求中发送不被 LangGraph 支持的 `error` 字段。
- `platform-web -> platform-api -> runtime-service` 的登录、项目范围、graph 目录、聊天线程和实际流式 run 已完成浏览器联调。

## Residual risk

- 本次真实 Agent run 使用无工具最小消息；工具调用的执行语义由 `harden-runtime-agent-tooling` 变更中的 runtime-service 测试覆盖。

## Disposition

- Accepted: local checks and browser end-to-end evidence passed.
