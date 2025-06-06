

## 项目初步搭建(2025年06月05日)

基础的框架

### 初始任务

```
参考提示词：
	1、做个前端界面，界面风格参考 ant.designPro，界面风格要炫酷，代码放到frontend目录
  可以参考https://x.ant.design/components/overview-cn
	2、后端基于Fastapi提供接口，使用sse协议进行流式输出，代码放到backend目录

	3、使用autogen0.5.7 实现与大模型对话，具体的autogen代码请参考：
	https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html
  本地demo放在了examples目录下

	autogen相关组件已经完成安装

	后端：进入backend，执行 pip install -r requirements.txt
		启动后端服务：直接运行main.py
	前端：进入frontend，执行 npm install
		启动前端服务：npm run dev
```





AI提示生成代码

<img src="./assets/image-20250605153425659.png" alt="image-20250605153425659" style="zoom:50%;" />



开始前端创建

<img src="./assets/image-20250605153712233.png" alt="image-20250605153712233" style="zoom:50%;" />

修复问题完成创建

<img src="./assets/image-20250605153811039.png" alt="image-20250605153811039" style="zoom:50%;" />

遇到了一些问题,需要作者这边手动处理

<img src="./assets/image-20250605154249797.png" alt="image-20250605154249797" style="zoom:50%;" />

主要问题`start.sh`脚本生成有问题,而且提示我需要重新创建虚拟环境

### 优化

和AI进行对话,内容如下

```
我做了如下修改
1. 后端需要在根目录下运行,不需要创建虚拟环境,直接使用根目录下的虚拟环境
2. 我讲conf移到了Backend目录下,请使用该目录下的环境变量配置
3. 后端的导入,请从根目录下,而不是Backend,例如:from backend.models.chat import ChatRequest, ChatResponse, StreamChunk而不是from models.chat import ChatRequest, ChatResponse, StreamChunk
```



<img src="./assets/image-20250605160155055.png" alt="image-20250605160155055" style="zoom:50%;" />

修复代码:

<img src="./assets/image-20250605160735707.png" alt="image-20250605160735707" style="zoom:50%;" />

### 优化

运行前后端的脚本部分,我还想要做进一步优化

```
start.sh的相关功能需要优化
1. 使用makefile的方式
功能分为:
1. 环境安装
2. 后端运行,使用nohup的方式
3. 前端运行
4. 停止前端进程
5. 停止后端进程
```

![image-20250605162255773](./assets/image-20250605162255773.png)

接下来就是一步步根据AI助手的提示修改

![image-20250605164825255](./assets/image-20250605164825255.png)



![image-20250605164835746](./assets/image-20250605164835746.png)

最终帮我完成

![image-20250605165129775](./assets/image-20250605165129775.png)

### 优化

fastapp我想变成工厂的模式,和AI代码对话内容如下:

```
backend/app.py 文件内的内容放到backend/__init__.py内,修改为工厂模式,代码可以参考如下
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_data()
    yield
    await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")
    return app


app = create_app()
```

![image-20250605165535610](./assets/image-20250605165535610.png)

AI很贴心的帮我完成了`READEME.md`

<img src="./assets/image-20250605170432907.png" alt="image-20250605170432907" style="zoom:67%;" />

### 问题

![image-20250605172724532](./assets/image-20250605172724532.png)

前端报错,这会儿就需要看后端代码了

F12调试

![image-20250605173401631](./assets/image-20250605173401631.png)

代码此处报错`错误: The agent name must be a valid Python identifier.false`

那遇到报错最好的处理方式其实就是打断点来进行调试了

而且此刻的我发现我缺啥一个log模块,很多关键日志都没有,那么此时让AI来帮助我完成

和AI对话如下:

```
我发现后端没有log模块,请帮我做一下封装,可以使用loguru这个第三方库,然后在代码的关键位置都输出关键日志,这样可以很好的进行debug
```

![image-20250605174904935](./assets/image-20250605174904935.png)

最终帮我完成了日志模块

![image-20250605181058312](./assets/image-20250605181058312.png)

### 优化

每一次优化,AI助手都会帮我生成一个md文档,用来表述这些内容包含什么,我想他帮我这些文档加入到导读文档中

```
你帮我生成了很多使用文档,请在README.md文中适合的地方加入他们的链接,并且,在这些文档的开始还有链接可以在跳转回来,这种方式:[工程搭建记录](./MYWORK.md)
```

![image-20250605181444239](./assets/image-20250605181444239.png)

优化后的结果:

<img src="./assets/image-20250605182745699.png" alt="image-20250605182745699" style="zoom:50%;" />



### 解决问题

现在日志已经能够反应出问题在哪里了

![image-20250605191544425](./assets/image-20250605191544425.png)

这个问题,我们可以自己修改,也可以让AI修改,但是本次的挑战是尽量让AI帮忙生成代码,因此,我们把问题抛给AI让AI来帮忙解决

这里先说一下我的思路,问题的出在这里,这里的`name=f"assistant_{conversation_id}"`不可复用,而且使用完成后我也没看到销毁agent的地方,这里应该有隐患,就是最后的内存泄漏发生(尽管`clear_conversation`函数中有销毁agent的逻辑)也就是说我还需要让服务可以自己回收agent

```
 agent = AssistantAgent(
                name=f"assistant_{conversation_id}",
                model_client=openai_model_client,
                system_message=system_message,
                model_client_stream=True,
            )
```



和AI进行对话

