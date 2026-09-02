## Why

`platform-api` 当前通过 LangGraph SDK 协议适配器访问 Runtime，但现有验证主要使用 mock upstream，尚未证明真实平台 HTTP 请求可以经过鉴权、项目权限和 delegation token 进入 GraphHarbor。现在补齐这条最短真实链路，才能把“上层无感切换”从架构判断变成可重复证据。

## What Changes

- 增加一个显式环境门控的真实 HTTP 集成测试，验证 `platform-api -> runtime gateway -> GraphHarbor`。
- 覆盖 Platform access token、`x-project-id`、项目权限、Runtime delegation JWT、GraphHarbor `/info`、Graph search 和 Thread 创建。
- 测试缺少真实环境时明确跳过，不启动旧 `langgraph dev`，不把 skip 计为通过。
- 记录 GraphHarbor endpoint、版本、命令、结果和未覆盖边界。
- 不修改 GraphHarbor 通用代码，不新增 Platform 灰度、回滚或 route ownership。

## Capabilities

### New Capabilities

- `platform-runtime-graphharbor-compatibility`: 验证 Platform Runtime Gateway 可以通过兼容 Agent Server 协议访问 GraphHarbor，并保持 Platform 的鉴权与项目边界。

### Modified Capabilities

无。现有 Runtime Gateway 对外路径和 Runtime/GraphHarbor 协议不变，本变更只增加真实兼容性证据。

## Impact

- **Owning locus**：`apps/platform-api`，最短链路连接 `apps/runtime-service` 的 GraphHarbor Agent Server。
- **Execution band**：B3 Governed；涉及跨服务认证、项目 scope 和真实外部服务验收。
- **Affected code**：`apps/platform-api/tests/integration/`，必要时补充测试环境说明；不修改生产 Gateway 实现。
- **Required inputs**：运行中的 Platform API、运行中的 GraphHarbor API/Worker、Platform access token、可访问项目 ID 和两端匹配的 delegation secret。
- **Compatibility**：保持 `/api/langgraph/*` 现有平台接口；GraphHarbor 只作为 upstream 实现，不向上层暴露专用 API。
- **Rollback**：测试文件和验证记录可独立移除；不改数据库 schema、Thread/Run 数据或 GraphHarbor。
