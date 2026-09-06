<h1 align="center">企业级 AI Agent 平台</h1>

<p align="center"><strong>面向二次开发与企业落地的 AI Agent 平台底座</strong></p>

<p align="center"><a href="README.en.md">English</a> | 中文</p>

<p align="center">
  <img src="https://img.shields.io/badge/Vue-3%20Workspace-42B883" alt="Vue 3 Workspace" />
  <img src="https://img.shields.io/badge/Testcase-Agent%20Live-2563EB" alt="Testcase Agent Live" />
  <img src="https://img.shields.io/badge/Skills-Private%20Skill%20Stack-0F766E" alt="Skills" />
  <img src="https://img.shields.io/badge/MCP-Knowledge%20Ready-7C3AED" alt="MCP Knowledge Ready" />
  <img src="https://img.shields.io/badge/Harness-AI%20Continuous%20Coding-F59E0B" alt="Harness" />
  <img src="https://img.shields.io/badge/LangGraph-Runtime%20Core-111827" alt="LangGraph Runtime Core" />
  <a href="https://github.com/ljxpython/ai-agent-platform/releases/latest"><img src="https://img.shields.io/github/v/release/ljxpython/ai-agent-platform" alt="Latest Release" /></a>
  <img src="https://img.shields.io/badge/README-EN%2FZH-F59E0B" alt="README EN/ZH" />
</p>

<p align="center"><a href="#system-overview">系统总览</a> · <a href="#frontend-entry">前端入口</a> · <a href="#quick-start">快速开始</a> · <a href="docs/deployment-guide.md">部署文档</a> · <a href="https://github.com/ljxpython/ai-agent-platform/releases/tag/v0.3.1">最新 Release</a> · <a href="docs/CHANGELOG.md">更新日志</a> · <a href="#acknowledgements">致谢参考</a> · <a href="#ai-deploy">AI代理部署</a></p>

## Testcase Agent 展示视频

<p align="center">
  <a href="https://youtu.be/SVplU-uIci0">
    <img src="docs/assets/testcase-agent-demo-preview.jpg" alt="Testcase Agent 展示视频" width="100%" />
  </a>
</p>

<p align="center">
  <strong><a href="https://youtu.be/SVplU-uIci0">▶ 观看当前平台 Testcase Agent 演示视频</a></strong>
</p>

<p align="center"><sub>GitHub README 中采用预览图展示，点击后跳转到 YouTube 播放。</sub></p>

基于 `LangGraph / LangChain` 的企业级 AI 平台架构，可在此基础上进行二次开发。  
它把**平台治理层**和**Agent Runtime 执行层**拆开，既支持平台侧的认证、项目管理、审计、catalog 管理，也支持 Agent 侧的图编排、模型装配、Tools / MCP / Skills 接入与快速调试，适合作为企业内部 AI 平台和智能体应用的基础骨架。

当前仓库默认提供一套正式五服务演示链路，并保留可选 `runtime-web` 调试入口，适合：

- 想基于主流 Agent 技术栈做二次开发的团队
- 想同时建设平台能力和 Agent 执行能力的项目
- 想快速验证 LangGraph Runtime、Agent 行为和前端交互的开发者
- 希望把 AI 协同开发真正纳入工程流程的团队

> 想先理解 AI Harness 和任务分级，可看 [Harness Engineering 简明说明](docs/knowledge/harness-engineering.md)。

当前建议优先把下面几份文档当成正式事实源：

- `docs/local-deployment-contract.yaml`
- `docs/standards/01-ai-execution-system.md`
- `docs/local-dev.md`
- `docs/env-matrix.md`
- `deploy/README.md`
- `docs/runbooks/container-update-runbook.md`

如果你要从零开始使用 Docker / Docker Compose 部署当前项目，优先看：

- `deploy/README.md`
- `docs/zero-to-one-container-deploy.md`
- `docs/runbooks/container-update-runbook.md`

## AI 执行入口

如果你希望后续的人类开发者或 AI 代理都按同一套 Harness Engineering 体系进入任务，建议先按下面顺序阅读：

1. [Root AGENTS Routing Surface](AGENTS.md)
2. [AI 执行系统当前标准](docs/standards/01-ai-execution-system.md)
3. [AI 执行系统使用指南](docs/ai-execution-system-usage-guide.md)
4. [Docs 总入口](docs/README.md)

