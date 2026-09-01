## 1. Owner Gate And Baseline

- [x] 1.1 由任务所有者一起审阅 `proposal.md`、`design.md`、两个 delta spec 和本任务清单；记录批准或明确 waiver 后才 apply
- [x] 1.2 运行当前 R3 基线测试并把基线结果写入 `verification.md`，确认新增失败来自缺失接线而不是环境漂移

## 2. Tool Reliability Implementation

- [x] 2.1 在 `reference_agent/agent.py` 显式接入官方 `ToolRetryMiddleware`，只配置明确幂等 Tool、明确临时异常和有界参数
- [x] 2.2 接入官方 `ToolErrorMiddleware`，实现只处理可由模型修正异常的脱敏分类器，并保持未知异常、取消和 interrupt 传播
- [x] 2.3 用当前 `langchain==1.3.17` 真实 `create_agent` graph 验证 Tool retry 在内、Tool error 在外的实际调用顺序

## 3. Model Reliability Cases

- [x] 3.1 增加显式 test-only fallback model adapter，在有 adapter 时才装配官方 `ModelFallbackMiddleware`，生产匿名配置不启用
- [x] 3.2 增加显式 test-only model retry case，验证异常过滤、最大尝试次数和最终异常传播；确认默认生产路径不叠加 Provider retry
- [x] 3.3 增加真实 graph 的 Tool 成功、临时失败重试、可恢复错误、未知异常、fallback、model retry、超时和取消测试

## 4. Harness Documentation

- [x] 4.1 更新 `15-runtime-middleware-lifecycle-and-failure-semantics.md`，加入逐项 R3 对齐表，包含 `是否实现`、代码、验证、测试、案例和 Open SWE 取舍
- [x] 4.2 更新 `reference_agent/README.md` 和 `31-runtime-refactor-alignment-audit.md`，区分已接线、仅单测、local-complete、真实 E2E 和 Durable 未覆盖
- [x] 4.3 检查 28 号计划、R3 归档记录和 active spec 的状态措辞，移除“Tool Error/Retry 已接入”一类与代码不符的表述

## 5. Verification And Handoff

- [x] 5.1 运行 `uv run pytest tests/middlewares tests/services/reference_agent tests/test_r0_baseline.py -q` 和相关全套 Runtime 测试
- [x] 5.2 在可用凭据下运行 `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -q`；无凭据时明确记录 not executed
- [x] 5.3 运行 `uv run python -m compileall -q src tests scripts`、`uv lock --check`、`git diff --check` 和 `openspec validate --strict --no-interactive`
- [x] 5.4 运行 `graphify update .`，把命令、输入、结果、未覆盖边界、文档影响和最终 local/chain/E2E 判定写入 `verification.md`
