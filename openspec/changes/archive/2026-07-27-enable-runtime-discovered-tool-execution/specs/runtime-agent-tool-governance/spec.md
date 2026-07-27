## MODIFIED Requirements

### Requirement: 动态工具必须具有工具调用执行路径
runtime-service SHALL 只向模型公开已经在 graph 创建阶段注册的工具，或由同一 runtime middleware 在模型调用阶段解析、并能在工具调用阶段按相同 runtime context 与 allowlist 重新解析和绑定的运行时发现工具。不得只在模型调用阶段注入 ToolNode 无法执行的工具；执行阶段无法重新解析或不再获准的工具必须 fail-closed，且不得回退到其他工具实现。

#### Scenario: 静态可枚举工具
- **WHEN** 服务的工具可在 graph 创建时枚举
- **THEN** 服务必须在创建 graph 时注册该工具后才允许模型调用它

#### Scenario: 运行时发现工具有完整 middleware 执行路径
- **WHEN** runtime context 选择一个运行时发现工具，且 runtime middleware 能在模型调用和工具调用阶段使用相同授权输入解析该工具
- **THEN** 模型可以看到该工具，并且工具调用阶段必须绑定解析出的真实工具实现后再交给 ToolNode handler 执行

#### Scenario: 运行时发现工具缺少执行路径
- **WHEN** runtime context 选择的工具不能预注册且 middleware 没有工具调用阶段的绑定路径
- **THEN** runtime-service 不得向模型公开该工具

#### Scenario: 动态工具在执行阶段不再可用
- **WHEN** 模型已生成动态工具调用，但执行阶段的 resolver 无法再次解析该工具或该工具不再获准
- **THEN** runtime-service 不得执行缓存实现、其他同名来源之外的实现或任意替代工具，并返回未知或不可用工具结果

#### Scenario: 静态与动态工具名称冲突
- **WHEN** graph 已注册工具与 runtime resolver 返回工具具有相同的标准化名称
- **THEN** runtime-service 必须保留并执行 graph 已注册工具，不得由动态工具覆盖它

#### Scenario: 同步与异步执行保持授权一致
- **WHEN** 同一 runtime context 分别通过受支持的同步和异步 Agent 路径调用动态工具
- **THEN** 两条路径必须使用相同的 required/public 工具选择、名称匹配和 fail-closed 语义
