## 1. 工具运行时语义

- [x] 1.1 修改 `RuntimeRequestMiddleware`，以 `request.tools` 为基线保留已注册工具，并追加 required 与允许的 public optional 工具后去重。
- [x] 1.2 修改工具 registry/resolver 的空请求语义，使 `enable_tools=true` 且没有 Agent 默认 allowlist 时不公开 builtin 或 MCP 工具。
- [x] 1.3 审查使用运行时 resolver 的服务 graph；静态工具在 graph 创建时注册，缺少执行路径的动态工具不再仅在 `wrap_model_call` 中注入。

## 2. 服务模块边界

- [x] 2.1 审查生产 Agent 是否位于 `runtime_service/services/<agent>/`，仅把跨 Agent 的 middleware、runtime context 和公共工具保留在共享层。
- [x] 2.2 保持 `platform-api` runtime gateway 只做 context 归一化与受信任项目范围注入，不引入 runtime 工具解析或图执行。

## 3. 验证与治理证据

- [x] 3.1 扩展 runtime-service 单测，覆盖业务工具保留、DeepAgents 内置工具保留、`enable_tools=false`、默认 allowlist、空工具请求、未知工具和动态工具执行约束。
- [x] 3.2 运行 runtime-service 的相关单测与 `compileall`，记录命令、结果和剩余风险。
- [x] 3.3 运行 platform-api runtime gateway contract 测试，确认工具选择仍只进入 runtime `context`，项目范围注入不变。
- [x] 3.4 执行 `rtk graphify update .`，并在 `verification.md` 记录预实施批准、验证证据、未覆盖边界和结论。
- [x] 3.5 评估运行手册与 API 文档影响；至少记录“调用方需显式选择公共工具或由 Agent 声明默认 allowlist”的兼容性说明。
