

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

这里先说一下我的思路,问题的出在这里,这里的`name=f"assistant_{conversation_id}"`命名不符合Python的语法,而且使用完成后我也没看到销毁agent的地方,这里应该有隐患,可能导致内存泄漏发生(尽管`clear_conversation`函数中有销毁agent的逻辑)也就是说我还需要让服务可以自己回收销毁agent

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

<img src="./assets/image-20250606133210440.png" alt="image-20250606133210440" style="zoom:50%;" />



提交代码,完成本次开发任务



## 用例评审智能体初步搭建(2025年06月08日)

上一次开发了一个简单的AI对话模块,有一些待开发的小模块没有开发完成(文件上传,历史记录),这些放在后面优化

这一次,我们来开发一个用例评生成智能体,主要的需求可以简述为:

1. 支持用户上传一个文件或者文字,然后对其进行解析,给出相应的测试用例
2. 之后AI对用例进行评审,然后修改,前端展示用例
3. 用户给出反馈和是否同意,最多三次意见
4. 最终给出用例,返回到前端

要求:明确显示输出的内容是哪个智能体发出的（做成时间轴或者折叠效果）

优化: 后期支持把相关内容进行落库



和AI进行对话

```
在当前代码的基础上,完成AI用例模块开发:
1. 前端界面，界面风格参考 Gemini，界面风格要炫酷，代码放到frontend目录
2. 后端基于Fastapi提供接口，使用sse协议进行流式输出，代码放到backend目录
3. 智能体开发技术:
	使用autogen0.5.7 实现与大模型对话,具体的例子可以参考:
	https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html
	使用RoundRobinGroupChat和SingleThreadedAgentRuntime来实现
	本地demo参考:examples/multi_agent.py examples/team.py examples/topic.py examples/agent_call_tools.py

4. 业务逻辑:
	前端支持上传文件\照片\文本,发送给需求获取智能体
	需求获取智能体将内容解析后发送给用例生成智能体
	多次和用户交流(最多三次),直到用户同意
	将结果结构化展示给用户,之后结束
要求:明确显示输出的内容是哪个智能体发出的（做成时间轴或者折叠效果）


```



![image-20250608170838776](./assets/image-20250608170838776.png)

AI解读后的逻辑:

![image-20250608171204234](./assets/image-20250608171204234.png)



启动AI生成的代码

![image-20250608172947624](./assets/image-20250608172947624.png)



### 优化

当前把AI对话模块弄没了,需要优先修复该问题

继续和AI进行对话

```
AI对话模块和AI用例生成模块是两个独立的模块,请不要混在一起,请还原之前的代码,然后重新完成上述功能,在首页有两个功能的入口
```

![image-20250608173358739](./assets/image-20250608173358739.png)



### 优化

![image-20250608174650268](./assets/image-20250608174650268.png)

用例生成界面

![image-20250608181048224](./assets/image-20250608181048224.png)

如上的用例生成界面还是比较难看的

并且我看了服务端的代码

和用户对话且和终止的部分没有使用Autogen的的代码,如下

我应该告诉他具体使用Autogen的哪个相关代码,且给到一个demo

![image-20250608181251080](./assets/image-20250608181251080.png)

### 优化

现在一个一个优化,首先优化一下前端的页面

继续和AI进行对话

```
前端优化,进入对应模块后:最好有一个左侧的导航栏,可以指定进入到对应的模块,且导航栏可以折叠到左侧
```

![image-20250608181715280](./assets/image-20250608181715280.png)



![image-20250608182842901](./assets/image-20250608182842901.png)



生成后的代码,配色上我感觉还有不少的问题,且折叠的按钮我想固定到页面的最下角,继续优化

![image-20250608183127182](./assets/image-20250608183127182.png)

### 优化

继续和AI进行对话

```
1. 侧边栏的配色和主要内容区的颜色差异很大,不太美观,请修复,页面尽可能的美观简约高大上
2. 折叠后的按钮放在页面的最下角,不管如何滑动,始终固定在最下角
3. 折叠后AI模块的标题还能看到,不美观
4. 增加一个上方导航栏,在导航栏的右侧为我的git代码仓库,链接地址为:https://github.com/ljxpython/aitestlab和用户的头像

```

![image-20250608184010606](./assets/image-20250608184010606.png)



![image-20250608185745611](./assets/image-20250608185745611.png)

### 优化

