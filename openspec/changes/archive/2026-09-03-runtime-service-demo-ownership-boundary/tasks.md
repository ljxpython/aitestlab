## 1. 规划与所有权

- [x] 1.1 创建 `runtime-agent-service-boundary` 的目录所有权 delta spec。
- [x] 1.2 记录 `verification.md` 的 B3 pre-apply owner approval、范围和验证计划。

## 2. Demo 迁移

- [x] 2.1 将六个 Demo 包从 `services/` 移至 `demo/`，保留 `reference_agent`。
- [x] 2.2 更新 graph adapter、测试和受控验收脚本的内部导入，保持 graph ID 与配置入口不变。

## 3. 文档与验证

- [x] 3.1 更新当前目录设计、知识文档和 active OpenSpec 的路径引用；不改 archive。
- [x] 3.2 运行旧路径静态检查、配置解析、R0/定向/完整本地测试、文档检查和 OpenSpec strict validation。
- [x] 3.3 在 `verification.md` 记录命令、结果、未覆盖边界和 disposition。
- [x] 3.4 Owner acceptance 后同步 delta spec 到 `openspec/specs/` 并 archive；未经明确授权不执行。
