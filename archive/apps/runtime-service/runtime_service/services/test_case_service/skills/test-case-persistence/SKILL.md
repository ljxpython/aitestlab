---
name: test-case-persistence
description: 当最终测试资产已经整理完成且需要正式落库时激活。负责调用唯一持久化工具，把附件解析结果和正式测试用例写入 interaction-data-service。
---

# 测试用例持久化 Skill

## 激活场景
- 用户明确要求保存、落库、入库、持久化
- `output-formatter` 已完成，已有结构化结果可写入

## 前置条件
- 已完成 `requirement-analysis`
- 已完成 `test-strategy`
- 已完成 `test-case-design`
- 已完成 `quality-review`
- 已完成 `output-formatter`

## 调用前最小输入
- `bundle_title`
- `bundle_summary`
- `test_cases`
- `quality_review`

## 执行规则
1. 只调用 `persist_test_case_results`
2. 不要自行传 `project_id`、`thread_id`、文档 ID
3. 结构化结果准备好后立即调用工具，不要继续写长说明
4. 只能根据工具返回结果汇报是否保存成功
5. 如果落库前发现关键事实依据不足，应回到前序阶段先调用知识库工具补证据，而不是带着猜测落库

## 返回汇报
- `status=persisted`：说明已入库，并给出文档数、用例数、项目标识、批次标识
- `status=skipped_remote_not_configured`：说明远端未配置，本轮仅生成未入库
- `status=skipped_empty_test_cases`：说明没有可入库的正式测试用例
- `status=failed_remote_request`：说明远端已配置但请求失败，本轮未完成正式落库
- `status=partial_failed`：说明部分记录写入成功、部分失败，必须如实汇报失败项
- 其他状态：如实报告失败原因

## 约束
- 没有工具成功返回，不能说“已保存”
- 持久化是最终动作，不要在中间阶段提前执行
