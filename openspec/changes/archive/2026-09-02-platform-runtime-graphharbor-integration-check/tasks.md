## 1. Integration harness

- [x] 1.1 在 `apps/platform-api/tests/integration/` 增加显式环境门控的真实 Platform API HTTP 测试。
- [x] 1.2 覆盖 `/api/langgraph/info`、`/api/langgraph/graphs/search` 和 `/api/langgraph/threads`，断言项目 scope 和 GraphHarbor 响应结构。
- [x] 1.3 增加未认证请求和缺少集成环境变量的失败/skip 语义测试，不启动旧 `langgraph dev`。

## 2. Verification and documentation

- [x] 2.1 在隔离环境运行 Platform API、GraphHarbor API/Worker、PostgreSQL 和 Redis，使用匹配的 delegation secret 完成真实链路验收。
- [x] 2.2 运行 Platform delegation 定向回归、OpenSpec strict validate 和 `git diff --check`；全量 discovery 的两个既有 schema-provider 基线失败已记录在 `verification.md`，不计入本变更证据。
- [x] 2.3 更新 Runtime GraphHarbor 选型文档、Platform Runtime Gateway 联调清单和本变更 `verification.md`，记录结果与未覆盖边界。
- [x] 2.4 已获 owner acceptance，同步 accepted spec 并归档本变更；不执行生产灰度、回滚或 Platform route ownership 变更。
