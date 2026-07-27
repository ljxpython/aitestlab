## 1. Contract Fix

- [x] 1.1 移除 platform-web 线程搜索首请求中的不支持 `error` select 字段，保留受支持字段与现有 fallback。
- [x] 1.2 补充 workspace runtime gateway service 单测，断言首请求字段集不包含 `error`。

## 2. Verification

- [x] 2.1 运行 platform-web 相关单测、typecheck 和 build。
- [x] 2.2 复跑浏览器路径：登录 -> Graphs -> 打开 Chat，确认 `/api/langgraph/threads/search` 首请求不为 422 且控制台无错误。
- [x] 2.3 在 `verification.md` 记录预实施批准、命令、结果、残余风险和结论。
