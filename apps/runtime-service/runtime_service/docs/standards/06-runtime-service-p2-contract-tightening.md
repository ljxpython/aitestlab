# runtime_service P2/P3：运行时契约收口与旧入口删除

> 本文档是当前有效标准，不是历史说明。
> 当前项目按“重做”处理，不做旧入口兼容，不做旧数据迁移，不保留双轨范式。

## 1. 当前结论

P2/P3 完成后的运行时标准已经明确：

1. **可信身份和项目只认 Agent Server `Auth`**
2. **每次运行的业务参数只认 `config.configurable.platform_runtime`**
3. **执行控制只认标准 `config`**
4. **线程 / 平台 / 服务私有字段只认 `config.configurable`**
5. **旧 runtime API 已删除，不再保留正式链路 compat 层**

换句话说，仓库里不再允许同时存在两套心智模型。

---

## 2. 已收死的业务契约

### 2.1 `project_id` 只认 Agent Server 认证结果

允许：

```python
runtime.server_info.user["project_id"]
resolve_trusted_runtime_context(runtime).project_id
```

禁止：

- `state["project_id"]`
- `config["metadata"]["project_id"]`
- `config["configurable"]["project_id"]`
- `config["configurable"]["platform_runtime"]["project_id"]`
- `config["configurable"]["x-project-id"]`
- 从 `system prompt` / 消息文本反推 `project_id`

缺失就直接报错。

### 2.2 `test_case_service` 不再做默认项目 fallback

当前已经删除：

- `test_case_default_project_id`
- `test_case_allow_default_project_fallback`

正式 Agent Server 链路的 `project_id` 必须来自 `Auth` 验证后的 delegation credential。
本地调试只能使用后续单独定义的显式 debug 入口，不得成为正式 resolver fallback。

### 2.3 `test_case_service` 的平台字段仍可从 `config/configurable` 读取

允许继续读这些执行/线程字段：

- `thread_id`
- `run_id`
- `batch_id`
- 私有服务配置，例如 `test_case_multimodal_parser_model_id`

这不属于公共业务契约污染。

---

## 3. 已删除的旧 runtime 入口

以下旧入口已删除，不再允许新代码继续引用：

### 3.1 已删除的类型 / 函数

- `AppRuntimeConfig`
- `ModelSpec`
- `build_runtime_config(...)`
- `merge_trusted_auth_context(...)`
- `resolve_model(...)`
- `apply_model_runtime_params(...)`
- `build_tools(options)`
- `build_assistant_tools(options)`

### 3.2 已删除的文件 / 心智

- `runtime/options.py` 已删除
- 公共门面不再导出旧 runtime API
- live/debug 示例脚本不再示范旧 runtime 写法

---

## 4. 当前唯一推荐主路径

### 4.1 graph

默认只允许：

```python
graph = create_agent(...)
graph = create_deep_agent(...)
graph = builder.compile()
```

### 4.2 运行时解析

统一走：

```python
RuntimeContext
RuntimeOptions
RuntimeRequestMiddleware
resolve_runtime_settings(...)
resolve_model_by_id(...)
```

### 4.3 工具解析

统一走：

```python
build_runtime_tools(...)
abuild_runtime_tools(...)
```

### 4.4 模型切换 / prompt / tools 动态控制

统一由：

- Agent Server `Auth` 生成的 `RuntimeContext`
- `config.configurable.platform_runtime` 生成的 `RuntimeOptions`
- `RuntimeRequestMiddleware`
- `runtime/runtime_request_resolver.py`

处理，不允许 graph 自己再拼一套。

---

## 5. Harness 硬规则

当前 harness 至少要守住下面这些点：

1. `RuntimeContext` 只包含可信身份与项目字段
2. `RuntimeOptions` 只包含模型、prompt、生成参数、工具和多模态模型字段
3. graph 默认静态导出
4. 正式 resolver 只从 `runtime.server_info.user` 读取可信身份
5. 业务运行参数只从 `configurable.platform_runtime` 读取，且禁止身份字段
6. `test_case_service` 不得从 `state/configurable/metadata/system prompt` 推断 `project_id`
7. 公共门面不再导出旧 runtime API
8. `tools/registry.py` 不再接受 `AppRuntimeConfig`
9. live/debug/mainline 代码不再出现旧 runtime 写法

---

## 6. 不再做的事情

以下方向明确不做：

- 不做 compat 层保留
- 不做双轨范式过渡
- 不做旧脚本长期兼容
- 不做旧字段兜底
- 不做“先保留以后再删”

原则只有一句：

> 旧入口不是收容，而是删除。

---

## 7. 当前推荐执行顺序

后续继续收敛时，按这个顺序：

1. 先收死公共业务契约
2. 再删除旧 runtime 入口
3. 再删旧示例 / 旧脚本 / 旧文档引用
4. 最后用 harness tests 把规则钉死

这样仓库里最终只剩现行范式，不再允许“还能凑合跑的旧写法”继续存活。