优化后的配色如下,变得更加难看了,且侧边栏的折叠功能生成的也不好

![image-20250608185925514](./assets/image-20250608185925514.png)

继续和AI进行对话优化

```
折叠侧边栏的按钮需要固定放到页面的侧边栏的最下面
整体的配色要进行统一,要高大上且美观
用户的功能暂未实现,暂时先取消该按钮
导航栏的AI测试平台标题和侧边栏的标题内容重复了
```

![image-20250608190428018](./assets/image-20250608190428018.png)



### 优化

上述优化后的前端展示如下:

![image-20250608192043435](./assets/image-20250608192043435.png)



看着还是很难看,需要继续优化



参考我之前设计的页面,让AI对应着生成

![image-20250608191931038](./assets/image-20250608191931038.png)

```
请参考图片中的平台进行设计
风格相似
折叠按钮跟随侧边栏,按照图中展示的生成
侧边栏选中后,不要变成深色
```

![image-20250608192430367](./assets/image-20250608192430367.png)

![image-20250608193139414](./assets/image-20250608193139414.png)



![image-20250608193637580](./assets/image-20250608193637580.png)



### 优化



```
侧边栏优化:
	1. 侧边栏的AI图标放到导航栏标题左侧,侧边栏的标题去掉
	2. 侧边栏 一级标题二级标题增加折叠功能
	3. 当页面滑动时,侧边栏不随这页面滑动

```

![image-20250608195120247](./assets/image-20250608195120247.png)



![image-20250608200243610](./assets/image-20250608200243610.png)





### 优化

![image-20250608200100810](./assets/image-20250608200100810.png)

优化后,可以发现存在一个小的问题,导航栏会跟着移动,需要优化

继续和AI进行对话

```
导航栏优化:
	当页面滑动时,侧边栏不随页面滑动
```



![image-20250608201503761](./assets/image-20250608201503761.png)



![image-20250608201423632](./assets/image-20250608201423632.png)



### 优化

发现到现在还没有一个用户界面,直接使用AI设计一个前端和后端及用户系统

继续和AI对话

```
设计平台用户系统:
	1. 完成前端登录页面
	2. 后端fastapi+Tortoise+Aerich
	3. 数据库暂时选用sqlite,预先生成一个账户:test 密码 test的用户,登录页面提示该用户名和密码
	4. 导航栏右侧增加用户的图标,放到该图标上,可以下拉进入用户详情界面,可以修改用户信息

```





中途我看AI卡在安装用例的地方

我手动执行安装

```
 poetry add tortoise-orm aerich passlib python-jose bcrypt
```



![image-20250608205350768](./assets/image-20250608205350768.png)



![image-20250608205314474](./assets/image-20250608205314474.png)



![image-20250608212104723](./assets/image-20250608212104723.png)

### 解决问题

执行代码会发现报错

backend/core/security.py

这里的问题是没有根据`backend/conf` 中引入环境变量

![image-20250608212137938](./assets/image-20250608212137938.png)

继续和AI进行对话

```
1. 请修复backend/core/security.py中的from backend.core.config import settings问题,我希望使用backend/conf/config.py的settings来完成环境变量的使用,可以查阅目录下其他代码对其的使用
2. 整理docs目录下的markdown文件,使其调理清晰
```



![image-20250608213336498](./assets/image-20250608213336498.png)

AI修复这里的问题会报错,手动修复

![image-20250608215838795](./assets/image-20250608215838795.png)

backend/core/database.py,这里就需要详细的了解`tortoise` 的使用方式了,可以查看`tortoise`的官网学习一下

https://tortoise.github.io/

修复如下:

```
# Tortoise ORM 配置
TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": [
                "backend.models",
                "aerich.models"
            ],
            "default_connection": "default",
        },
    },
}
```

再次启动报错,` 创建默认用户失败: default_connection for the model <class 'backend.models.user.User'> cannot be None`

![image-20250608220209115](./assets/image-20250608220209115.png)

这一块的修改需要了解Python相关库的使用,和AI进行对话

```
backend/core/init_app.py 和  backend/core/database.py代码有重合的部分,代码合并到database.py中,且一些目录变量使用backend/conf/constants.py定义好的变量,比如from backend.conf.constants import backend_path
DATABASE_URL = os.path.join(backend_path, "data", "aitestlab.db")
将受到影响的代码进行修改
```

![image-20250608234541536](./assets/image-20250608234541536.png)

