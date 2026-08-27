# 参考项目与技术栈

状态：Draft supporting material。

## 1. 结论

新应用定位为独立的 React 工作台：采用 Open SWE 接近的 React 19、TypeScript、
Vite、TanStack 和 LangGraph 客户端组合；采用 DeepSeek Harness 接近的中性高密度
三栏界面、CSS 变量设计令牌和主题切换。不要迁入 DeepSeek Harness 的 Cordis 插件
容器，也不要把 Open SWE 的服务端接口假设带进本项目。

推荐目录为 `apps/agent-web`，前端正式调用链为：

```text
React Agent Web -> platform-api -> runtime-service / LangGraph
```

## 2. 对比结果

| 维度 | DeepSeek Harness | Open SWE | Agent Web 选择 |
| --- | --- | --- | --- |
| 框架 | React 18 | React 19 | React 19 |
| 语言 | TypeScript 6 | TypeScript 5.9 | TypeScript 5.9 或初始化时稳定的兼容版本 |
| 构建 | Vite 6 | Vite 7 | Vite 7 |
| 样式 | CSS Modules + CSS token sheet | Tailwind CSS 4 + CSS variables | Tailwind CSS 4 + 自有 CSS token sheet |
| 路由/查询 | 壳内插件装配 | TanStack Router + Query | TanStack Router + Query |
| AI 流 | 自有插件/服务层 | `@langchain/react` + LangGraph SDK | Durable Run + Protocol v2；`fetch` SSE transport |
| 组件基础 | 自有 primitives/slots | Base UI、CVA、Lucide | Base UI、CVA、Lucide |
| 代码工作台 | 多个 agent UI 包 | Monaco、diff/tree renderer | 首期只保留 Markdown、工具卡片、diff；Monaco 延后 |

## 3. 建议的依赖分层

### 3.1 首期必须依赖

| 类别 | 依赖 | 用途 |
| --- | --- | --- |
| 框架 | `react`、`react-dom`、`typescript`、`vite` | 应用运行与构建 |
| 导航和缓存 | `@tanstack/react-router`、`@tanstack/react-query` | URL 即工作区状态；缓存 thread/Run 快照 |
| AI 契约 | `@langchain/core`、`@langchain/langgraph-sdk`、`@langchain/react` | Protocol v2 DTO、消息类型与受控运行投影；transport 不直接绑定 SDK hook |
| UI | `tailwindcss`、`@base-ui/react`、`class-variance-authority`、`lucide-react` | 可访问的基础控件与一致样式 |
| 内容 | `streamdown` 或已验证的 Markdown renderer、`shiki` | 流式 Markdown、代码高亮 |
| 运行时校验 | `zod` | 浏览器收到的受控 API DTO 校验 |

### 3.2 明确延后

- Monaco、完整文件树、终端与复杂 diff 编辑器：只有 agent 产物查看的真实需求出现后再加。
- 自研状态管理库：TanStack Query + 局部 React state 足够；不要引入第二个全局状态源。
- DeepSeek Harness 的 Cordis、slots、plugin loader 和所有 `@deepseek-ai/dsh-client-*` 包：
  它们服务于可组合 agent harness，不是单一平台工作台的必需复杂度。
- Open SWE 的 Slack、GitHub、Linear、沙箱、PR 自动修复 UI：当前需求是平台内 Agent
  工作台，不是编码 agent 运营后台。

## 4. DeepSeek Harness：借什么，不借什么

### 可以吸收的能力

| 参考位置 | 吸收内容 | Agent Web 的落点 |
| --- | --- | --- |
| `packages/client/ui-theme/src/styles/design-platform.css` | 分层颜色、浅/深色语义 token、sidebar/bubble/input token | 自有 `--aw-*` token；不保留 `--dsw-*` 命名 |
| `packages/client/ui-layout/src/client/AppFrame.tsx` | sidebar / center / details 三栏、窄屏让步、面板常驻 | `WorkspaceFrame`，由 CSS Grid 和局部 state 实现 |
| `packages/client/ui-layout/src/client/columns.ts` | 可读的列宽让步规则 | 定义固定最小内容宽度、可收起 panel，不复制算法 |
| `packages/client/web/src/AppRoot.tsx` | 启动失败不展示半成品 UI | `AppBootGate` 显示可诊断的 loading/error 状态 |
| `packages/client/ui-theme` | 尊重 `prefers-reduced-motion` | 全局 motion token 和无动画降级 |

