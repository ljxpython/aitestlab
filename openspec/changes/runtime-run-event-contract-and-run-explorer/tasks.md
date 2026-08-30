## 1. 契约与数据模型

- [ ] 1.1 新增 Runtime Run 事件类型、事件信封和 `safe_metadata` 白名单校验，覆盖 `event_id`、`event_version`、`sequence`、来源和关联字段
- [ ] 1.2 扩展 `DurableRunRecord` 的 assistant/graph/request/trace/config/时间字段，并生成可回滚数据库迁移
- [ ] 1.3 新增 `RuntimeRunEventRecord`、`(run_id, sequence)`、来源幂等约束和查询索引
- [ ] 1.4 在仓储层实现生命周期事件事务写入、来源幂等写入、按 `after_sequence` 查询和 cursor 编解码
- [ ] 1.5 固化事件状态转移表和冲突错误码，覆盖终态重复、非法恢复和来源幂等冲突

## 2. Runtime Gateway 写入链路

- [ ] 2.1 在 `run.submitted`、`run.started`、interrupt、cancel 和终态同步路径写入平台生命周期事件
- [ ] 2.2 确保 Run/Operation 状态变更与生命周期事件同事务提交，并为失败增加可重试对账日志
- [ ] 2.3 增加内部执行细节事件入口的认证、Run 归属校验和 at-least-once 幂等处理
- [ ] 2.4 将敏感字段过滤和 payload 大小限制应用到所有事件写入路径

## 3. Run Explorer API

- [ ] 3.1 新增 `/api/runtime/runs` cursor 分页列表接口和项目/assistant/graph/status/actor/时间筛选
- [ ] 3.2 新增 `/api/runtime/runs/{run_id}` 详情接口，聚合 Run、事件、Operation、Audit 和 Langfuse 摘要
- [ ] 3.3 新增 `/api/runtime/runs/{run_id}/events` 事件分页接口，支持 `after_sequence` 和稳定排序
- [ ] 3.4 为外部数据源实现独立超时、部分返回和 `source_status`，不得向浏览器暴露凭据
- [ ] 3.5 为列表、详情、事件和 break-glass 查看补齐项目/平台权限校验与 Audit 记录
- [ ] 3.6 明确 `/api/runtime/*` 项目路由与 `/api/admin/*` 平台路由的独立权限边界

## 4. SSE 与前端接入

- [ ] 4.1 为平台事件流定义 `id: event_id`、`event: event_type` 和 `Last-Event-ID` 补发语义
- [ ] 4.2 验证历史事件与实时事件按 `event_id` 去重、按 `sequence` 排序，未知事件可忽略
- [ ] 4.3 在 `platform-web` 增加 Run Explorer 列表、详情时间线和 `/admin` 路由布局接入

## 5. 验证与文档

- [ ] 5.1 编写事件信封、幂等、并发 sequence、敏感字段和事务一致性测试
- [ ] 5.2 编写 Run Explorer 权限、cursor、部分失败、Trace 凭据隔离和事件补发测试
- [ ] 5.3 运行 runtime_gateway 相关 pytest、platform-api 最短链测试和前端类型/构建检查
- [ ] 5.4 更新 17 号架构文档及 API/运维说明，记录兼容和回滚行为
- [ ] 5.5 创建并持续维护 `verification.md`，记录 owner review、命令、结果、未覆盖边界和 disposition
