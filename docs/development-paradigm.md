# 当前项目开发范式说明

> 状态：Supporting Legacy Reference。当前任务路由以 `AGENTS.md` 和
> `docs/standards/01-ai-execution-system.md` 为准；本文保留详细架构、需求模板和联调清单，
> 不属于默认阅读路径。

## 这篇文档想讲清什么

这篇文档不重复介绍怎么启动项目，而是专门回答 3 个问题：

- 当前项目到底在解决什么工程问题
- 为什么要把平台侧、运行时、调试入口拆成现在这样
- 以后继续开发时，应该优先改哪里，按什么顺序推进

如果只用一句话概括，这个项目的核心思路就是：

> 用平台侧做治理，用运行时做智能体，用调试前端做快速验证，用结果域服务做持久化承接，几块之间通过浅封装和稳定契约连接起来，而不是揉成一个大泥球。

补充口径：

- 当前正式平台前端宿主是 `apps/platform-web`
- 当前正式平台控制面是 `apps/platform-api`
- 当前正式平台链路是 `platform-web -> platform-api -> runtime-service`
- `runtime-web` 继续作为独立调试入口

如果你要的是“现在该怎么判、怎么升级、怎么走最短链”，先读：

- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`

这篇文档讲背景和范式；上面两篇分别讲当前标准/路由，以及未来实际提需求与完成任务时怎么使用这套系统。

## 1. 这个项目真正解决什么问题

很多 Agent 项目一开始都能跑 demo，但一旦进入真实工程开发，很快就会出现几类典型问题：

- 平台治理和智能体逻辑写在一起，后面谁改都痛苦
- 调试入口和正式产品入口混在一起，导致验证链路混乱
- 权限、项目隔离、审计、catalog、运行时能力这些平台问题，反过来污染智能体代码
- 智能体结果落库直接塞进平台主数据模型，最后平台越来越重
- 本地能跑，后面一到拆服务、上容器、做独立部署就开始互相扯头花

当前仓库的设计目标，就是把这些问题提前拆开。

## 2. 一句话理解当前架构

当前默认链路可以概括成两条：

- 平台链路：`platform-web -> platform-api -> runtime-service`
- 调试链路：`runtime-web -> runtime-service`

再加上一个结果域服务：

- 持久化链路：`runtime-service -> interaction-data-service`

这说明当前仓库不是单体 Agent Demo，而是一个明确分层的企业级 AI 平台骨架：

- `platform-web` / `platform-api` 负责平台控制面
- `runtime-service` 负责智能体运行时
- `runtime-web` 负责运行时调试
- `interaction-data-service` 负责结果域数据

## 3. 为什么要这么设计

### 3.1 平台侧做浅封装，不深度侵入 Runtime

这里最容易被误解的一点，就是“平台接入 Runtime”不等于“平台吃掉 Runtime”。

当前项目里，平台侧的定位很明确：

- `platform-api` 负责认证、项目边界、成员与权限、审计、catalog、runtime policy/capability 管理
- `platform-web` 负责平台工作台界面、管理页面、聊天入口和工作区导航

而智能体真正的执行、模型装配、工具装配、MCP 接入、graph 编排，都放在 `runtime-service`。

这就叫“浅封装”。

这里的浅，不是说平台什么都不做，而是说平台只做上层治理和入口整合，不去改写智能体内部的运行模式。当前 `platform-api` 不是透明透传 proxy，而是保留明确的 `/api/langgraph/*` 网关，在这里做：

- 显式路由
- 必要白名单处理
- 项目边界校验
- metadata 注入
- 平台治理相关控制

这样做的好处很直接：

- 平台团队可以专注权限、管理、审计，不用被智能体实现细节拖死
- AI 开发可以专注 `runtime-service`，不必每做一个 Agent 都改一轮平台底座
- Runtime 依然保持标准 LangGraph 风格接口，后面升级和替换成本更低

### 3.2 功能解耦比“功能堆一起”更重要

当前仓库里，每个应用的边界其实已经很明确：

- `platform-web`：正式平台工作台、管理页面、平台聊天入口
- `platform-api`：鉴权、项目治理、审计、catalog、运行时网关
- `runtime-service`：graph 注册、模型参数解析、工具装配、MCP、智能体执行
- `runtime-web`：直连 Runtime 的调试前端
- `interaction-data-service`：结果域落库与查询

这套拆法的意义不是“服务多看起来高级”，而是为了让每一层都只承担自己该承担的责任。

平台侧不去吞智能体逻辑，运行时不去硬扛平台治理，结果域服务不去污染平台主数据，这才是后续能长期演进的前提。

### 3.3 调试链路必须独立存在

`runtime-web` 的存在不是装饰品，它解决的是一个很实际的问题：

如果每次开发智能体都必须先接完整个平台链路，你的调试成本会很高，排查问题也会混在权限、网关、页面逻辑里一起爆炸。

所以当前项目保留了独立调试链路：

- `runtime-web -> runtime-service`

这条链路的价值是：

- 先验证智能体本身是不是工作正常
- 先验证 prompt、tools、MCP、graph 编排是不是符合预期
- 先验证运行时接口是不是稳定
- 在不引入平台治理复杂度的前提下快速迭代

等你把智能体在 `runtime-web` 上调通之后，再接到 `platform-web` / `platform-api` 里，成本就会非常低。

这里所谓“零成本、无适配”，本质上指的是：

- 你开发和调试的本来就是同一个 `runtime-service`
- 平台侧消费的也是同一套 Runtime 契约
- 只要你没有绕开现有边界、私自把业务逻辑写死在平台层，那么后续接平台通常不需要重写 Agent

也就是说，真正的秘诀不是“平台魔法适配”，而是“一开始就守住边界”。

### 3.4 结果域再拆一层，平台会更轻

很多项目一做结果落库，就喜欢全塞进平台后端，最后平台侧数据库模型越来越脏，越改越重。

当前仓库选择把结果域抽到 `interaction-data-service`，核心好处有两个：

- 平台主数据和结果域数据不互相污染
- Runtime 需要持久化时，可以通过明确的 HTTP 契约写入结果域服务

这样平台侧依然可以通过 `platform-api` 聚合查询、做权限与项目隔离，但不需要亲自维护每一个智能体业务表。

### 3.5 以后改成 Docker 部署会更自然

你提到后面各部分用 Docker 方式部署，这个方向和当前设计其实是完全一致的。

因为当前已经把责任边界拆清楚了，所以后面如果做容器化部署：

- `platform-web`
- `platform-api`
- `runtime-service`
- `runtime-web`
- `interaction-data-service`

都可以按各自职责独立构建、独立部署、独立扩缩容。

换句话说，Docker 不是这套架构成立的前提，而是这套解耦架构成熟之后最自然的部署结果。

## 4. 为什么说智能体开发主战场在 `runtime-service`

当前仓库里，真正和 AI 能力强相关的内容都已经收敛到 `runtime-service`：

- graph 注册在 `apps/runtime-service/langgraph.json`
- 运行时业务输入收敛在 `runtime_service/runtime/context.py`
- graph 运行时解析收敛在 `runtime_service/middlewares/runtime_request.py`
- 模型装配在 `runtime_service/runtime/modeling.py`
- 工具装配在 `runtime_service/tools/registry.py`
- MCP server 清单在 `runtime_service/mcp/servers.py`
- 业务型智能体建议放在 `runtime_service/services/<service_name>/`

更关键的是，这里不是只给了一个空壳，而是已经准备好了多种开发范式和例子：

- `assistant`：默认推荐范式，适合从最小可行 Agent 开始
- `deepagent_demo`：适合任务分解、多子任务协同
- `personal_assistant_demo`：适合 supervisor + subagent 协作
- `customer_support_handoffs_demo`：适合显式步骤流
- `sql_agent`：适合服务化 Agent 参考

所以，后面新增智能体时，默认思路应该是：

- 先在 `runtime-service` 里实现
- 先在 `runtime-web` 或 runtime devtools 里验证
- 稳定后再挂到平台入口

不要一上来就把智能体逻辑散落到平台前后端里，那是给后面埋雷。

## 5. 为什么说几行代码就能搭一个简单智能体

`runtime-service` 已经把最麻烦的共性问题封装掉了：

- 模型选择和运行时参数处理已经有统一入口
- 公共 tools / MCP 装配已经有现成注册机制
- 多模态 middleware 已经准备好
- graph 注册方式已经固定
- 相关测试和最小验证路径也已经写好

所以，一个最小可运行 Agent 的核心代码可以非常薄。按照仓库现成的模板，一个 hello demo 的核心结构大概就是这样：

```python
from langchain.agents import create_agent

from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import AgentDefaults


DEFAULTS = AgentDefaults(
    model_id="default-model",
    system_prompt="You are a helpful assistant.",
    enable_tools=False,
)

graph = create_agent(
    model=resolve_model_by_id(DEFAULTS.model_id),
    tools=[hello_tool],
    system_prompt=DEFAULTS.system_prompt,
    context_schema=RuntimeContext,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=DEFAULTS,
            required_tools=[hello_tool],
            public_tools=[],
        )
    ],
)
```

真正要做的事情，通常只剩下 3 步：

1. 写自己的 tool / prompt / graph 逻辑
2. 注册到 `langgraph.json`
3. 跑最小验证命令

这就是为什么说它已经不是“从零搭框架”，而是“在现成运行时骨架上扩展能力”。

## 6. 未来继续开发时，建议你按这个顺序判断

### 6.1 先判断需求属于哪一层

你以后每接一个需求，先别急着写代码，先做一个最基础的判断：

- 如果是权限、项目、成员、审计、catalog、平台配置，改 `platform-api` / `platform-web`
- 如果是 prompt、tool、MCP、graph、模型装配、Agent 行为，改 `runtime-service`
- 如果是运行时联调和交互验证，先用 `runtime-web`
- 如果是业务结果持久化与查询，改 `interaction-data-service`

这个判断做对了，后面开发基本就顺了；判断做错了，代码很快就会串层。

### 6.2 先在 Runtime 内把能力做通

新增智能体能力时，推荐顺序是：

1. 先选合适范式
2. 在 `runtime-service` 内完成 graph / tools / prompts
3. 注册 graph
4. 本地验证运行时接口
5. 用 `runtime-web` 做交互验证

如果这一步都没过，就不要急着接平台页面。

### 6.3 再决定要不要接平台入口

只有当智能体本身已经稳定后，再看平台侧要不要补：

- 管理页面
- 平台聊天入口
- assistant/graph 管理
- 项目级权限控制
- catalog 同步与治理能力

平台侧的角色应该是“把已经稳定的 Runtime 能力纳入治理和产品入口”，不是“代替 Runtime 做智能体开发”。

### 6.4 需要结果落库时，再接结果域服务

如果某个智能体只是对话验证，不一定立刻需要持久化。

但如果它进入正式业务链路，需要：

- 结构化结果沉淀
- 列表查询
- 详情展示
- 审批后落库

这时候再把结果域能力放进 `interaction-data-service`，由 Runtime 的本地 tools 通过 HTTP 调用它。

这套方式比把业务表直接硬塞进 `platform-api` 这类平台控制面更清爽得多。

### 6.5 最后再考虑部署形态

当边界都守住之后，部署方式反而简单：

- 本地联调用当前默认多服务方案
- 独立部署时按服务拆镜像和容器
- 哪个服务变化频繁，就独立迭代哪个服务

所以重点永远不是“先写 Docker”，而是“先把边界守住”。

## 7. 一定要记住的几个核心思路

最后把最重要的话直接收口成几条，后面开发时反复对照就行：

1. 平台侧是浅封装，不是把智能体运行时深度吞进去。
2. 平台侧优先专注权限、管理、审计、catalog、治理能力。
3. 智能体和 AI 相关开发，主战场永远在 `runtime-service`。
4. `runtime-web` 是调试入口，先把智能体在这里调通，再接平台。
5. 调试完成后，只要遵守现有契约，就可以无缝接入 `platform-api` / `platform-web`，不需要为平台重写一套 Agent。
6. `interaction-data-service` 负责结果域，避免平台主数据和业务结果表混成一锅粥。
7. 后面用 Docker 独立部署，是当前解耦设计的自然延伸，不是另一套新思路。
8. `runtime-service` 已经提供脚手架、范式和样例，后续开发优先仿照现有模式，不要重复造轮子。

## 8. 建议配套阅读

如果你想把这套开发范式看得更实，建议继续看这些文件：

- `README.md`
- `docs/development-guidelines.md`
- `docs/project-story.md`
- `apps/platform-api/docs/README.md`
- `apps/platform-api/docs/handbook/project-handbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/runtime-web/README.md`
- `apps/runtime-service/docs/README.md`
- `apps/runtime-service/runtime_service/docs/05-template-to-runnable-agent-10min.md`
- `apps/interaction-data-service/README.md`

## 9. 多应用联动开发范式

这一节不是抽象口号，而是把最近一轮 `test_case_service -> interaction-data-service -> platform-api -> platform-web` 的真实开发、调试、联调、提交过程收敛成一套后续都能复用的方法。

### 9.1 第一原则：先把要做什么讨论清楚，再开始写代码

任何一轮开发，先回答下面这些问题：

1. 这次变更的最终目标是什么
2. 这次只改哪几层，不改哪几层
3. 输入是什么，输出是什么，谁来持久化
4. 上下游链路怎么走，接口边界在哪
5. 当前是否需要页面，只做服务层能不能先闭环
6. 本轮验收用什么真实数据、真实接口、真实模型来验证

如果这 6 个问题说不清，就不要急着开工。

核心要求只有一句：

> 代码一定要简洁，方案一定要先对齐，链路一定要先画清，再开始写。

### 9.2 先追求最小闭环，不追求一口气全做完

推荐做法不是一上来就全链路齐头并进，而是按“最小可验证闭环”推进：

1. 先在最靠近业务本体的一层把能力做通
2. 再补持久化层
3. 再补平台管理接口
4. 最后补平台页面和交互

比如最近这轮 testcase 开发，正确顺序就是：

1. 先把 `runtime-service` 里的 `test_case_service` 做通
2. 再把结果落到 `interaction-data-service`
3. 再由 `platform-api` 暴露 testcase 管理接口
4. 最后由 `platform-web` 展示管理页和导出能力

不要反过来。先堆页面、再倒逼服务补能力，通常只会把边界写烂。

### 9.3 各应用层必须遵守的职责边界

#### `runtime-service`

只负责：

- 智能体 graph
- prompt / skills / tools / middleware
- 模型选择与运行时行为
- 真实业务处理

不要负责：

- 平台权限治理
- 平台管理页面协议
- 平台表结构和页面状态拼装

#### `interaction-data-service`

只负责：

- 结果域落库
- 结果域查询
- 服务专属资源接口

不要负责：

- 智能体编排
- 平台权限
- 页面展示口径

接口范式要尽量统一：

- 一个服务一组专属前缀
- 资源语义清楚
- 不把不同业务结果揉成一个“万能接口”

#### `platform-api`

只负责：

- 管理面聚合接口
- 项目边界和权限校验
- 对下游服务做协议整形
- 文件下载、列表聚合这类平台适配能力

不要负责：

- 直接承载智能体核心业务逻辑
- 替 `runtime-service` 实现 prompt / tool / graph
- 把结果域表直接挪成平台主数据

#### `platform-web`

只负责：

- 页面、交互、筛选、下载、详情展示
- 调平台管理接口
- 用产品化方式组织工作区

不要负责：

- 自己拼业务持久化协议
- 绕过 `platform-api` 直连结果域服务
- 把导出、权限、聚合逻辑硬写在前端

#### `runtime-web`

只负责：

- 调试入口
- 快速验证运行时行为
- 在不引入平台治理复杂度的情况下先把 Agent 调通

不要拿它替代正式平台入口，但也不要低估它的价值。
Agent 没在 `runtime-web` 或服务级脚本里调通之前，不要急着接 `platform-web`。

### 9.4 开发前必须写清楚的“链路图”

每一轮需求都建议先写一段文本链路，至少写到这个颗粒度：

```text
前端/入口
  -> 平台接口层
    -> 运行时服务 / 结果域服务
      -> 存储落点
```

例如 testcase 管理能力：

```text
platform-web
  -> platform-api /_management/projects/{project_id}/testcase/*
    -> interaction-data-service /api/test-case-service/*
      -> test_case_documents / test_cases
```

例如智能体生成能力：

```text
runtime-web 或 platform-web chat
  -> runtime-service test_case_agent
    -> skills / tools / middleware
      -> interaction-data-service
```

链路不写清楚，后面一定会出现：

- 接口加错层
- 字段放错位置
- 页面和服务口径不一致
- 调试时不知道该看哪一层

### 9.5 沟通方式也要工程化

多人协作或和 AI 协作时，不要只说“做一个 xxx 功能”，要明确以下信息：

- 本轮目标
- 本轮范围
- 是否要落库
- 是否要上平台页
- 是否要走真实前端
- 默认项目 ID / 默认模型是否允许兜底
- 验收路径是什么

更具体一点，推荐直接把下面这些话说出来：

1. “这一轮先只做服务层，不接前端”
2. “这一轮要把平台接口一起补上”
3. “这一轮必须用真实 PDF / 真实模型 / 真实下游服务验证，不能 mock”
4. “这一轮只验证到 platform-api，不依赖前端”
5. “这一轮要前端真实上传、真实下载，再看最终体验”

这类沟通越具体，返工越少。

### 9.6 测试与验证：关键链路禁止 mock

这个项目后续最重要的统一约束之一：

> 只要涉及智能体行为、持久化、平台联动、文件上传下载，就优先使用真实数据、真实服务、真实模型来验证，不要用 mock 自我感动。

原因很简单：

- mock 很难暴露模型工具遵循问题
- mock 很难暴露流式输出异常
- mock 很难暴露上下游真实字段不一致
- mock 很难暴露超时、幂等、下载文件、权限链路问题

最近 testcase 这轮就验证出了一个典型问题：

- `iflow_kimi-k2` 在正式持久化场景下会口头声称“已保存”
- 但真实工具调用记录里根本没有 `persist_test_case_results`
- 这个问题只有在真实模型、真实脚本、真实远端查询下才看得出来

### 9.7 正确的测试顺序：先单层真实验证，再逐层抬高

推荐统一使用下面的顺序。

#### 第一层：服务内最小真实验证

如果当前需求不依赖前端，先别上前端。

先在服务层用真实数据验证：

- 真实模型
- 真实输入文件
- 真实下游服务
- 真实查询接口

例如 `runtime-service` 的 testcase 场景，先用这类脚本：

- `runtime_service/tests/services_test_case_service_debug.py`
- `runtime_service/tests/services_test_case_service_document_live.py`
- `runtime_service/tests/services_test_case_service_persistence_live.py`

这一步重点看：

- 流式输出是否正常
- skills 是否真的被读取
- tool call 是否真的发生
- 下游数据是否真的落库
- 有没有异常、超时、字段丢失

#### 第二层：结果域真实校验

只要涉及落库，就必须查下游服务，不要只看模型回复文本。

例如：

- `runtime-service` 写入后，要去查 `interaction-data-service`
- `platform-api` 导出后，要把真实下载文件重新打开校验

必须查的内容包括：

- 是否真的有记录
- 条数是否正确
- 关键字段是否齐
- 关联字段是否正确
- 幂等是否成立

#### 第三层：平台接口真实校验

如果当前变更已经到管理面，就用真实登录和真实接口来测：

- 真实登录拿 token
- 真实请求 `platform-api`
- 真实 project_id / batch_id / case_id
- 真实下载文件或详情接口

例如这轮 Excel 导出，正确做法就是：

1. 登录 `platform-api`
2. 调 `/_management/projects/{project_id}/testcase/cases/export`
3. 下载真实 `.xlsx`
4. 再用 `openpyxl` 反读校验 sheet 和数据行数

这比只看前端按钮亮没亮靠谱得多。

#### 第四层：前端真实联调

只有当需求确实依赖页面交互时，再进入前端联调。

这时候必须用真实前端动作测试：

- 真实登录
- 真实上传
- 真实下载
- 真实筛选和跳转
- 真实页面状态

不要用“接口已经通了”代替“前端已经可用”。
但同样，不要在前端还没必要参与时，一上来把问题复杂化。

### 9.8 如果当前问题只需要验证某一层，就只打到那一层

这是后续研发中非常实用的一条纪律：

- 只改 `runtime-service`，就先在 `runtime-service` 把真实验证做透
- 只改 `interaction-data-service`，就直接调它的接口确认读写口径
- 只改 `platform-api`，就用真实登录 + curl / 脚本做管理面验证
- 只改 `platform-web`，就在后端已经稳定的前提下看页面交互

不要一上来就五层一起跑，然后出了问题全靠猜。

### 9.9 真实测试数据也要沉淀成固定资产

建议每个业务服务都保留一组可复用的真实样例：

- 真实 PDF
- 真实图片
- 真实请求文本
- 真实项目 ID / batch ID
- 真实调试脚本

例如当前 testcase 场景已经有：

- `apps/runtime-service/runtime_service/test_data/接口文档.pdf`

以后类似功能开发，都应该尽量保留这类“可重复执行”的真实样例，而不是每次临时凑一个假数据。

### 9.10 调试输出要看 4 类信息，不能只看最后一句回复

调智能体时，至少要抓这 4 类内容：

1. 流式输出内容
2. tool call 记录
3. 下游服务返回结果
4. 最终异常或成功状态

如果只盯最后一句“成功了”“失败了”，信息密度太低，排查效率会很差。

### 9.11 超时时间宁可长一点，也不要因为默认超时误判

智能体、PDF 解析、落库、导出这些链路本来就可能慢。

推荐做法：

- 脚本和联调命令显式传较长 timeout
- 下游 HTTP timeout 也单独拉长
- 在文档里把这些超时写明

避免因为默认 30 秒、60 秒超时，把本来能成功的链路误判成系统坏了。

### 9.12 文档要跟着方案和代码走，不要最后补

每一轮真实开发，至少要同步维护两类文档：

1. 设计文档
2. 问题排查 / 验证文档

建议放置原则：

- 通用范式放 `docs/`
- 服务设计放应用自己的 `docs/`
- 业务专项设计放对应服务目录

文档里至少写清：

- 目标
- 边界
- 接口
- 数据落点
- 验证方式
- 当前已知问题

### 9.13 提交也必须是工程化的

代码写完不是结束，提交也必须可追踪。

统一要求：

- 遵守 `docs/commit-and-changelog-guidelines.md`
- commit message 必须写 `Log` 和 `Test`
- `Test` 里明确写：
  - 跑了什么自动测试
  - 做了什么真实手工验证
  - 如果没跑，为什么没跑

这样后面回看提交记录时，才知道这一轮到底改了什么、验证到哪一层。

### 9.14 后续开发统一按这张清单自检

每次动手前，自检一遍：

1. 这轮目标和范围是否已经说清楚
2. 这轮属于哪一层，链路图是否写清楚
3. 是否优先选择了最小闭环，而不是一口气全改
4. 是否保持了各应用层职责边界
5. 是否优先使用真实数据、真实模型、真实服务验证
6. 是否先在低依赖层完成真实验证，再逐层抬高
7. 是否记录了流式输出、tool call、远端结果和异常
8. 是否把设计和验证过程写进对应文档
9. 是否按规范提交，并写清楚 `Log` / `Test`

如果这一轮都能按这 9 条执行，失误会明显下降，返工也会少很多。

## 10. 标准需求评审模板

这一节不是说明文，是后续每轮开发都可以直接复制的模板。

推荐做法：

1. 每次新需求先贴这一段
2. 先把空白项补全
3. 补全后再开始设计和编码

### 10.1 标准模板

````md
# 需求评审模板

## 1. 目标

- 本轮要解决的问题：
- 最终用户可感知结果：
- 不做什么：

## 2. 范围

- 涉及应用：
  - runtime-service:
  - interaction-data-service:
  - platform-api:
  - platform-web:
  - runtime-web:
- 本轮主改动层：
- 本轮不改动层：

## 3. 链路

```text
入口
  -> 平台接口 / 运行时服务
    -> 下游服务
      -> 存储落点
```

- 请求入口：
- 上游调用方：
- 下游依赖：
- 最终落点：

## 4. 输入与输出

- 输入数据：
- 输出数据：
- 关键字段：
- 是否需要持久化：
- 是否需要下载文件：
- 是否需要上传文件：

## 5. 职责边界

- runtime-service 负责：
- interaction-data-service 负责：
- platform-api 负责：
- platform-web 负责：
- runtime-web 负责：

## 6. 接口与数据设计

- 新增接口：
- 修改接口：
- 复用接口：
- 数据表 / 资源：
- 幂等策略：
- 默认值 / 兜底策略：

## 7. 模型与工具策略

- 是否需要真实模型：
- 默认模型：
- 是否允许服务级默认模型兜底：
- 关键 tool / skill：
- 是否必须校验 tool call：

## 8. 验证方案

- 是否允许 mock：否 / 仅限非关键层
- 服务层验证方式：
- 平台接口验证方式：
- 前端验证方式：
- 真实测试数据：
- 真实 project_id / batch_id：
- timeout 策略：

## 9. 验收标准

- 服务层通过标准：
- 下游落库通过标准：
- 平台接口通过标准：
- 前端通过标准：
- 文档补充要求：

## 10. 提交策略

- 是否拆分提交：
- 提交边界：
- 每个提交的 Log / Test 重点：
````

### 10.2 填写要求

这份模板至少要把下面几项写实，不能空着：

- 本轮目标
- 改动范围
- 入口到落点的链路
- 是否需要真实模型
- 是否需要真实数据
- 验证做到哪一层
- 验收标准

如果这些还没写清楚，就不应该开始写代码。

## 11. 标准联调清单

这一节同样是可直接复用的执行清单。

推荐用法：

1. 每轮开始联调前复制一份
2. 按顺序逐项打勾
3. 任何一步没过，就停在当前层排查，不跳层猜问题

### 11.1 标准清单

```md
# 联调清单

## A. 联调前准备

- [ ] 本轮需求评审模板已补完
- [ ] 已明确本轮只改哪几层
- [ ] 已明确上下游链路
- [ ] 已准备真实测试数据
- [ ] 已准备真实 project_id / batch_id / case_id
- [ ] 已写清超时时间

## B. 服务启动检查

- [ ] runtime-service 已启动并健康检查通过
- [ ] interaction-data-service 已启动并健康检查通过
- [ ] platform-api 已启动并健康检查通过
- [ ] platform-web / runtime-web 已按需启动

## C. 服务层真实验证

- [ ] 使用真实模型验证
- [ ] 使用真实 PDF / 图片 / 文本验证
- [ ] 已抓取流式输出内容
- [ ] 已抓取 tool call 记录
- [ ] 已抓取最终异常 / 成功状态
- [ ] 已确认模型回复与真实 tool 行为一致

## D. 下游结果校验

- [ ] 已查询 interaction-data-service 真实结果
- [ ] 已确认记录真实存在
- [ ] 已确认条数正确
- [ ] 已确认关键字段完整
- [ ] 已确认关联字段正确
- [ ] 已确认幂等成立

## E. 平台接口校验

- [ ] 已使用真实登录获取 token
- [ ] 已用真实项目上下文调用 platform-api
- [ ] 已确认路由和权限正确
- [ ] 已确认聚合结果正确
- [ ] 已确认下载 / 导出文件可真实打开

## F. 前端联调校验

- [ ] 只有在后端稳定后才开始前端联调
- [ ] 已完成真实登录
- [ ] 已完成真实上传
- [ ] 已完成真实下载
- [ ] 已完成真实筛选 / 跳转 / 详情查看
- [ ] 已确认页面错误提示符合预期

## G. 文档与提交

- [ ] 已补设计文档
- [ ] 已补排查 / 验证文档
- [ ] 已记录真实验证命令
- [ ] 提交信息已按 Log / Test 规范编写
- [ ] 已确认无无关文件混入提交
```

### 11.2 联调执行顺序

统一按这个顺序执行：

1. 先服务层真实验证
2. 再查下游结果
3. 再验平台接口
4. 最后验 `platform-web` 等真实前端页面

不要跳步骤。

### 11.3 联调失败时的排查纪律

如果联调失败，按下面顺序排查：

1. 先确认是不是当前层问题
2. 再确认上下游字段和契约是否一致
3. 再确认是真实 tool call 问题，还是模型口头回复问题
4. 再确认是接口问题、权限问题、超时问题，还是页面问题

不要一失败就直接去改前端或改平台页。

### 11.4 建议作为每轮开发的固定输出

后续每轮开发，建议至少沉淀这 3 份内容：

1. 一份需求评审模板实例
2. 一份联调清单执行结果
3. 一次按规范写好的提交记录

这样后面不管是人看还是 AI 协助，都能快速接手，不会反复踩同样的坑。
