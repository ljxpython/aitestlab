# runtime_service Middleware 开发规范（Playbook）

本文定义 `runtime_service/middlewares/` 下的统一开发范式，目标是：

- 中间件目录长期可维护
- LangChain middleware 生命周期使用一致
- 复杂中间件可拆，但不污染根目录

参考基线：

- LangChain 官方自定义 middleware 文档：
  `https://docs.langchain.com/oss/python/langchain/middleware/custom`

## 1. 总原则

- 一个中间件对外只有一个稳定入口。
- 优先用 LangChain 官方 `AgentMiddleware` 生命周期，不自己发明一套拦截协议。
- 只有“横切关注点”才进入 middleware：输入归一化、状态增强、模型调用包装、输出审计。
- 业务流程本身不是 middleware；复杂流程仍应放在 graph / tool / service。
- 公共 runtime 解析层优先收敛成共享 middleware，而不是散落在每个 graph 里各写一套。

## 2. 目录规则

### 2.1 简单中间件

满足以下条件时，使用单文件：

- 总行数预期不超过 `300`
- 职责不超过 `2` 类
- 不需要额外的协议/解析子模块

目录形态：

```text
runtime_service/middlewares/
  auth_guard.py
  step_guard.py
```

### 2.2 复杂中间件

满足任一条件时，升级为子 package：

- 总行数超过 `300`
- 同时包含协议适配、解析、prompt 注入、状态编排等多类职责
- 存在同步/异步双路径
- 需要独立测试/兼容导出

目录形态：

```text
runtime_service/middlewares/
  multimodal/
    __init__.py
    middleware.py
    types.py
    protocol.py
    prompting.py
    parsing.py
```

硬规则：

- 根目录禁止平铺 `xxx_helper.py / xxx_utils.py / xxx_shared.py` 这类“从属文件”。
- 复杂中间件的内部模块必须收进自己的子目录。
- 子 package 内文件数默认控制在 `3-5` 个；再往上拆，先重新审视设计。
- 外部代码只允许从 `runtime_service.middlewares.<name>` 顶层包导入，不要直接依赖内部子模块。

## 3. 包内模块职责

复杂中间件推荐使用以下命名，不要每次重新起名：

- `middleware.py`
  只放 `AgentMiddleware` 子类、生命周期编排、兼容导出拼装。
- `types.py`
  放 `TypedDict`、类型别名、常量、状态 key。
- `protocol.py`
  放消息/content block 归一化、输入识别、状态原材料收集。
- `prompting.py`
  放 system message 注入、模型可见摘要、状态回填文本。
- `parsing.py`
  放外部模型调用、PDF/图片解析、响应解析、fail-soft 处理。

如果中间件没有某类职责，就不要为了“对称”硬拆出空模块。

## 4. LangChain 生命周期使用规则

按官方文档，middleware 可以做节点式前后处理，也可以包裹模型调用。团队统一规则如下：

### 4.1 `before_model`

适用：

- 读取当前 state/messages
- 生成派生 state
- 不做重 I/O 或只做可接受的轻量准备

要求：

- 返回值只放“需要更新的 state 字段”
- 不在这里偷偷改业务语义

### 4.2 `wrap_model_call` / `awrap_model_call`

适用：

- 归一化请求消息
- 重写 `request.messages`
- 调整 `request.system_message`
- 在模型调用前做解析增强

要求：

- 必须使用 `request.override(...)`
- 同步/异步逻辑差异只保留在“调用方式”，业务分支尽量共用 helper

### 4.3 `after_model`

适用：

- 检查模型输出
- 做轻量结果审计或状态补充

不适用：

- 业务主流程分支判断
- 大量结构化转换

### 4.4 执行顺序

按官方文档：

- `before_*` 按声明顺序执行
- `wrap_model_call` 嵌套执行
- `after_*` 逆序执行

因此团队要求：

- 有顺序依赖的 middleware 必须在 graph 中显式排序
- 后置 middleware 不得依赖“前面某个 wrap 一定已经改过某字段”这种脆弱约定，除非写在注释和文档里

### 4.5 统一运行时解析 middleware 约定

后续 `runtime_service` 的共享 runtime 解析层，优先落成公共 middleware。

适合放进这个公共 middleware 的职责：