```
代码执行时报错,日志2025-06-05 19:13:12 | INFO     | backend.services.autogen_service:chat_stream:63 | 开始流式聊天 | 对话ID: 5cb91fb6-b59d-4748-ac07-a1e30112da13 | 消息: 帮我写一首诗...
2025-06-05 19:13:12 | ERROR    | backend.api.chat:generate:54 | 流式响应生成失败 | 对话ID: 5cb91fb6-b59d-4748-ac07-a1e30112da13 | 错误: The agent name must be a valid Python identifier.
修复这个问题,另外,这里没有自动清除创建的agent的逻辑,这会不会导致内存泄漏的问题发生,如果存在请修复这个问题
```

AI助手可以分析出问题所在

![image-20250605192933113](./assets/image-20250605192933113.png)



问题1,AI助手修复如下,我认为是正确的

![image-20250605194038681](./assets/image-20250605194038681.png)



关于问题2

这个其实我没想到什么好的思路,但是AI帮我想到的这些震撼了我

他给出的方案

![image-20250605195208646](./assets/image-20250605195208646.png)



![image-20250605195223096](./assets/image-20250605195223096.png)

![image-20250605195259192](./assets/image-20250605195259192.png)

自己测试,解决了对话问题



### 优化

AI对话的窗口比较简陋,功能点也少,需要优化

```
现在生成的页面风格请换成Gemini的风格,https://gemini.google.com/
当前的功能也比较少,相关的功能对比Gemini的相关功能
```

![image-20250605201548256](./assets/image-20250605201548256.png)



### 问题

前端的进程启动一直有问题,杀进程的代码我看到也是有问题的

```
	@# 通过 PID 文件停止
	@if [ -f "frontend.pid" ]; then \
		PID=$$(cat frontend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "✅ 前端主进程已停止 (PID: $$PID)"; \
		else \
			echo "⚠️  PID 文件中的进程不存在"; \
		fi; \
		rm -f frontend.pid; \
	fi
```

这段代码导致一直不能杀掉已经存在前端进程,原因是需要通过找到`frontend.pid`文件来杀掉进程



继续和AI对话

```
当前启动前端的命令一直报错🎨 启动前端服务...
❌ 前端服务启动失败
make: *** [start-frontend] Error 1
但实际服务启动成功
停止前端的服务,请通过ps -ef | grep xxx 的方式查找所有前端相关进行,然后杀掉进程
```

![image-20250605203919252](./assets/image-20250605203919252.png)



AI 助手修复问题

![image-20250605205033251](./assets/image-20250605205033251.png)



### 问题

当前还存在一个问题,就是前端页面如下

![image-20250605205108230](./assets/image-20250605205108230.png)

继续和AI 进行对话

```
现在前端页面打开没有AI对话的界面,只有背景,请帮忙修复这个问题
```

忘了看前端的报错

![image-20250605205609040](./assets/image-20250605205609040.png)

重新把该问题提交给AI

```
Uncaught SyntaxError: The requested module '/node_modules/.vite/deps/@ant-design_icons.js?v=d11622af' does not provide an export named 'MicrophoneOutlined' (at ChatInput.tsx:8:3) 我检查了一下,前端控制台报错,请修复这个问题
```

AI继续修复代码

![image-20250605205653560](./assets/image-20250605205653560.png)



之后运行程序依然报错

![image-20250605212310464](./assets/image-20250605212310464.png)

对于这种问题,AI协助解决后可能还会有问题,此时我们需要的手动解决

源代码中,可以看到,还有两处报错

![image-20250605212443305](./assets/image-20250605212443305.png)

我也很久没有看此处的代码,react的逻辑我虽然明白,但是具体的,我还是需要看官方文档才可以,翻看了官方文档后,找到替代图标

https://ant.design/components/icon

这就有点费事了

![image-20250605212908582](./assets/image-20250605212908582.png)

可以找到很多款,先找到一款近似的

原文是跟声音相似有关的

![image-20250605213053102](./assets/image-20250605213053102.png)

![image-20250605213021932](./assets/image-20250605213021932.png)

现在就可以正常打开界面了



![image-20250606100921465](./assets/image-20250606100921465.png)

问答

![image-20250606101002532](./assets/image-20250606101002532.png)





### 优化

现在上面有个问题就是输出没有段落结构,这个可以使用TS相关的markdown相关库进行优化,继续和AI助手进行对话

```
现在输出到前端的文字不是段落结构,需要进行美化,可以看下前端有没有适合的markdown库进行一下封装
```



![image-20250606101639899](./assets/image-20250606101639899.png)

优化后的效果

![image-20250606102125237](./assets/image-20250606102125237.png)





### 优化

我发现每次AI都会根据我的优化生成一个文档,但是最好把这些文档都放到一个目录下管理更好,继续和AI助手对话

```
生成的相关md文档太多了,我创建了一个docs文档,整理到该目录下进行维护
```

![image-20250606102708454](./assets/image-20250606102708454.png)

优化后,目前已经全部迁移到新的空间内

![image-20250606103501900](./assets/image-20250606103501900.png)

### 优化

帮忙生成的文档,其实之描述了AI对话的功能,不过我想实现的是一个AI自动化测试平台,需要AI助手帮忙重新完成,继续和AI对话

```
我做的是自动化测试平台开发的项目,AI对话只是其中一个模块,请帮忙修改相关md文档
```

![image-20250606104029110](./assets/image-20250606104029110.png)



### 优化

阅读AI助手帮助完成的代码时,发现停止后端服务的逻辑有缺陷,继续和AI对话

```
makefile中停止后端服务的逻辑优化,通过ps -ef | grep xxx的方式查找所有相关后端服务进程,然后杀掉进程
```



### 效果呈献

![image-20250606133013971](./assets/image-20250606133013971.png)

问答

![image-20250606133139202](./assets/image-20250606133139202.png)



下拉功能中,本次完成了清楚对话的功能,其余待实现

![image-20250606133210440](./assets/image-20250606133210440.png)



提交本次代码,完成本次开发任务
