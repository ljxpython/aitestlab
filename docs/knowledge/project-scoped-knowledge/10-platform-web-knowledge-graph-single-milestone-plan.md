# platform-web 知识图谱单阶段实施计划

## 1. 文档目的

本文是当前知识图谱工作的**唯一有效实施方案**。

它取代此前偏“只读重构 / 分阶段收口”的方案文档，将目标统一收敛为：

> 在一个单独里程碑内，完成 `platform-web` 知识图谱页对 LightRAG 图谱工作区的高保真对齐，并同时完成图谱 mutation 流程、环境修通与浏览器实机验收。

---

## 2. Supersedes

本计划明确取代以下旧文档中的旧边界：

- `.omx/plans/prd-knowledge-graph-redesign-20260413.md`
- `.omx/plans/test-spec-knowledge-graph-redesign-20260413.md`
- `docs/knowledge/project-scoped-knowledge/09-platform-web-knowledge-graph-redesign-plan.md`

旧文档仍可保留作历史材料，但不再作为当前执行依据。

---

## 3. 单阶段目标

当前阶段必须一次性完成以下四块内容：

1. **LightRAG 风格高保真图谱工作区**
   - graph-first 页面结构
   - labels / search / toolbar / legend / properties 的层级对齐
   - 更接近 LightRAG 的交互读感与视觉表达

2. **图谱 mutation 流程**
   - entity edit
   - relation edit
   - delete entity
   - delete relation
   - entity exists check
   - expand
   - prune
   - rename collision guidance

3. **本地环境稳定化**
   - 通过现有 demo up/down 脚本稳定启动
   - 排查并修复阻塞浏览器验收的 `/api/identity/session` 500
   - 能在本地真实打开并进入图谱页

4. **浏览器实机验收**
   - 不只依赖 typecheck/build
   - 必须用真实浏览器对照运行中的 LightRAG 参考界面做走查

---

## 4. 核心原则

### 原则 A：Parity over partial polish

这次目标不是“让图谱页更好一点”，而是把它拉到 **LightRAG-style parity** 的层级。

### 原则 B：Graph-first workspace

中间图谱画布是主角，labels、search、legend、settings、properties 都是附着在图谱周围的工作区工具。

### 原则 C：单阶段完成，不再拆成 UI-only / mutation-only

用户已经明确选择：**A+B 一起做，且作为一个阶段结束条件**。

### 原则 D：验证是交付内容的一部分

环境修通和浏览器走查不是附带项，而是完成标准本身。

### 原则 E：保持平台边界真实

- 前端继续走 `platform-api`
- 不直接移植 React 实现
- 不伪造后端没有的 merge 语义

---

## 5. 当前已知事实

### 5.1 已有前端基础

当前 `platform-web` 已经具备以下基础：

- Sigma/graphology 图谱画布
- 图谱页布局已开始向 LightRAG 靠拢
- 基础 graph toolbar / legend / inspector / search / labels 组件
- 图谱页部分 mutation 流程已经打通

主要路径：

- `apps/platform-web/src/modules/knowledge/pages/KnowledgeGraphPage.vue`
- `apps/platform-web/src/modules/knowledge/components/graph/*`
- `apps/platform-web/src/modules/knowledge/composables/*`
- `apps/platform-web/src/modules/knowledge/stores/knowledgeGraph.ts`
- `apps/platform-web/src/modules/knowledge/utils/*`

### 5.2 已有平台 API 基础

当前 `platform-api` 已经具备 project-scoped graph 支撑能力：

- `graph/label/list`
- `graph/label/popular`
- `graph/label/search`
- `graphs`
- `graph/entity/exists`
- `graph/entity/edit`
- `graph/relation/edit`
- `graph/entity`
- `graph/relation`

主要路径：

- `apps/platform-api/app/modules/project_knowledge/application/contracts.py`
- `apps/platform-api/app/modules/project_knowledge/application/service.py`
- `apps/platform-api/app/modules/project_knowledge/presentation/http.py`

### 5.3 当前最大 blocker

浏览器走查仍被本地环境问题阻塞：

- 登录页发起 `/api/identity/session`
- 返回 `500`
- 导致图谱页无法进入浏览器真实验收流程

所以环境稳定化必须纳入本阶段主计划。

---

## 6. Parity Contract

## 6.1 Layout parity

页面需要对齐到以下结构：

- 左上：轻量 `GraphLabels`
- 右上：轻量 `GraphSearch`
- 左下：分组 toolbar
- 右侧：details / properties panel
- 右下：legend
- 中间：graph-first canvas

## 6.2 Interaction parity

必须对齐这些行为：

- node click / edge click 选择
- search-select 聚焦
- zoom / fit / fullscreen / rotate / focus
- graph 不得出现点击后消失或镜头异常飞走