- 读取 `RuntimeContext`
- 解析模型与运行参数
- 覆盖 `system prompt`
- 根据 `enable_tools/tools` 筛选静态工具集合
- 保留已注册的业务、middleware 和 DeepAgents 内置工具；只筛选 public optional 工具
- 运行时发现工具必须同时通过 `wrap_model_call` 暴露、通过 `wrap_tool_call` / `awrap_tool_call` 绑定真实实现
- 工具调用阶段必须使用相同 `RuntimeContext` 和 allowlist 重新解析并按标准化名称精确匹配；失效或未授权时 fail-closed
- 静态已注册工具优先于同名动态工具；禁止在 middleware 实例、state 或全局变量中缓存跨 run 的动态工具对象
- 对非法 runtime 参数直接报错

不适合放进这个公共 middleware 的职责：

- 业务流程分支
- deepagent 专属 `skills/subagents` 编排
- 某个业务服务私有的核心决策逻辑

要求：

- 模型、prompt、tools 的公共运行时逻辑不要散落到每个 graph 自己手搓
- 修改模型调用请求时，优先通过 `request.override(...)` 和 `request.system_message`
- 需要 graph 明确排序时，在 graph 里直接把 runtime middleware 放在靠前位置

## 5. 状态设计规则

- 每个中间件只能写自己的命名空间字段
- key 统一用稳定字符串常量，不要在代码里散落硬编码
- 复杂中间件必须提供 `state_schema`
- state 中存“事实”和“派生结果”，不存随手拼的临时垃圾

推荐：

```python
MY_MIDDLEWARE_RESULT_KEY = "my_middleware_result"
```

禁止：

- 直接写 `state["result"]`
- 把临时调试字段长期留在 state

## 6. 请求改写规则

- content block 归一化只做一次；禁止同一链路重复 normalize
- 修改 system prompt 时，优先走 `request.system_message`
- 不要伪造额外 `SystemMessage` 塞进普通 `messages`
- 模型可见上下文必须是“摘要/关键要点”，不是把长文原样灌进 prompt

## 7. 失败处理规则

- runtime contract 校验失败必须直接报错，不能静默回退
- 非法 `model_id`、非法 `tools`、非法字段类型直接返回明确错误
- 外部增强链路是否允许 fail-soft，必须按中间件性质区分并写入文档
- 即便允许降级，也不能静默吞错，错误信息必须可观测、可定位
- 对外模型可见内容只给必要错误摘要，不泄漏过长内部细节
- 同一类失败分支统一走共享 helper，不要每个分支各写一套失败对象

## 8. 对外 API 规则

- package 对外 API 只在 `middlewares/<name>/__init__.py` 暴露
- 根 `middlewares/__init__.py` 只暴露业务真正会复用的稳定入口
- 内部 helper 默认为私有；如果只是为了测试导出，必须明确写兼容说明
- 包内部模块允许相对导入；不要为了“全都走顶层包”制造循环依赖

## 8.1 动态导入规则

- 普通执行链路里禁止在函数内部使用 `importlib.import_module(...)` 做运行期动态导入
- 可选依赖统一在模块顶层 `try/except ModuleNotFoundError` 导入，再在函数中判断是否可用
- 真正插件机制例外，但必须在文档明确说明并有测试覆盖

## 9. 测试基线

每个中间件至少覆盖：

1. 纯输入归一化
2. state 写入/清理
3. `wrap_model_call` 改写行为
4. fail-soft 路径
5. sync/async 一致性
6. 兼容导入或 monkey patch 场景（如果存在）

改完后至少执行：

```bash
python -m compileall runtime_service/middlewares
pytest -q runtime_service/tests/test_<middleware>.py
```

## 10. 当前多模态中间件的落地结论

`multimodal` 已超过“简单中间件”规模，因此采用子 package：

- `runtime_service/middlewares/multimodal/`

这不是例外，而是团队后续处理复杂 middleware 的标准形态。

## 11. 禁止事项

- 为一个复杂中间件在 `middlewares/` 根目录平铺多个从属文件
- 在 middleware 里承载业务工作流主逻辑
- 重复实现 sync/async 大段相同分支
- 把测试专用 helper 当成长期公开 API 滥暴露
- 不看官方生命周期约束，自己乱改 request/state
