# 15. 演示环境与走查手册

## 目标

这份文档只做一件事：

- 把 `apps/platform-web-vue` 当前可演示环境、账号、启动方式和推荐演示顺序固定下来

后续老板汇报、产品走查、联调回归都按这份手册执行，不再临时回忆“先点哪个页、账号是多少、服务怎么起”。

## 当前演示基线

截至 `2026-04-05`，当前固定基线如下：

- 前端：`http://127.0.0.1:3173`
- 平台后端：`http://localhost:2142`
- LangGraph 开发服务：`http://localhost:8123`
- 登录方式：用户名密码登录

## 启动方式

### 1. 启动平台后端

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2142 --reload
```

### 2. 启动 LangGraph 开发服务

```bash
uv run langgraph dev --config langgraph.json --port 8123 --no-browser
```

如果是容器环境，需要同步带上：

```bash
export BG_JOB_ISOLATED_LOOPS=true
```

或者在 `langgraph.json` 的 `env` 中固定：

```json
{
  "graphs": {
    "agent": "./graph.py:graph"
  },
  "env": {
    "BG_JOB_ISOLATED_LOOPS": "true"
  }
}
```

### 3. 启动前端

```bash
pnpm --dir "apps/platform-web-vue" dev --host 127.0.0.1 --port 3173
```

## Node 版本约定

- `platform-web-vue` 的 `engines.node` 为 `>=20.17.0 <23`
- 推荐直接使用 Node `20 LTS` 或 `22 LTS`
- 当前机器如果是 Node `25.x`，虽然大部分场景还能跑，但会有 engine warning，不作为正式演示基线

## 固定演示账号

当前默认保证可登录的固定账号为：

- 管理员：`admin / admin123456`

验证方式：

- `POST http://127.0.0.1:2142/api/identity/session`
- `admin / admin123456` 返回 `200`

补充说明：

- 当前正式实现只保证 bootstrap 管理员账号
- 普通用户如果需要纳入演示，请先确认本地数据中确实存在该用户及其密码口径

## 演示前置数据要求

为了保证汇报路径稳定，演示前至少确认下面几点：

- 当前环境里至少有一个可切换项目
- 至少有一个可进入的 assistant / graph
- `chat`、`sql-agent`、`testcase/generate` 可拿当前项目正常进入
- 公告列表能正常返回数据；如果真实接口异常，前端会退回演示替身

如果项目选择器显示“暂无项目”，优先：

1. 在 `/workspace/projects` 新建一个项目
2. 或切换到已有项目后再进入 agent 相关页面

## 推荐演示顺序

汇报优先级继续保持：

1. agent 相关能力最重要
2. 其次是平台基础管理能力

推荐按照下面顺序演示。

### 主线 A：Agent 与复杂工作区

1. `/workspace/overview`
   - 用作总入口，先说明当前项目、最近活动、引导面板已经成型
2. `/workspace/assistants`
   - 展示助手列表、当前项目上下文和详情入口
3. `/workspace/chat`
   - 展示通用对话工作台
   - 重点看线程复用、运行参数抽屉、ToDo / Files / Tool Call / Artifact
4. `/workspace/sql-agent`
   - 展示固定场景 agent 已收敛到同一套 chat 基座
5. `/workspace/testcase/generate`
   - 展示 agent 驱动的用例生成入口
6. `/workspace/testcase/cases`
   - 展示正式用例管理列表
7. `/workspace/testcase/documents`
   - 展示文档管理、在线预览、原始下载
8. `/workspace/threads`
   - 展示线程页已改成“点中后再拉详情”的懒加载模式

### 主线 B：平台基础管理能力

1. `/workspace/projects`
2. `/workspace/projects/:projectId`
3. `/workspace/projects/:projectId/members`
4. `/workspace/users`
5. `/workspace/users/:userId`
6. `/workspace/announcements`
7. `/workspace/audit`
8. `/workspace/resources/playbook`

最后一页 `Resources / Playbook` 不是业务页，而是给团队解释：

- 现在前端开发不再靠“抄一个页面再改”
- 已经有统一母版、组件复用和工程规范

## 现场汇报建议

- 第一句不要先讲 UI 换壳，先讲“原平台页面与链路已经迁到新基座”
- 先演 agent，再演管理后台
- 所有页面都从左侧导航进入，不要现场手敲路由
- 能不改数据就不现场改数据，避免把演示变成联调排障

## 常见排障

### 登录后又跳回登录页

优先检查：

- `2142` 后端是否启动
- 浏览器本地是否残留旧 token
- 当前账号是否还能通过 `/api/identity/session`

### Chat / SQL Agent 没有返回

优先检查：

- `8123` LangGraph 服务是否启动
- `langgraph.json` 是否已带 `BG_JOB_ISOLATED_LOOPS=true`
- `platform-api` 日志里是否有上游 `500`

### 某页能打开但数据为空

优先检查：

- 当前项目上下文是否正确
- 对应管理接口是否返回 `200`
- 是否只是演示数据为空，而不是页面渲染失败
