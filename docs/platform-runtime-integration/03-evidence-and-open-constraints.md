# Platform Runtime Integration 证据与开放约束

- 文档类型：Draft Supporting Evidence Register
- 状态：`L1 partial; L2 local-complete; L3 partial; production governance out-of-scope`
- 证据真源：[`verification.md`](../../openspec/changes/redesign-platform-runtime-integration/verification.md)
- 更新时间：2026-09-04

## 1. 当前已执行证据

| 检查 | 输入 | 结果 | 说明 |
| --- | --- | --- | --- |
| OpenSpec strict validation | `redesign-platform-runtime-integration` | 通过 | planning artifacts 合法；不证明实现完成 |
| Documentation checks | `uv run --frozen python scripts/check_docs.py` | 通过 | docs 导航、链接和 lifecycle metadata 通过 |
| Owner pre-apply review | proposal/specs/design/tasks | Approved | 允许进入实施前准备，不代表代码通过 |
| GATE-13 | Run consistency 方案 | Accepted by owner | 统一 launch、intent/outbox、幂等和 reconciliation |
| Runtime unit checks | `uv run --frozen pytest tests/runtime -q` | 通过（48 passed） | 覆盖当前 Runtime 配置校验；不证明跨服务链路 |
| Model proxy capability probe | 已废弃 | 不再执行 | 旧统一模型代理方案已被七字段最小模型配置取代 |
| Runtime model profile validation | `tests/runtime/test_runtime_config_validation.py` | 通过（定向校验） | `local-compat|production` 和 production deny 规则已锁定；local-compat shortest chain 尚未执行 |
| Local stack doctor | 默认环境；临时 `RUNTIME_MODEL_PROFILE=local-compat` | 默认按预期拒绝；临时显式 profile 后通过 | 未修改 `.env`；目标为本机 PostgreSQL/Redis，尚未 migration、启动服务或执行 shortest chain |

## 2. 尚未执行证据

以下边界在 `verification.md` 中仍为 `not-executed`、`partial` 或 `blocked`：

- 真实 HITL 图的 `input.respond`、事件去重和完整恢复语义；
- scope/target/hash mismatch 和 `get_agent({})` 边界；
- owner 授权的真实 Provider smoke；
- 完整 Browser E2E 和 owner UAT；
- GATE-10 历史 Thread inventory 与脱敏 fixture；
- legacy disposition、current standards/runbook 和重叠 OpenSpec 处置。

当前可交付范围包括 Runtime 配置校验、七字段模型管理和本机真实模型链路的准备；旧统一模型代理、Secret Store、
RS256/JWKS、workload identity 和 capability probe 已废弃，不再作为 P0/P1 门禁。

## 3. 开放约束登记

| 约束 | 为什么不能假设 | 需要的决定/输入 | 阻塞范围 |
| --- | --- | --- | --- |
| GATE-10 历史 Thread | 当前只有原则，没有真实数据覆盖 | 真实历史样本、脱敏规则、fixture 和保留窗口 | legacy parser、读取 normalization、删除清单 |
| 旧统一模型代理/Secret Store/JWKS | 与当前七字段方案冲突 | 未来需求另立 change | 不阻塞当前实现 |
| 生产 Secret Store/代理/身份治理 | 已被最小方案废弃 | 未来另立 change | 不阻塞当前实现 |
| Runtime 动态读取配置 | 当前本地链仍使用既有 env 兼容路径 | 明确最短受信配置读取链 | Runtime 模型闭环 |
| GraphHarbor Compatibility Profile | 当前文档结论不能代替真实请求抓取 | 固定版本、隔离 PostgreSQL/Redis、真实 API/Worker | 所有 chain/formal evidence |
| 旧文档处置 | 不能以“新方案存在”直接删除历史材料 | disposition matrix 和 owner 批准 | 文档清理、导航收口 |

## 4. GATE-10 inventory 操作规程

实施期按以下顺序执行，结果写回 `verification.md`，不在本文档伪造结论：

1. 列出仍被产品、测试、脚本或用户依赖的历史 Thread 入口和 payload 形态。
2. 确认样本来源、租户/项目范围和数据保留授权；不凭空创造历史输入。
3. 脱敏消息、身份、模型和工具参数，形成可重放 fixture。
4. 为每类 fixture 写读取、重开、拒绝和不写回断言。
5. 只有 fixture 通过且 owner 确认保留窗口后，才把兼容项列入正式实现。
6. 没有真实 fixture 或保留要求的 fallback，在新链通过后列入删除清单。

## 5. 当前模型配置检查

模型配置实施必须确认以下事实：

- Platform 保存七字段配置，API key 只写不读；
- 服务端使用 master key 加密并在 Runtime 请求时读取；
- GraphHarbor、Thread、Run、Context 和日志不接收 API key；
- 模型禁用、解密失败和连接失败必须 fail closed。

不实现 execution reference、revision 或第二套代理；本地兼容只复用已有 Provider 环境变量。

## 6. 文档与 runbook 影响

实现阶段预计需要更新：

- Platform Web/API current standards：新 Gateway allowlist、Agent 命名、模型管理和权限边界；
- Platform/GraphHarbor 配置文档：模型七字段、master key、local compatibility profile；
- 部署/恢复 runbook：API/Worker 重启、SSE reconnect、timeout reconciliation 和取消；
- Compatibility Profile：实际 method/path、字段、envelope、错误码、SSE 和脱敏规则；
- 旧文档导航：先加 `Superseded`/`Archived` 标识，再按处置矩阵移动或删除。

这些文档更新必须跟随代码、契约和验证结果，不能先把 target state 写成 Current fact。

## 7. 完成判定

本项目只有同时满足以下条件，才能从 `L1 partial; L2 local-complete; L3 partial` 进入 accepted completion：

1. OpenSpec tasks 全部完成且与代码一致；
2. `verification.md` 的 local、shortest chain、formal/browser/human 证据完整；
3. GATE-10 有真实 inventory 和 fixture 结论；
4. Runtime 动态读取配置的本地受信边界可复现；
5. owner 完成页面 UAT、迁移/删除/发布处置批准；
6. accepted delta specs 已 sync 到 `openspec/specs/`；
7. docs、runbook、导航和历史状态已同步，未产生新的 shadow canon。

在此之前，任何“完成”“上线”“已兼容”的表述都必须限定到实际证据层级。
