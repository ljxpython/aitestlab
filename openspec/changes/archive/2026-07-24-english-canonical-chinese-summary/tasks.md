## 1. 仓库政策

- [x] 1.1 更新仓库 AI 执行标准，规定 OpenSpec 使用中文权威正文并保留必要的英文机器结构。
- [x] 1.2 更新人工使用指南，说明正文语言、保留英文的内容、采用范围和示例。
- [x] 1.3 更新 OpenSpec 共享 context，使产物生成和 apply 遵循中文唯一事实源政策。
- [x] 1.4 删除本 change 的 `summary.zh-CN.md`，避免保留第二份重复内容。

## 2. 验证

- [x] 2.1 运行 strict validation，证明官方 `spec-driven` schema 仍能识别中文正文和英文机器结构。
- [x] 2.2 检查 apply `contextFiles`，证明 LLM 直接读取标准中文权威产物且不存在语言镜像。
- [x] 2.3 检查仓库标准、使用指南和 OpenSpec context 的政策一致性。
- [x] 2.4 维护 `verification.md`，记录实施前评审、命令、输入、结果、未覆盖边界、残余风险、文档影响和最终 disposition。

## 3. 生命周期

- [x] 3.1 验收后将 `openspec-language-policy` delta spec 同步到 `openspec/specs/`。
- [x] 3.2 仅在验证与 disposition 满足仓库完成门禁后归档 change。