![image-20250608234501162](./assets/image-20250608234501162.png)



AI助手生成的代码报错

![image-20250608234446045](./assets/image-20250608234446045.png)



阅读AI的代码,发现问题,修复如下

![image-20250608235148731](./assets/image-20250608235148731.png)



此时再次启动应用,已经OK

![image-20250608235223147](./assets/image-20250608235223147.png)



登陆界面:

![image-20250608235423675](./assets/image-20250608235423675.png)



顺利登陆

![image-20250608235456574](./assets/image-20250608235456574.png)

接下来我们优化AI用例生成模块

### 优化

![image-20250608235747785](./assets/image-20250608235747785.png)



我之前做的测试智能体还是比较好看的,因此我直接将相关的模版给到AI助手

![image-20250609000018969](./assets/image-20250609000018969.png)



```
AI用例智能体的前端请仿照图中平台的进行优化
页面的左边为步骤及实时展示的结果,右侧展示用例根据内容生成的用例
```



![image-20250609001059913](./assets/image-20250609001059913.png)



![image-20250609001416441](./assets/image-20250609001416441.png)

前端效果:

![image-20250609001611595](./assets/image-20250609001611595.png)



效果还是不错的,有些颜色比较特异的地方我们最后优化,接下来我们优化一下后端的代码

### 问题

现在测试用例模块没有真正的和后端进行联调

![image-20250609002619329](./assets/image-20250609002619329.png)

继续和AI进行对话

```
当前测试用例模块前端没有和后端进行交互,请阅读后端的相应代码,打通前后端
```

![image-20250609003204385](./assets/image-20250609003204385.png)

![image-20250609003637476](./assets/image-20250609003637476.png)

启动后查看

![image-20250609003953565](./assets/image-20250609003953565.png)

查看后端代码:

流式输出这段代码中,我的预期是,等待用户输出使用`UserProxyAgent` 函数,用户同意和最大次数3次为`RoundRobinGroupChat`中的ExternalTermination TextMentionTermination

![image-20250609004056222](./assets/image-20250609004056222.png)

![image-20250609004310644](./assets/image-20250609004310644.png)

修复这部分的代码,我先使用一段已有的代码,让AI来仿写,如果不行,我再手写

### 问题修复

再次和AI进行对话

```
参考examples/testcase_agents.py中的逻辑,完成AI测试用例生成的后端代码,和用户交互的代码   team = RoundRobinGroupChat([testcase_generator_agent, user_proxy], termination_condition=termination_en | termination_zh, )
终止条件为询问用户三次或者用户回复同意,终止条件的代码参考:https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tutorial/termination.html
前端用例解析文件的代码参考examples/requirement_agents.py中的RequirementAcquisitionAgent

后端逻辑:
解析文件(如果存在)和用户描述的需求重点 -> 生成用例 -> 和用户交互 -> 智能体评审优化输出最终版
这个过程,每个智能体的输出的内容都返回到前端,且告知哪个智能体的输出
前端后端可以调通
代码做好注释及log打印
```



### 杂项优化

继续和AI进行对话

```
删除前端的无用页面:滚动测试和帮助
增加数据库的迁移和使用,使用Aerich
对docs进行整理,docs文档根目录下留下一个readme文档,其余分门别类的放到合适的文件夹内
根据当前开发的内容,重新对根目录下README.md进行优化
根目录下的测试文件放到test目录下
```

![image-20250609020822304](./assets/image-20250609020822304.png)



### 优化

再次优化,和AI对话

```
前端登录界面去掉账户名和密码的提示
去掉侧边栏的帮助和滚动测试
修复侧边栏的折叠按钮,右边未展示的问题
根据当前开发的内容,重新对根目录下README.md进行优化,优化内容放到README.md下的工程搭建记录章节后,上面的内容不要删除,整合当前开发的内容

```





### 优化

根据改动重新生成readme文档



```
增加数据库的迁移和使用,使用Aerich
对docs进行整理,docs文档根目录下留下一个readme文档,其余分门别类的放到合适的文件夹内
根据当前开发的内容,重新对根目录下README.md进行优化
根目录下的测试文件放到test目录下

```

内部逻辑优化

```
终止条件的部分参考下面也: https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tutorial/termination.html
```



对文档进行整理,docs文档留下一个readme文档,其余分门别类的放到各个文件夹内

readme文档也是增加相应的功能



测试文件夹放到一个测试目录下
