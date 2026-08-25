# runtime_service Knowledge

这里存放 `runtime_service` 相关的学习型资料，重点回答“官方推荐怎么用”和“本仓库应该怎么落地”。

推荐阅读顺序：

1. `01-langgraph-context-vs-config.md`
2. `02-create-agent-params.md`
3. `03-sdk-and-curl-passing-context-and-config.md`
4. `04-runtime-contract-v1.md`
5. `05-runtime-contract-open-questions.md`
6. `06-runtime-blueprint-pseudocode.md`
7. `07-langgraph-ecosystem-repository-research.md`
8. `08-streaming-protocols-and-future-events.md`
9. `09-langgraph-runtime-upgrade-and-event-migration.md`

阅读目标：

- 搞清楚 `RuntimeContext`、`config`、`configurable`、`env` 的职责边界
- 搞清楚 `create_agent(...)` 常见参数到底干什么
- 搞清楚通过 LangGraph SDK / HTTP API 怎么把 `context` 和 `config` 传进去
- 搞清楚后续重构要收敛到的正式运行时契约
- 搞清楚还有哪些未决问题不能直接拍脑袋改代码
- 搞清楚如果不考虑兼容，标准重构蓝图应该长什么样
- 了解优秀 LangGraph 产品如何处理生产运行、显式工作流、动态工具和评测
- 搞清楚本地流格式、远程 SSE 协议，以及子图和 HITL 的演进路径
- 搞清楚官方 runtime 升级、普通流和 Protocol v2 事件流的分阶段迁移工作

阅读完成后，再回头看这些活代码会更顺：

- `runtime_service/agents/assistant_agent/graph.py`
- `runtime_service/agents/research_agent/graph.py`
- `runtime_service/services/test_case_service/graph.py`

如果你要看“当前现行标准”，先回到：

- `docs/standards/01-harness-overview.md`
- `docs/standards/02-architecture.md`
- `docs/standards/03-agent-development-playbook.md`
- `docs/standards/08-middleware-development-playbook.md`
