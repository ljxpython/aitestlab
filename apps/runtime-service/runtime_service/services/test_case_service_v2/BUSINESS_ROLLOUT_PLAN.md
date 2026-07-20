# testcase_v2 业务开发规划

文档类型：`Execution Plan`

## 背景

`test_case_service_v2` 的服务内核已经独立完成，并完成了 LightRAG project-scoped MCP 迁移与验证。

当前真正缺少的不是 agent 内部能力，而是业务入口：

- `runtime-service` 仍只注册 `test_case_agent -> v1`
- `platform-web` 的 testcase 页面仍固定绑定 `test_case_agent`
- testcase 结果查询链路已经是项目级结果域，可直接复用

因此，本阶段的目标不是继续改 `v2` agent 内部，而是把它作为一条独立业务线接入到前后端。

## 已确认决策

- 新 graph id：`test_case_agent_v2`
- 新前端业务页组：`/workspace/testcase-v2/*`
- `testcase_v2` 前端页面直接复制现有 testcase 页面能力，不做兼容切换
- testcase 结果域继续混用现有接口，不做 `v1/v2` 分流
- 不改现有 `test_case_agent`、`/workspace/testcase/*` 入口
- 不做灰度、兼容、迁移开关

## 范围

### in scope

- `runtime-service`
  - 注册 `test_case_agent_v2`
  - 补 `v2` graph 的注册/静态 contract 测试
- `platform-web`
  - 新增 `/workspace/testcase-v2/generate`
  - 新增 `/workspace/testcase-v2/cases`
  - 新增 `/workspace/testcase-v2/documents`
  - 新增对应导航组件与侧边栏入口
  - `generate` 页面固定绑定 `test_case_agent_v2`
  - `cases/documents` 继续复用现有 testcase 结果域接口
- 端到端验证
  - `testcase-v2` 页面可真实发起生成
  - 生成结果可在 `testcase-v2` 的 cases/documents 页面查看

### out of scope

- 替换现有 `test_case_agent`
- 兼容旧 testcase 页面切换到 `v2`
- testcase 结果域按 `v1/v2` 做隔离或分库
- 调整 interaction-data-service API path
- 重写 `platform-api` testcase 结果域

## 代码依据

