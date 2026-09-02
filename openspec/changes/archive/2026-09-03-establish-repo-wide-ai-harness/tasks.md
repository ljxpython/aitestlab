## 1. Harness Entry

- [x] 1.1 新增 `docs/harness/README.md`，定义通用 Harness、七个 intake 维度、B1/B2/B3 和最短阅读路径
- [x] 1.2 在 `docs/README.md` 和 `AGENTS.md` 增加唯一 Harness 入口，保持现有 authority order 不变

## 2. Standards Alignment

- [x] 2.1 将 `docs/standards/01-ai-execution-system.md` 中过期的 Runtime Harness 测试路径修正为当前 `apps/runtime-service/tests/`
- [x] 2.2 明确 R0-R6 是 Runtime 领域实例，并链接 Runtime 对齐审计和服务级验证入口

## 3. Verification And Lifecycle

- [x] 3.1 增加入口导航、关键目录存在性和过期路径检查，不新增测试依赖
- [x] 3.2 维护本变更 `verification.md`，记录 owner review、local/chain/formal 证据、残余风险和 disposition
- [x] 3.3 运行文档检查、OpenSpec strict validate 和 `git diff --check`，确认当前标准与入口可读取
- [x] 3.4 owner acceptance 后同步 accepted spec 到 `openspec/specs/` 并归档本变更
