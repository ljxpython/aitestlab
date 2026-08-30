# runtime_service 运行时契约待明确项

本文档只记录“还没最终拍板”的问题。

已确认内容以 `04-runtime-contract-v1.md` 为准；这里不再重复已经定下来的边界。

## 1. 统一运行时解析层的最终形态

待明确：

- 公共 runtime 解析层最终放在哪个模块
- 是单 middleware，还是 middleware + resolver helper 的最小组合
- 哪些校验放公共层，哪些校验留给具体 graph / service

当前倾向：

- 以共享 middleware 为主
- 只保留极薄 helper，不再扩成复杂层级

## 2. graph 迁移顺序与样板图

待明确：

- 第一阶段是否只把 `assistant_agent` 收成标准样板
- `research_agent`、`deepagent_agent`、`test_case_service` 的迁移顺序

当前倾向：

1. 先改 `assistant_agent`
2. 再抽公共 runtime middleware / resolver
3. 再迁移 `research_agent`
4. 再迁移 `deepagent_agent` / `test_case_service`

## 3. 工具 catalog 的对外协议

待明确：

- `tools/registry.py` 的 catalog 数据结构如何统一
- `custom_routes/tools.py` 对外暴露哪些字段
- 平台侧拿到的是“可选工具集合”还是“最终生效工具集合”

当前倾向：

- `tools/registry.py` 做唯一真源
- `custom_routes/tools.py` 只做只读暴露

## 4. 公共字段与服务私有字段的边界

待明确：

- `RuntimeContext` 最终固定哪些公共字段
- `test_case_service`、`deepagent` 是否还需要新增私有字段
- 私有字段是继续放 `config.configurable`，还是进一步下沉到服务内部

## 5. 上层联动顺序

待明确：

- `platform-api` 何时切到 `context-first`
- `platform-web-v2` assistant 编辑页何时改成 `context/config` 双区分

## 6. 明确延期项

下面这些不是当前阻塞项，后面再谈：

- `skills` / `subagents` 的公开 contract
- `RuntimeContext.tools` 的细颗粒度白名单治理
- 服务私有 override 的精确白名单
- run override 的权限边界模型
