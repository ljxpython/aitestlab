## Why

真实浏览器联调发现，从 Graphs 打开 Chat 时前端首个 `POST /api/langgraph/threads/search` 请求包含 LangGraph 不支持的 `select: ["error"]`，上游返回 `422` 后前端才重试成功。这会产生可观测的浏览器错误和无意义的失败请求。

## What Changes

- 使 platform-web 线程列表的首个搜索请求只使用当前 LangGraph 支持的 `select` 字段。
- 补充前端回归测试，保证 Graphs 进入 Chat 时不会以 `422` 作为 fallback 控制流。
- 补充最短 `platform-web -> platform-api -> runtime-service` 浏览器联调证据。

## Capabilities

### New Capabilities

- `runtime-thread-search-contract`: 规范平台聊天线程搜索对 LangGraph 支持字段的使用及浏览器端验收。

### Modified Capabilities

- 无。

## Impact

- 所有者 locus：`apps/platform-web`；受影响链路：`platform-web -> platform-api runtime_gateway -> runtime-service LangGraph threads`。
- 执行等级：B3 Governed，原因是公开跨服务 runtime gateway contract 发生行为修正。
- 已加载标准：根 `AGENTS.md`、`docs/standards/01-ai-execution-system.md`、platform-api runtime gateway interface standard、platform-web 控制面与前端开发规范。
- 影响文件预计为 `apps/platform-web/src/services/runtime-gateway/workspace.service.ts` 及其测试；不修改 platform-api 或 runtime-service 的执行逻辑。
- 回滚方式：恢复前端字段列表即可；不涉及持久化或数据迁移。
