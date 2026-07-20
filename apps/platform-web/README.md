# Platform Web

`apps/platform-web` 是当前正式平台前端宿主，也是仓库默认的人类工作台入口。

## 跨应用 AI 执行入口

如果这是跨应用需求，或者你希望 AI 先判定这件事该不该落在正式前端，先读：

1. [Root AGENTS Routing Surface](../../AGENTS.md)
2. [AI 执行系统当前标准](../../docs/standards/01-ai-execution-system.md)
3. [AI 执行系统使用指南](../../docs/ai-execution-system-usage-guide.md)

然后再进入 `platform-web` 自己的 leaf standard：

- [Control Plane 页面标准](./docs/control-plane-page-standard.md)
- [前端开发范式手册](./docs/frontend-development-playbook.md)

## 这个 app 在仓库里的角色

它负责：

- 正式平台工作台
- 正式控制面页面
- 平台治理相关前端交互

它不负责：

- 直接替代 `runtime-service` 的运行时调试入口
- 绕过 `platform-api` 直连正式治理链路

## 推荐读路径

1. [Control Plane 页面标准](./docs/control-plane-page-standard.md)
2. [前端开发范式手册](./docs/frontend-development-playbook.md)
3. [当前项目开发范式说明](../../docs/development-paradigm.md)

如果你的问题是：

- 这是什么页面 / 用哪种页面骨架  
  → 优先看前端开发范式手册

- 正式控制面页面在 service/state/permission/audit 上应该怎么做  
  → 优先看 control-plane 页面标准
