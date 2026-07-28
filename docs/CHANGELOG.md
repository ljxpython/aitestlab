# Changelog

本项目的变更日志遵循 `docs/commit-and-changelog-guidelines.md` 的规范，并采用 Keep a Changelog 的结构。

## [Unreleased]

> 当前默认归档到下一版本：`v0.4.1`
>
> 维护规则：
>
> - 新的 `feat / fix / perf` 先补到下面对应分组
> - 发版前再从这里提炼成正式版本条目
> - 已经正式进入某个版本的内容，要从这里移走，别堆成一坨

### Added

- 待补充：新增能力、新页面、新入口、新模板

### Changed

- 待补充：交互收敛、视觉统一、工程化优化、性能改进

### Fixed

- 待补充：缺陷修复、兼容性问题、联调问题、回归问题

## [v0.4.0] - 2026-07-28

### Added

- 新增正式聊天 v2 运行链路、独立调试工作台和运行级模型、工具、提示词配置入口
- 新增服务端生成的可信身份与项目上下文契约，并将其传递到运行时请求解析链路
- 新增运行时委派、平台认证、聊天状态映射和调试接口的覆盖测试

### Changed

- 将正式聊天收敛到 LangChain 流式运行时状态，统一线程续接、消息展示、工具调用和中断交互
- 将运行时模型、工具和 prompt 配置迁移到受管服务端契约，减少前端手工推导与隐式上下文注入
- 升级前端聊天相关依赖，并将调试能力从正式聊天页面拆分为独立工作台

### Fixed

- 修复运行时委派未配置时聊天请求失败的问题，提供兼容的受管委派路径
- 修复发送消息后页面短暂闪烁以及线程目标恢复、搜索参数和工具结果展示的回归问题

## [v0.3.1] - 2026-07-20

### Added

- 新增 repo-local `lightrag-service`，提供 HTTP 与项目级 MCP 知识链路，并接入默认本地启动、健康检查和停止脚本
- 新增 OpenSpec 项目配置、官方 Codex Skills 与显式 `route-project-change` Skill，为持久 B2/B3 变更提供 proposal、spec、tasks、verification、sync 和 archive 生命周期
- 新增跨平台文档与变更状态检查器，并在 CI 中执行 OpenSpec strict validation 和 Harness 闭环门禁

### Changed

- 将活动 Harness helper host 从 `.omx` 迁移到 `.harness`，保留 `.omx` 作为历史和过渡面
- 收敛 B1/B2/B3 路由、B3 实施前审批、持久验证证据、accepted spec sync 和 archive 规则
- 更新本地 demo 依赖顺序、当前文档入口、前端 leaf playbook 和 Harness 人类使用指南

### Fixed

- 修复本地 demo 启动时知识服务与依赖项未完整拉起的问题
- 修复活动计划、OpenSpec change 和验证证据可能形成重复真相源或绕过完成门禁的问题
- 修复 Graphify、CodeGraph 和本机数据库等生成物可能误入版本控制的问题

## [v0.3.0] - 2026-04-23

### Added

- 新增 `v0.3.0` 发版草案与执行清单，固定“平台正式宿主命名收口版”的发布口径

### Changed

- 将当前正式平台宿主从 `platform-api-v2` / `platform-web-vue` 收口为 `platform-api` / `platform-web`
- 将仓库级 current-standard、默认本地部署 contract、CI、Docker Compose、Nginx upstream、helper scripts 与当前 README/leaf docs 统一到新的正式名称
- 将 `apps/platform-api-v2` / `apps/platform-web-vue` 目录整体迁移到 `apps/platform-api` / `apps/platform-web`，并同步更新前后端 env 前缀、包名、构建路径与当前主链说明
- 将 runtime / interaction-data / runtime-web 等当前文档中的正式链路说明改为 `platform-web -> platform-api -> runtime-service`

### Fixed

- 修复活动面里仍残留旧正式宿主命名导致的 CI、脚本、文档与当前标准口径不一致问题
- 修复本地 demo 脚本、Docker stack 与前端环境变量在新正式命名下的路径/服务名对齐问题
- 修复当前主链文档仍把 `platform-api-v2` / `platform-web-vue` 视作正式宿主的漂移

## [v0.2.0] - 2026-04-22

### Added

- 新增 `apps/runtime-service` 单应用容器化交付面，补齐受管 `Dockerfile`、`docker-compose.runtime-service.yml` 与 deploy 级 env 示例
- 新增整仓 Docker Compose 交付面，覆盖无 Nginx / 带 Nginx 两种部署拓扑、共享 Postgres 初始化脚本与容器地址填写指南
- 新增容器化从零部署指南、容器更新 runbook 与 deploy 总入口文档，形成 operator 视角的 bring-up / recreate / rollback 路径
- 新增 `platform-web-vue` 针对 no-nginx 场景的 API base 回归测试，锁定显式 `localhost:2142` 不再被错误改写为同源 `/api`

### Changed

- 将根目录 README、docs 总入口和部署文档收敛到 Docker 使用路径，补充单应用 runtime、整仓 compose 无 Nginx、整仓 compose 带 Nginx 3 种启动命令
- 将容器化基线中的共享多模态附件解析模型默认值收敛为 `MULTIMODAL_PARSER_MODEL_ID=gpt_5.4-ccr`
- 让 `runtime-service` 的 `test_case_service_v2` 支持从 env fallback 读取私有 knowledge MCP 参数与远端持久化目标配置
- 对 `interaction-data-service`、`platform-web-vue`、`runtime-service` 的 Docker build 上下文做瘦身，补齐 `.dockerignore` 与生产容器入口配置
- 将 `interaction-data-service` 容器的健康检查从 `curl` 改成 Python 内建探活，移除镜像里仅为 healthcheck 引入的系统包依赖