### 不应直接迁移

- `AppWebEntry`、loader holding、module seed table、Cordis services、slot renderer：它们为
  可插拔 harness 设计，会把单一 app 的复杂度放大数倍。
- DeepSeek 的品牌色、文字、logo 与完整 CSS token 文件：可参考层级和对比度，不能把
  产品识别直接伪装成平台自身。
- 任何未经确认的内部交互、工具名称或 agent 行为。

若复制 MIT 代码的实质片段，必须在所复制文件保留相应版权和 MIT 许可证；默认优先
重写小而明确的布局与 token，而不是 vendoring 整包。

## 5. Open SWE：借什么，不借什么

| 参考位置 | 值得吸收的机制 | Agent Web 的适配要求 |
| --- | --- | --- |
| `ui/src/features/agents/lib/AgentThreadStreamProvider.tsx` | 单一线程流生命周期、标签页回到前台后的 hydrate、完成后失效查询缓存 | Provider 绑定 active thread/run；不能假定 cookie 鉴权 |
| `ui/src/features/agents/lib/streamMessagesToUi.ts` | 把消息、tool call、subagent 投影转为稳定 UI chunk | 只保留本平台实际事件/工具；不能照搬 Open SWE 工具分类表 |
| `ui/src/features/agents/components/AgentThreadView.tsx` | 初次加载、hydrate 失败、运行错误、计划审阅、上下文用量的明确状态 | 对齐新 Run resource，保持在单个工作台页面内 |
| `ui/src/features/agents/components/chat/ToolExecution.tsx` | 工具卡片的运行中/完成/错误表现 | 使用服务端事件 id 更新同一张卡，绝不以文本猜状态 |
| `ui/src/features/agents/lib/queries.ts` | thread 列表和详情的 query key 组织 | Agent Web 定义自己的 key，按 project/thread/run 分层 |

### 不应直接迁移

- Open SWE 使用 cookie 凭证和自己的 `/dashboard/api`；本项目现有平台使用 Bearer 刷新
  逻辑与项目头，因此以 `fetch + ReadableStream` 请求 POST SSE，并在 header 带 Bearer
  token 和 `x-project-id`。
- GitHub PR、Slack、Linear、云 sandbox、桌面 ACP 不是首期范围。
- 把 LangGraph SDK 的实时数组当作 durable Run 的唯一事实：新协议中 Run 查询才是事实源。

## 6. 本项目现有资产必须保留的语义

| 现有位置 | 不可丢失的语义 |
| --- | --- |
| `apps/platform-web/src/services/langgraph/client.ts` | token 刷新、401 处理、`x-project-id`、正式 gateway URL |
| `apps/platform-web/src/modules/chat/composables/usePlatformChatStream.ts` | active thread 防串写、取消、interrupt、持久 history 与 live state 合并 |
| `apps/platform-web/src/modules/chat/components/BaseChatTemplate.vue` | 草稿隔离、自动跟随不抢阅读位置、空/加载/错误/中断状态 |
| `apps/platform-api/app/modules/runtime_gateway/` | 项目 scope、role、delegation credential、runtime target/options policy |

组件代码不能跨 Vue/React 直接复用；需要迁移的是这些行为、契约和验收场景。

## 7. 技术决策

1. React 19 + TypeScript + Vite 7 作为新应用基础。
2. TanStack Router 的 URL 表示 project、thread、run 和 panel 状态；TanStack Query 只缓存
   服务端 snapshot。
3. CSS token 是唯一视觉事实源，Tailwind 只消费 token；禁止页面手写散落色值。
4. Run resource 和事件流由一个受控 transport 管理；组件不能自行创建 stream。
5. `runtime-web` 继续是内部调试壳，不被 Agent Web 替代或引用为生产能力。
6. Durable Run 是事实与恢复模型，Protocol v2 `run.start`/`input.respond` 和 event stream
   是其正式远程交互协议；不为 Agent Web 保留 legacy `runs.stream` fallback。