- 当前 `runtime-service` 只注册了 `test_case_agent`
  - [langgraph.json](../../langgraph.json#L36)
- 当前 testcase 生成页固定绑定 `test_case_agent`
  - [TestcaseGeneratePage.vue](../../../../platform-web/src/modules/testcase/pages/TestcaseGeneratePage.vue#L25)
  - [TestcaseGeneratePage.vue](../../../../platform-web/src/modules/testcase/pages/TestcaseGeneratePage.vue#L100)
- 当前 testcase 路由组是成套组织的，适合直接复制一份给 `v2`
  - [routes.ts](../../../../platform-web/src/router/routes.ts#L345)
- 当前 testcase 工作区导航可直接复制
  - [TestcaseWorkspaceNav.vue](../../../../platform-web/src/components/platform/TestcaseWorkspaceNav.vue)
- 当前侧边栏已有 testcase 独立入口，可照此新增 `testcase-v2`
  - [AppSidebar.vue](../../../../platform-web/src/components/layout/AppSidebar.vue#L106)
- testcase 结果查询是项目级结果域，不依赖 graph id
  - [http.py](../../../../platform-api/app/modules/testcase/presentation/http.py)

## 方案

### 1. runtime-service 暴露 v2 graph

- 在 `runtime_service/langgraph.json` 新增：
  - graph id: `test_case_agent_v2`
  - path: `./runtime_service/services/test_case_service_v2/graph.py:graph`
  - description: 明确是 `v2` testcase 生成服务
- 补与 graph 注册相关的测试：
  - graph description 测试
  - 静态 graph contract 测试
  - `v2` graph 的模块级测试

### 2. platform-web 新增 testcase-v2 页面组

- 新增路由组：
  - `/workspace/testcase-v2`
  - `/workspace/testcase-v2/generate`
  - `/workspace/testcase-v2/cases`
  - `/workspace/testcase-v2/documents`
- 新增页面：
  - `TestcaseV2GeneratePage.vue`
  - `TestcaseV2CasesPage.vue`
  - `TestcaseV2DocumentsPage.vue`
- 新增导航：
  - `TestcaseV2WorkspaceNav.vue`
- 侧边栏新增独立入口：
  - label 建议：`Testcase V2`

### 3. 前端页面策略

- `generate` 页：
  - 固定 graph id 为 `test_case_agent_v2`
  - 最近聊天目标缓存也写 `test_case_agent_v2`
  - 标题、说明、context notice 全部改成 `Testcase Agent V2`
- `cases` / `documents` 页：
  - 先直接复制现有 testcase 页面
  - 服务调用继续使用现有 testcase 结果域 API
  - 不按 `agent_key` 做过滤

### 4. 结果域策略

- documents / cases / batches / overview 沿用现有项目级 testcase 结果域
- `v1/v2` 生成的结果允许混合展示
- 页面职责是“`v2` 入口生成 + 查看项目当前 testcase 结果”，而不是“只看 `v2` 结果”

## 风险

- 风险 1：前端页面复制后命名、文案、graphId 有遗漏，导致仍误打到 `test_case_agent`
  - 缓解：对 `generate` 页和最近聊天目标写入做定点测试/静态检查
- 风险 2：`v2` 页面复用结果域后，用户可能看到 `v1` 历史数据
  - 缓解：这属于已确认产品决策，页面文案中不承诺“仅显示 v2 结果”
- 风险 3：`runtime-service` 虽然已有 `v2` graph，但未注册到 `langgraph.json`，导致前端无法使用
  - 缓解：把注册和注册测试放在第一步

## 验收标准

- `runtime-service/langgraph.json` 中存在 `test_case_agent_v2`
- `platform-web` 中存在 `/workspace/testcase-v2/generate`、`/cases`、`/documents`
- `testcase-v2/generate` 固定发往 `test_case_agent_v2`
- `testcase-v2/cases` 与 `testcase-v2/documents` 能正常读取项目级 testcase 结果
- runtime-service 相关测试通过
- platform-web 的 build/lint/相关测试通过
- 至少完成一次真实 `testcase-v2` 生成验证

## 实施清单

### A. runtime-service

- [x] 在 `runtime_service/langgraph.json` 注册 `test_case_agent_v2`
- [x] 为 `test_case_agent_v2` 补 description
- [x] 补 `v2` graph 的静态 graph contract 测试
- [x] 补 `v2` graph 注册/描述测试

### B. platform-web 路由与入口

- [x] 新增 `/workspace/testcase-v2` 路由组
- [x] 新增 `/workspace/testcase-v2/generate`
- [x] 新增 `/workspace/testcase-v2/cases`
- [x] 新增 `/workspace/testcase-v2/documents`
- [x] 在侧边栏新增 `testcase-v2` 入口

### C. platform-web 页面复制

- [x] 复制 `TestcaseGeneratePage.vue` 为 `TestcaseV2GeneratePage.vue`
- [x] 复制 `TestcaseCasesPage.vue` 为 `TestcaseV2CasesPage.vue`
- [x] 复制 `TestcaseDocumentsPage.vue` 为 `TestcaseV2DocumentsPage.vue`
- [x] 新增 `TestcaseV2WorkspaceNav.vue`
- [x] 将 `generate` 页固定绑定到 `test_case_agent_v2`
- [x] 更新页面标题、说明、context notice、recent chat target 文案为 `v2`

### D. 验证

- [x] 跑 `runtime-service` 相关测试
- [x] 跑 `platform-web` build
- [x] 跑 `platform-web` lint
- [x] 做一次真实 `testcase-v2/generate` 生成验证
- [x] 验证 `testcase-v2/cases` 能看到项目结果
- [x] 验证 `testcase-v2/documents` 能看到项目结果

## 执行顺序

1. 先做 `runtime-service` graph 注册与测试
2. 再做前端路由与入口
3. 再复制三页并固定 `v2` graph
4. 最后做端到端验证
