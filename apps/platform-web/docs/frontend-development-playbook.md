# Platform Web Frontend Development Playbook

- 文档类型：Current Leaf Standard
- Owning locus：`apps/platform-web`

本文定义页面 archetype、UI composition 和复用边界。正式控制面页面的
service/state/permission/audit 规则仍由 `control-plane-page-standard.md` 管理。

## 1. Source Of Truth

- 功能、路由和当前实现：`apps/platform-web`
- 视觉与交互基线：当前 `apps/platform-web` 壳层和共享组件
- `platform-web-sub2api-base`：仅作历史参考，不是开发宿主
- Chat 的 live messages/tools/interrupt/loading/error/lifecycle 由官方 SDK controller 维护；线程
  列表、历史快照和当前流订阅分离，页面不得再建立第二套运行状态机。

## 2. 先选页面 Archetype

新增页面先归类：

1. list
2. detail
3. create/edit
4. workspace
5. resource/help

优先复用同类当前页面和共享组件，不为单页建立新的布局体系。

## 3. 页面基本结构

### List

`PageHeader -> optional summary/filter -> DataTable -> PaginationBar`

搜索、空态、分页、排序和批量操作优先复用现有组件。

### Detail

`PageHeader -> summary -> grouped content -> related resources/activity`

先展示上下文和摘要，不把所有字段堆成一张长表单。

### Create/Edit

`PageHeader -> grouped form -> validation/error summary -> actions`

字段、默认值和失败语义必须来自 leaf contract，不在页面里自行发明。

### Workspace

`context/navigation -> primary work area -> optional inspector`

工作区保持主任务突出，调试信息不能变成正式用户主界面。

## 4. Reuse Rules

- 使用现有 shell、tokens、forms、tables、feedback 和 navigation primitives
- 新抽象至少要解决两个真实调用点
- 业务语义留在 module 内，共享组件只承载稳定 UI 行为
- 不整页复制历史参考应用

## 5. Verification

按改动范围选择：

- B1：目标页面 lint/typecheck/build 或最小交互证明
- B2：本地验证后，再验证 `platform-web -> platform-api` 最短链
- B3：公开管理行为、权限或契约变更按 OpenSpec change 验证

页面完成必须同时满足响应式布局、错误态、空态、加载态和基本可访问性。
