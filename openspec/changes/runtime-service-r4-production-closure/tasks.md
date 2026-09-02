## 1. 实施前门禁与基线

- [x] 1.1 完成 B3 owner 对 proposal、specs、design、tasks 的整体审阅，并将批准依据写入 `verification.md`
- [x] 1.2 固化当前 R4 baseline：原始 10 个 Demo 测试已扩展为 44 个定向闭合测试；此前确无真实 Tool 收缩和 Workspace 证据
- [x] 1.3 保持 R4 Service 的生产入口缺少已验证 Principal 时返回 `runtime.auth.missing_principal`，并为显式 `_runtime_test_*` adapter 保留隔离测试入口

## 2. Runtime Policy 与 Service 接线

- [x] 2.1 在 `deep_agent_demo`、`mcp_demo`、`backend_demo` 组合根显式声明 `AgentDefaults`、Runtime Context、Policy、Resolver 和 Middleware 顺序
- [x] 2.2 使业务 Tool、MCP Tool、Deep Agents 内置 Tool 使用同一份 resolved allowlist，并覆盖模型可见和执行前检查
- [x] 2.3 为匿名调用、旧 configurable 字段、客户端资源/凭据注入和未授权 Tool 补充稳定失败测试

## 3. Deep Agents 内置 Tool 收缩

- [x] 3.1 为 `deep_agent_demo` 显式配置只读 `FilesystemMiddleware`，仅保留 `ls`、`read_file`、`glob`、`grep`
- [x] 3.2 为 `backend_demo` 显式配置 `StateBackend` 对应的文件 Tool 集合，禁止无 Sandbox 时暴露 `execute`
- [x] 3.3 对 Bundled Skills 增加代码级只读 Permission，验证写入和编辑 `/skills/**` 在执行前失败
- [x] 3.4 为 Subagent 显式声明 `tools=[]`、自身 FilesystemMiddleware、Skill 和 Permission，验证不能继承父 Agent 未授予能力
- [x] 3.5 使用真实 `create_deep_agent` graph 测试模型可见 Tool surface、伪造 `execute`/`task` 调用和缺失执行路径

## 4. MCP 能力边界

- [x] 4.1 保持 MCP connection 和凭据只在 Service loader 内构造，拒绝客户端传入 URL、command、headers、token 或 Tool 实现
- [x] 4.2 补充 MCP 工具成功加载、名称冲突、必需/可选失败和关闭责任测试，禁止静默替换 Tool 集合
- [x] 4.3 验证 MCP Tool 进入 Runtime Policy allowlist，并在 Tool handler 前重新执行授权检查

## 5. Thread Workspace 实现

- [x] 5.1 将 `backend_demo` 的生产设计固定为 durable checkpointer 支撑的 Thread-scoped `StateBackend`，禁止 `FilesystemBackend`/`LocalShellBackend` 生产 fallback
- [x] 5.2 用显式 `_runtime_test_checkpointer` 注入本地测试 adapter，驱动真实 graph 验证同 Thread 跨 Turn 可读写
- [x] 5.3 验证不同 Thread 不能读取或修改彼此的虚拟 Workspace 文件
- [ ] 5.4 增加 checkpointer/backend 不可达、初始化失败、Thread scope 不一致和资源清理的 fail-closed 测试
- [ ] 5.5 增加真实本地 Agent Server durable chain 测试：graph 重建、Worker 重启和服务重启后同 Thread 文件恢复且两 Thread 仍隔离
- [ ] 5.6 增加 PostgreSQL/Redis/Worker restart、SIGTERM、备份恢复、TTL/清理和告警的 production-like 验证入口；外部资源不可用时记录 `blocked`/`not-executed`

## 6. 分层验证与文档

- [x] 6.1 运行 R4 local/minimal 测试，记录命令、输入、结果和未覆盖边界
- [ ] 6.2 运行最短相关链：Agent Server Auth -> Service `get_agent()` -> Runtime Middleware -> Deep Agents/MCP/StateBackend，并记录结果
- [ ] 6.3 只有 durable Agent Server、持久化依赖和真实 Sandbox 条件齐备时才运行 formal/production-like 验证，禁止用 local 结果替代
- [x] 6.4 更新 19、20、28、31 号知识文档中的实现状态、代码位置、测试位置、证据等级和部署前置条件
- [x] 6.5 持续维护本变更 `verification.md`，在代码完成后执行 `openspec validate "runtime-service-r4-production-closure" --strict --no-interactive`、`git diff --check` 和 `graphify update .`