一句话理解：

- `AGENTS.md`：薄路由与执行门禁
- `docs/standards/`：当前正式标准
- `docs/knowledge/`：背景、理由与设计哲学
- `.harness/`：B1/B2 helper、历史计划和 repo 级报告，不是 canonical truth
- `openspec/`：承载需要持久评审的 B2 和全部 B3 change lifecycle

需要显式判断任务应该走 B1、B2 还是 B3 时，在 Codex 中调用：

```text
$route-project-change <任务描述>
```

这个 Skill 只负责路由，不会绕过 `AGENTS.md`、leaf standard、人工审批或验证门禁。
需要执行持久 B2/B3 流程的设备还应安装 OpenSpec CLI；安装方式、6 个官方 Skills
和完整生命周期见 [AI 执行系统使用指南](docs/ai-execution-system-usage-guide.md#5-openspec-怎么参与)。

<a id="frontend-entry"></a>

## 当前前端与推荐入口

`apps/platform-web` 是当前正式平台前端宿主，也是仓库默认联调和后续平台前端开发的统一入口。

当前正式平台入口已经覆盖首批核心页面：

- `overview`
- `projects`
- `users`
- `assistants`
- `me`
- `security`
- `audit`

当前正式前端相关事实源：

- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-api/docs/README.md`
- `apps/platform-api/docs/handbook/project-handbook.md`
- `apps/platform-api/docs/delivery/change-delivery-checklist.md`

补充说明：上面列出的页面是当前正式前端范围中的核心入口，以 `apps/platform-web/src/router/routes.ts` 为代码事实源。

如果你是第一次跑这个仓库，建议直接按根目录脚本启动并打开 `apps/platform-web`。

## AI 持续编程 Harness

这个仓库不只是“放了一堆代码”，而是已经形成了一套可以指导 AI 代理持续开发、持续联调、持续验收的工程 Harness。

这里说的 Harness，不是单个工具，而是一整套受控的工程外壳：

- `边界`：平台治理、运行时执行、调试前端、结果域服务已经拆层，AI 不需要在一个大泥球里瞎改
- `契约`：本地部署 contract、环境变量矩阵、接口命名、默认启动顺序和账号口径都已固定
- `范式`：`runtime-service`、`platform-web`、控制面页面标准与现成样例页面已经沉淀出可复用范式
- `闭环`：根级脚本、健康检查、烟测清单、验收文档、CHANGELOG 和 release runbook 已形成可执行交付链路

平台控制面后端这部分，当前专用的落地蓝图与正式标准已经统一写入：

- `apps/platform-api/docs/README.md`
- `apps/platform-api/docs/handbook/project-handbook.md`

一句话说，这个仓库已经不是“让 AI 随便写代码”，而是“让 AI 在明确边界、稳定契约和现成范式中持续完成开发”。

## 这个项目解决什么问题

很多 Agent 项目能跑 demo，但一到真实工程场景就容易混乱：平台治理、运行时执行、调试入口、环境配置全耦在一起，后面越改越难受。

这个仓库的目标很明确：

- 用 `LangGraph / LangChain` 主流生态构建企业级 AI 平台架构，不重新发明一套封闭框架
- 把平台层和运行时层解耦，便于分工、演进和交付
- 提供可复用的 Runtime 执行骨架，而不是一次性 demo
- 给后续业务二开和测试场景接入预留空间

## 前端效果展示

如果你想先看当前平台前端已经做到了什么程度、页面大致长什么样，以及前端这部分是怎么组织和展示的，可以直接看这篇记录：

- [平台前端效果展示与介绍](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260325_platform_frontend_intro.md)

这篇内容更偏平台前端视角，适合快速了解当前 `Agent Platform Console` 的页面效果、工作区结构和一些实际展示结果。

![平台前端效果展示](docs/assets/image-20260325161139758.png)

<a id="system-overview"></a>

## 系统总览

当前根目录默认联调脚本会启动 5 个正式应用：

- `apps/interaction-data-service`：结果域数据服务 / 工作流结果落库与查询
- `apps/platform-api`：正式平台后端 / 控制面 API
- `apps/platform-web`：正式平台前端宿主 / 管理台入口
- `apps/runtime-service`：LangGraph 执行层 / Agent Runtime
- `apps/lightrag-service`：仓库内知识服务，同时提供 `platform-api` 侧 LightRAG HTTP 和 `runtime-service` 侧 project-scoped MCP

可选仓库内服务：

- `apps/runtime-web`：直连 Runtime 的调试前端

### 主要链路

- 平台链路：`platform-web -> platform-api -> runtime-service`
- 调试链路：`runtime-web -> runtime-service`
- 结果链路：`runtime-service -> interaction-data-service`
- 知识 HTTP 链路：`platform-api -> lightrag-service`
- 知识 MCP 链路：`runtime-service -> lightrag-service`

### 当前两个前端入口分别做什么

- `platform-web`：当前正式平台工作台入口，承接 `Agent Platform Console`、Agent 页面和平台治理相关前端能力
- `runtime-web`：直连 `runtime-service` 的调试前端，适合做 Agent 调试、交互验证和 Runtime 快速迭代

## 架构图

![系统架构图](docs/assets/system-architecture.zh.svg)

<a id="quick-start"></a>

## 快速开始

### 默认启动顺序

1. `runtime-service`
2. `interaction-data-service`
3. `lightrag-service`
4. `platform-api`
5. `platform-web`
6. 如需 runtime 调试，再启动 `runtime-web`

### 根目录脚本

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

这三个脚本分别对应：

- 启动：`scripts/dev-up.sh`
- 健康检查：`scripts/check-health.sh`
- 停止：`scripts/dev-down.sh`

它们现在统一代理到正式演示脚本：

- `scripts/platform-web-demo-up.sh`
- `scripts/platform-web-demo-health.sh`
- `scripts/platform-web-demo-down.sh`

### 本地 Runtime + Platform 进程模式

如果本机已经运行 PostgreSQL 和 Redis，使用新的本地进程脚本，不会修改或调用上面的旧演示脚本：

```bash
bash "./scripts/local-stack.sh" doctor
bash "./scripts/local-stack.sh" start
bash "./scripts/local-stack.sh" status
bash "./scripts/local-stack.sh" stop
```

该脚本直接启动 GraphHarbor API、GraphHarbor Worker、Platform API、Platform Worker 和 Platform Web；
数据库迁移使用 `migrate` 子命令执行，日志和 PID 文件放在系统临时目录。它不会停止或删除本机
PostgreSQL、Redis，也不会按端口杀掉不属于自己的进程。启动前会检查 `DATABASE_URI` 对应的 PostgreSQL
和 `REDIS_URI`，发现失效 PostgreSQL 锁文件时不会自动删除。Runtime 使用
`apps/runtime-service/.env`，Platform API 使用 `apps/platform-api/.env`。
首次使用时，分别从对应的 `.env.example` 创建本地 `.env`，填入真实模型凭据和本机 PostgreSQL
账号；不要覆盖已有 `.env`，也不要提交真实值。

### Docker / Docker Compose

如果你希望直接用容器方式启动，当前有 3 种常见用法：

1. 只启动 `runtime-service`

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d
```

2. 启动整仓 stack（无 Nginx，前后端分端口）

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d
```

3. 启动整仓 stack（带 Nginx，单入口）

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d
```

建议阅读顺序：

- `deploy/README.md`
- `docs/zero-to-one-container-deploy.md`
- `docs/runbooks/container-update-runbook.md`

### 如果你想单独启动 `platform-web`

根目录默认脚本已经会启动 `apps/platform-web`。

如果你要单独调试平台前端，也可以这样启动：

```bash
VITE_DEV_PORT=3002 pnpm --dir "apps/platform-web" dev
```

然后打开：

- `platform-web`：`http://127.0.0.1:3002`

这样不会和默认的 `platform-web:3000` 端口冲突。

### 默认本地端口

- `interaction-data-service`：`8081`
- `runtime-service`：`8123`
- `lightrag-service` HTTP：`9621`
- `lightrag-service` MCP SSE：`8621`
- `platform-api`：`2142`
- `platform-web`：`3000`
- `runtime-web`：`3001`（可选）

### 成功启动后访问地址

- `platform-web`：`http://127.0.0.1:3000`
- `runtime-web`：`http://127.0.0.1:3001`

### 最小健康检查

```bash
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:9621/health
curl http://127.0.0.1:8621/sse
curl http://127.0.0.1:2142/_system/health
curl http://127.0.0.1:2142/api/langgraph/info
```

如果 `platform-api` 的 `/api/langgraph/info`、`interaction-data-service` 的
`/_service/health` 和 `lightrag-service` 的 `/health` 都返回成功，说明平台、结果落库和
知识 HTTP 主链已经基本打通；MCP SSE 可连接性由统一健康检查脚本继续验证。

![本地联调启动流程图](docs/assets/local-dev-startup-flow.zh.svg)

## 仓库结构

```text
AITestLab/
├── apps/
│   ├── interaction-data-service/
│   ├── lightrag-service/
│   ├── platform-api/
│   ├── platform-web/
│   ├── runtime-service/
│   ├── runtime-web/
│   └── ...
├── .codex/skills/
├── .harness/
├── docs/
├── openspec/
├── scripts/
└── archive/
```

- `apps/`：业务应用目录，包含当前默认联调服务与其他按需维护的应用目录
- `.codex/skills/`：可跨设备复用的项目级 Codex / OpenSpec Skills
- `.harness/`：helper、历史计划和 repo 级验证报告
- `docs/`：部署、开发、约束和背景文档
- `openspec/`：持久 B2/B3 change、已批准 capability specs 和归档
- `scripts/`：统一启动、停止、健康检查脚本
- `archive/`：历史归档说明

<a id="docs-by-goal"></a>

## 按目标阅读文档

![文档导航图](docs/assets/readme-doc-navigation.zh.svg)

### 我想先把环境跑起来

先看：

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/env-matrix.md`

### 我想了解完整部署细节

再看：

- `docs/deployment-guide.md`

### 我想继续开发或二开

重点看：

- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`
- `docs/development-guidelines.md`
- `docs/project-story.md`

### 我想做正式发版

先看：

- `docs/releases/release-policy.md`
- `docs/releases/v0.3.1-agent-workspace-demo-draft.md`
- `docs/releases/v0.3.1-release-runbook.md`
- `docs/releases/`：完整历史发布记录

<a id="ai-deploy"></a>

### 我想让 AI 代理帮我部署

入口文档：

- `docs/ai-deployment-assistant-instruction.md`

如果你只是想触发标准本地部署，这句话就够了：

```text
阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境。
```

如果你已经知道本地要用哪套模型，建议把模型配置也一次性发给代理。这样代理更容易一次把环境配好，而不是启动到一半再回头追问 runtime 模型配置。

更推荐直接发这段（把占位符替换成你自己的真实配置，且只让代理写入本地 `settings.local.yaml`，不要把真实 key 提交回仓库）：

```text
阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境。

默认推理模型使用 `<YOUR_REASONING_MODEL_ID>`。
当前多模态链路需要的模型一并配置为 `<YOUR_MULTIMODAL_MODEL_ID>`。
如果本地缺少 runtime 模型配置，请把下面内容写入 `apps/runtime-service/runtime_service/conf/settings.local.yaml`，并继续完成部署、启动与验证；不要把真实 API Key 提交回仓库。

default:
  default_model_id: <YOUR_REASONING_MODEL_ID>
  models:
    <YOUR_MULTIMODAL_MODEL_ID>:
      alias: <OPTIONAL_MULTIMODAL_ALIAS>
      model_provider: openai
      model: <YOUR_MULTIMODAL_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
    <YOUR_REASONING_MODEL_ID>:
      alias: <OPTIONAL_REASONING_ALIAS>
      model_provider: openai
      model: <YOUR_REASONING_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
```

## 实操参考

如果你希望参考一套更贴近真实开发过程的本地实操记录，详细见：

- [ai-learning-portfolio 仓库](https://github.com/ljxpython/ai-learning-portfolio)
- [my_work_record 索引](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/README.md)

这组记录不是重复贴源码，而是专门补“具体怎么做、怎么验证、怎么复盘”的落地路径，可作为本仓库进行**智能体功能开发**和**平台相关能力开发**的参考。

建议这样理解这组内容：

- 根仓库 `README` 更偏项目地图、系统分层和文档导航
- `ai-learning-portfolio` 里的本地实操记录更偏真实开发过程、验证路径和复盘方法

如果你想按主线看，建议优先关注这些内容：

- [部署与验证基线](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260323_deployment_environment.md)
- [Text-to-SQL 简单能力开发案例](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260312_texttosql_rd.md)
- [多智能体复杂业务开发案例](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260314_requirement_agent_rd.md)

你可以这样理解这 3 篇记录的作用：

- `20260323_deployment_environment.md`：看本地环境怎么准备、怎么启动、怎么验证链路是否打通
- `20260312_texttosql_rd.md`：看一个相对简单的 Text-to-SQL 能力案例是怎么围绕具体场景做设计与实现的
- `20260314_requirement_agent_rd.md`：看多智能体复杂业务场景从需求理解、角色拆分到研发落地是怎么推进的

如果你是第一次接触这个仓库，比较推荐的阅读顺序是：

1. 先看当前仓库的 `README`、`docs/local-deployment-contract.yaml` 和 `docs/local-dev.md`
2. 再看 `ai-learning-portfolio` 中的本地实操记录索引
3. 如果想先从简单案例入手，就看 Text-to-SQL；如果想看复杂业务协作场景，就看多智能体需求研发案例

## 当前状态

当前仓库已经完成：

- 正式默认本地演示链路已收口到 `apps/*`
- `apps/platform-web` 是当前正式平台前端宿主
- `runtime-service` 可启动
- `interaction-data-service` 可启动
- `platform-api` 可启动
- `platform-api -> runtime-service` 联调已通过
- `runtime-service -> interaction-data-service` 已接入本地联调脚本
- `lightrag-service` 的 HTTP + MCP 已接入默认本地一键启动脚本
- `platform-web` 是当前正式平台前端入口，`runtime-web` 继续作为可选调试壳
- `apps/lightrag-service` 当前已进入默认本地一键启动集合，但 Compose 栈仍按需单独接入
- Harness + OpenSpec 已形成路由、B3 实施前审批、持久验证证据、spec sync、archive 和 CI 检查闭环
- 当前正式版本为 [`v0.3.1`](https://github.com/ljxpython/ai-agent-platform/releases/tag/v0.3.1)

当前仍保持的约定：

- 每个应用独立维护自己的环境与依赖
- 根目录不统一维护 `.env`
- 根目录暂不统一 Python / Node 依赖

## 项目方向

这个仓库的长期方向，是把它打磨成一套可复用、可扩展、可继续二开的 AI Agent 平台基础框架。  
当前会优先吸收测试工程相关场景能力，例如：

- AI 智能评审
- AI 驱动的 UI 自动化
- 自动化脚本生成与测试辅助
- AI 性能测试
- Text-to-SQL

更完整的项目背景、演进过程和设计取舍，见：

- `docs/project-story.md`

## 支持与交流

如果这个项目对你有帮助，欢迎 star。  
如果你希望交流测试平台、AI 协同开发、LangGraph / MCP 相关实践，也欢迎联系。

个人微信号：

<img src="docs/assets/image-20250531212549739.png" alt="个人微信号" width="300"/>

## 历史代码

旧版 `AITestLab` 代码已不再保留在当前工作分支。

如需回看旧版代码，请访问：

- [AITestLab-archive](https://github.com/ljxpython/AITestLab-archive)

<a id="acknowledgements"></a>

## 致谢与参考

本项目在持续演进过程中，参考并受益于一些优秀的开源项目与技术生态，尤其包括：

- [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api/tree/main)：在前端视觉组织、后台工作台布局、列表页与系统区交互节奏上给了当前平台工作台设计不少启发
- [FastAPI](https://fastapi.tiangolo.com/)：平台后端与服务接口层的重要基础
- [LangGraph](https://docs.langchain.com/langgraph)：Agent Runtime、状态编排与执行流建模的重要基础
- [FastMCP](https://gofastmcp.com/)：MCP 工具接入与服务化能力的重要参考生态
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)：项目级知识检索与可选仓库内 LightRAG MCP 接入方案的重要参考

这里的“参考”不是简单照搬源码，而是基于这些开源项目和技术生态，结合当前仓库的业务目标、工程边界和平台化需求，做了再组织、再封装和再落地。

## 开源与引用说明

本项目以公开源码方式持续维护，欢迎学习、参考和基于当前仓库继续二次开发。

如果你在公开项目、技术文章、演示材料、培训内容或二次发布中使用了本项目的代码、设计、文档或衍生实现，请明确注明来源仓库与作者信息。

建议至少保留类似说明：

```text
This project is based on or references AITestLab:
https://github.com/ljxpython/AITestLab
```