## 6.3 Mutation parity

当前阶段内必须支持：

- entity edit
- relation edit
- delete entity / relation
- entity exists check
- expand
- prune
- rename collision guidance

说明：

- merge 语义必须忠于当前平台 API 能力
- 如果后端只支持 rename collision guidance，就不能在 UI 上冒充完整 merge 系统

## 6.4 Visual parity

必须接近 LightRAG 的读感：

- 节点颜色按 type 稳定映射
- legend 与颜色一致
- label 显示密度合理
- 边默认克制、聚焦时强调
- 侧栏浮层不抢图谱主舞台

---

## 7. 单阶段硬门禁

必须按 Gate 顺序推进。

### Gate 1：Environment Gate

- `./scripts/platform-web-demo-down.sh` 可稳定停服务
- `./scripts/platform-web-demo-up.sh` 可稳定起服务
- LightRAG 参考服务可启动
- 本地登录/session 问题修通或有效绕过

### Gate 2：Parity Shell Gate

- graph-first layout 成立
- labels/search/toolbar/properties/legend 结构到位
- 图谱基础交互稳定

### Gate 3：Mutation / State Gate

- entity / relation 编辑可用
- delete entity / relation 可用
- expand / prune 行为可用
- graph/store/panel 状态不乱

### Gate 4：Browser Acceptance Gate

- 能进入真实图谱页
- 对照运行中的 LightRAG 做浏览器走查
- 通过 repo-owned checklist

---

## 8. 实施步骤

### Step 1 — Rebaseline current planning artifacts

目标：

- 把旧的 read-only-heavy 文档标为 superseded
- 用当前单阶段目标统一执行口径

产出：

- 新 PRD
- 新 test-spec
- 新 canonical implementation plan

### Step 2 — Close remaining frontend parity gaps

重点路径：

- `apps/platform-web/src/modules/knowledge/pages/KnowledgeGraphPage.vue`
- `apps/platform-web/src/modules/knowledge/components/graph/*`
- `apps/platform-web/src/modules/knowledge/composables/*`
- `apps/platform-web/src/modules/knowledge/stores/knowledgeGraph.ts`
- `apps/platform-web/src/modules/knowledge/utils/*`

重点任务：

- labels / search 交互改成更轻量、更接近 LightRAG
- toolbar 分组完全收口
- properties 面板更接近 LightRAG 结构
- legend / fullscreen / focus / rotate / zoom 细节对齐
- 节点颜色、边样式、标签密度调优

### Step 3 — Finish mutation flows and UI reconciliation

重点任务：

- entity edit
- relation edit
- delete entity / relation
- entity exists check
- rename collision guidance
- expand / prune
- mutation 后的 graph/store/panel 一致性修复

### Step 4 — Tighten project-scoped backend contract

重点任务：

- 确认 request/response shape 满足前端 mutation 需要
- 保持 read / write 图谱接口契约一致
- 保持 project-scoped control-plane 边界

### Step 5 — Stabilize local environment

重点任务：

- 修通 `platform-web-demo-up/down`
- 修通登录/session 链路
- 形成最小本地 runbook

### Step 6 — Real browser acceptance

重点任务：

- 打开本地图谱页
- 对照运行中的 LightRAG 参考页
- 执行 checklist
- 修最后一轮 parity gap

---

## 9. 风险与缓解

### 风险 1：环境问题一直阻塞验收

缓解：

- 把环境稳定化提前到 Gate 1
- 不允许跳过浏览器验收直接宣称完成

### 风险 2：前端状态继续处于过渡态

缓解：

- 审核 selection / focus / search / mutation / camera 的边界
- 不让 reducer 隐藏逻辑承担 mutation truth

### 风险 3：页面越来越像“仿制品”而不是 parity

缓解：

- 所有视觉与交互对齐都以 LightRAG 行为为参考
- 不是内部主观审美

### 风险 4：merge 语义与平台真实能力不一致

缓解：

- 明确 UI 只表达当前 API truth
- 不做夸大承诺

---

## 10. 验收资料

本阶段验收依赖两套材料：

1. **LightRAG reference verifier**
   - external LightRAG checkout（本地路径不纳入仓库文档）
   - `source .venv/bin/activate`
   - `lightrag-server`

2. **Repo-owned acceptance checklist**
   - `docs/knowledge/project-scoped-knowledge/11-platform-web-knowledge-graph-acceptance-checklist.md`

---

## 11. 结论

当前知识图谱工作已经不适合继续沿用旧的“只读优先、后续再补 mutation / 验收”的口径。

从现在开始，唯一正确的执行目标是：

> 在一个阶段内完成 LightRAG-style graph parity + mutation flows + environment stabilization + browser acceptance。