### Fixed

- 修复 no-nginx 容器前端在浏览器端把显式 `http://localhost:2142` 又改写回同源 `/api`，导致登录命中 `3000/api/identity/session` 返回 `404`
- 修复本地 `localhost:3000` 与 `127.0.0.1:3000` 访问口径不一致引发的 CORS 预检失败问题
- 修复 `platform-api-v2-worker` 未同步主服务 upstream 配置，导致 `runtime.models.refresh`、`runtime.tools.refresh` 等异步 operation 在 worker 中报 `LangGraph upstream is unavailable`
- 修复 `runtime-service` 容器未注入 `INTERACTION_DATA_SERVICE_URL`，导致 `test_case_service_v2` 的 `persist_test_case_results` 返回 `skipped_remote_not_configured`
- 修复 `platform-api-v2` 的 operation 统计在 PostgreSQL 下仍使用 SQLite `julianday()` 语法的问题

## [v0.1.2] - 2026-04-21

### Added

- 新增项目级知识工作区主线，补齐 `documents / retrieval / graph / settings` 页面、上传对话框与查询设置能力
- 新增 `platform-api-v2` 项目知识控制面链路，承接项目知识路由、权限、上游代理与相关集成测试
- 新增 `runtime-service` 的 `test_case_service_v2` graph、知识查询守卫、文档持久化与相关技能文档
- 新增仓库级 AI 执行系统 current-standard、使用指南、leaf resolver 与 `.omx/specs` helper artifacts

### Changed

- 收紧 `chat` / `sql-agent` / `testcase` 工作区布局，让目标上下文、输入区、消息区和 compact / focus 模式更聚焦主会话
- 将知识工作区重新对齐到共享前端壳、列表页范式和 metadata-aware 检索路径，减少页面结构漂移与滚动裁切
- 更新 README、部署/开发文档与知识设计文档，统一 AI 任务路由、发布入口和项目知识主线叙事
- 让共享多模态解析默认值支持环境配置，同时保留显式覆盖与运行时覆盖路径

### Fixed

- 修复 testcase 文档详情面板在旧数据形态下无法正常预览与原始下载的问题
- 修复项目知识设置页尾部斜杠请求导致的代理跳转与鉴权丢失问题
- 修复 compact / focus 模式下 chat 全局状态条、跟随滚动与局部布局噪音问题
- 修复若干知识页面滚动裁切、工作区内容溢出与上传元数据校验体验问题

## [v0.1.1] - 2026-04-11

### Added

- 新增 `platform-api-v2` 控制面主线，补齐 runtime gateway、用户平台角色、testcase 管理与多类治理模块
- 新增 `runtime-service` 静态 graph 标准化骨架与 harness 开发范式说明，统一 assistant / deepagent / testcase 等运行时主线
- 新增 `platform-web-vue` 的系统治理、工作区导航、chat / sql-agent / testcase / threads 等演示主线路径补强

### Changed

- 统一 `platform-web-vue` 的品牌口径、侧边栏分组、顶栏下拉层、项目上下文与运行时目录刷新体验
- 将旧 `platform-api` / `platform-web` 主线收口到归档或兼容语境，正式入口切换为 `platform-api-v2` 与 `platform-web-vue`
- 重写根级文档、app docs 与正式架构图，使仓库叙事统一到 `AI Harness` 总哲学与当前正式链路

### Fixed

- 修复 chat 场景中的流式运行时契约对齐问题，稳定会话续接、工具结果展示与阅读跟随体验
- 修复 `platform-web-vue` 中的会话过期跳转、图表工具结果渲染与若干工作区交互收口问题
- 修复文档中仍把历史控制面 / 历史前端宿主当成当前默认实现的漂移问题

## [v0.1.0] - 2026-04-05

### Added

- 新增 `apps/platform-web-vue` 作为新的前端工作台宿主，承接迁移后的正式工作区布局与页面主线
- 新增 `chat / sql-agent / testcase / threads` 主线可演示能力，覆盖 agent 工作台、线程懒加载与文档链路
- 新增 `Resources / Playbook` 作为前端开发范式、页面母版与模板资源沉淀入口
- 新增演示环境、烟测、验收与汇报相关文档，固定 `Agent 工作台可演示版` 发版口径

### Changed

- 统一顶栏系统区交互，包括项目切换、语言切换、公告中心与用户菜单
- 统一列表页母版能力，包括 `DataTable / Pagination / 列设置 / 筛选设置 / ActionMenu / BulkActionsBar`
- 统一 `chat` 与 `sql-agent` 的执行态工作台、消息级操作、上下文抽屉与执行面板交互
- 对 dark mode、移动端与大屏布局做了专项收敛，修正关键页面占满、溢出与视觉一致性问题

### Fixed

- 修复线程页一次性展开所有 thread 内容导致的性能与可读性问题
- 修复 testcase 文档在线预览与原始下载主链路
- 修复 chat 中 retry / edit 后的分支挂载、默认最新分支与历史交互问题
- 修复多处顶栏、下拉、分页、筛选器与 tooltip 的交互一致性问题
