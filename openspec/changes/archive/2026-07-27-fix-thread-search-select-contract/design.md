## Context

platform-web 的 `listThreads` 首次调用会向 platform-api 透传 `select` 字段。当前列表包含 `error`，但本地 LangGraph `/threads/search` schema 不支持该字段；前端 catch 后删除 `select` 并重试，页面可继续加载但浏览器控制台保留 `422`。

## Goals / Non-Goals

**Goals:**

- 首个线程搜索请求符合当前 LangGraph schema。
- 保留现有线程列表字段和页面行为，不依赖失败重试。

**Non-Goals:**

- 不改变 platform-api adapter、LangGraph 版本或线程数据模型。
- 不执行真实模型调用或修改生产数据。

## Decisions

### 使用已支持字段，不以 fallback 隐藏 schema 错误

从前端 `select` 中移除 `error`，保留 LangGraph 支持的线程字段。现有 fallback 作为上游未来兼容保护保留，但正常请求不得触发它。

替代方案是在 platform-api 过滤字段。拒绝：platform-api 是受控网关，不应为前端已知的非法上游字段承担静默修正，且会掩盖客户端契约错误。

## Risks / Trade-offs

- [上游以后新增 `error` 字段] -> 仅在上游 schema 明确支持且有端到端测试后再加入。
- [fallback 仍可能掩盖未来字段错误] -> 回归测试断言首个请求字段集，并用浏览器联调检查无 `422`。
