# 和AI一起开发测试开发平台

已经完成两个测试平台的开发项目了,基本上完全手写,这次我想做一个挑战,使用AI帮我完成测试平台开发的项目,我会将所有的步骤记录到这个文档中,如果你感兴趣,欢迎加我微信和我交流讨论😄

[自动化测试平台](https://www.coder-ljx.cn:7524/user/login)

[AI测试平台](https://www.coder-ljx.cn:3100/login)

个人微信号:

<img src="./assets/image-20250531212549739.png" alt="Description" width="300"/>



## 技术栈

AI技术栈:

```
autogen0.5.7
llamaindex
pydanticai
langchain
```



后端技术栈:

```
Python
fastapi
Tortoise
Aerich
```



前端技术栈:

```
react
ant.designPro
TS
```





代码规范:

```
组件名: 大驼峰命名 (PascalCase)
文件名: 短横线命名 (kebab-case)
变量名: 小驼峰命名 (camelCase)
常量名: 大写下划线 (UPPER_SNAKE_CASE)
后端:使用Black和Isort进行代码格式化
前端:使用Ruff进行代码检查
```

项目部署:

```
git
Nginx
```



## 前提

这并不是一个小白项目,如果完全没有项目经验,跟我一起实践的过程可能会遇到很多困难,希望你在掌握一定的基础后再来跟我操作

相关基础在我的博客中也有提及,也欢迎翻阅😁

[个人博客](https://www.coder-ljx.cn:8825/)

在看我搭建完成测试框架的整个过程,我想你也能明白,AI只是帮我们提高了编码效率,前后端及部署相关的知识,如果你不懂,其实是根本没办法让AI来代替你编码的,这也是我一直践行的一个道理:打铁还需自身硬!



## 说明

这个项目的进度可能需要根据作者的业余时间而定,做不定期更新,技术交流请直接加微信



## AI工具使用

在编写代码的过程中,本次笔者会尽可能的前端使用AI生成,后端大部分手写,小部分使用AI

工具上我们可以使用的有`cursor` `Augment` `Trae` 均可,注意其中有些软件后期是需要付费的,选取一款你认为好用的即可,这里不做过多的评判



## 架构

技术架构图

这部分我应该会在项目将要结束或者主要功能搭建完成后补充,当然具体要实现什么,我心中已经有了



代码结构

```
# 占位,待项目完工
```



## 功能模块

项目会逐步完成下述功能模块的开发:

```
AI对话

RAG知识库

texttosql

AI测试用例智能体模块

接口测试智能体

UI测试智能体

性能测试智能体
```



## 工程搭建记录

[工程搭建记录](./MYWORK.md)



---

## 自动化测试平台 - AI 对话模块

### 🎯 模块定位

AI 对话模块是自动化测试平台的智能助手组件，为测试人员提供：
- 🤖 **测试用例生成**: 基于需求描述自动生成测试用例
- 📋 **测试脚本编写**: 协助编写自动化测试脚本
- 🔍 **问题诊断**: 分析测试失败原因和解决方案
- 📊 **测试报告解读**: 智能解析测试结果和数据
- 💡 **最佳实践建议**: 提供测试策略和优化建议

### ✨ 功能特性

- 🎨 **Gemini 风格界面**: 仿 Google Gemini 的现代化 UI 设计
- 🌈 **动态渐变背景**: 多彩渐变 + 流畅动画效果
- 🚀 **流式输出**: 支持 SSE 协议的实时流式对话
- 🤖 **AutoGen 集成**: 使用 AutoGen 0.5.7 进行智能对话
- 📝 **Markdown 渲染**: 支持代码高亮、表格、列表等丰富格式
- 💬 **智能建议**: 预设测试相关对话建议卡片
- 📱 **响应式设计**: 适配各种屏幕尺寸
- 🗂️ **对话管理**: 历史记录、搜索、重命名、删除
- ⚙️ **个性化设置**: 主题、字体、语言、高级参数
- ⚡ **高性能**: FastAPI 后端 + React 前端

### 📚 相关文档

📖 **[文档中心](./docs/)** - 项目完整文档库

| 分类 | 描述 | 主要文档 |
|------|------|----------|
| **[项目设置](./docs/setup/)** | 环境搭建和架构 | [Makefile 指南](./docs/setup/MAKEFILE_GUIDE.md)、[架构说明](./docs/setup/FACTORY_PATTERN.md) |
| **[开发指南](./docs/development/)** | 开发工具和实现 | [日志系统](./docs/development/LOGGING_GUIDE.md)、[Markdown 渲染](./docs/development/MARKDOWN_RENDERER.md) |
| **[问题排查](./docs/troubleshooting/)** | 故障排除方案 | [AutoGen 修复](./docs/troubleshooting/AUTOGEN_FIXES.md)、[进程管理](./docs/troubleshooting/PROCESS_MANAGEMENT.md)、[后端进程管理](./docs/troubleshooting/BACKEND_PROCESS_MANAGEMENT.md) |
| **[设计文档](./docs/design/)** | UI/UX 设计 | [Gemini 对比](./docs/design/GEMINI_FEATURES_COMPARISON.md)、[测试示例](./docs/design/MARKDOWN_TEST_EXAMPLES.md) |

**快速导航**：
- 🚀 新手入门：[文档中心](./docs/) → [Makefile 指南](./docs/setup/MAKEFILE_GUIDE.md)
- 🛠️ 开发者：[架构说明](./docs/setup/FACTORY_PATTERN.md) → [开发指南](./docs/development/)
- 🔧 问题排查：[故障排除](./docs/troubleshooting/) → [日志调试](./docs/development/LOGGING_GUIDE.md)

### 🏗️ 项目结构

```
AutoTestPlatform-AI-Chat/
├── main.py           # AI 对话模块启动入口
├── backend/          # FastAPI 后端服务
│   ├── __init__.py   # 工厂模式应用创建
│   ├── api/          # API 路由
│   │   └── chat.py   # 对话 API 接口
│   ├── models/       # 数据模型
│   │   └── chat.py   # 对话相关模型
│   ├── services/     # 业务逻辑
│   │   └── autogen_service.py # AutoGen 服务
│   ├── core/         # 核心模块
│   │   ├── init_app.py      # 应用初始化
│   │   ├── exceptions.py    # 自定义异常
│   │   ├── logger.py        # 日志配置
│   │   └── config_validator.py # 配置验证
│   └── conf/         # 配置文件
│       └── settings.yaml    # 应用配置
├── frontend/         # React 前端界面
│   ├── src/
│   │   ├── components/  # UI 组件
│   │   │   ├── ChatMessage.tsx     # 消息组件
│   │   │   ├── ChatInput.tsx       # 输入组件
│   │   │   ├── MarkdownRenderer.tsx # Markdown 渲染
│   │   │   ├── ConversationHistory.tsx # 对话历史
│   │   │   └── SettingsPanel.tsx   # 设置面板
│   │   ├── pages/      # 页面
│   │   │   └── ChatPage.tsx        # 主对话页面
│   │   ├── services/   # API 服务
│   │   │   └── api.ts  # API 接口
│   │   └── types/      # 类型定义
│   │       └── chat.ts # 对话类型
│   └── package.json
├── examples/         # AutoGen 示例
├── docs/            # 项目文档
│   ├── setup/       # 项目设置文档
│   ├── development/ # 开发指南文档
│   ├── troubleshooting/ # 问题排查文档
│   └── design/      # 设计文档
└── Makefile         # 项目管理脚本
```

### 🚀 快速开始

#### 方式一：使用启动脚本（推荐）

```bash
# 安装依赖
make install

# 启动应用
make start

# 停止应用
make stop
```

#### 方式二：手动启动

**启动后端：**
```bash
# 在项目根目录下运行
poetry install
poetry run python main.py
```

**启动前端：**
```bash
cd frontend
npm install
npm run dev
```

### 🌐 访问地址

- **前端应用**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

### 🔧 配置说明

在 `backend/conf/settings.yaml` 中配置 AI 对话模块：

```yaml
test:
  # AI 模型配置 - 用于测试用例生成和问题诊断
  aimodel:
    model: "deepseek-chat"          # 推荐使用 DeepSeek 或 GPT-4
    base_url: "https://api.deepseek.com/v1"
    api_key: "your-api-key-here"    # 请替换为您的 API Key

  # AutoGen 服务配置 - 智能对话管理
  autogen:
    max_agents: 100        # 最大 Agent 数量
    cleanup_interval: 3600 # 清理检查间隔（秒）
    agent_ttl: 7200       # Agent 生存时间（秒）
```

### 🧪 测试配置

运行测试脚本验证配置是否正确：

```bash
python test_config.py
```

如果看到 "🎉 所有组件测试通过！" 说明配置正确。

### 📋 Makefile 命令

详细的 Makefile 命令说明请参考：[Makefile 使用指南](./MAKEFILE_GUIDE.md)

**常用命令**：
```bash
make help           # 查看所有命令
make install        # 安装所有依赖
make start          # 启动所有服务
make status         # 查看服务状态
make stop           # 停止所有服务
make logs           # 查看日志
```

### 📚 Poetry 依赖管理

详细的 Poetry 管理命令请参考：[Makefile 使用指南](./MAKEFILE_GUIDE.md#poetry-依赖管理)

**常用命令**：
```bash
make add-dep DEP=requests      # 添加依赖
make add-dev-dep DEP=pytest   # 添加开发依赖
make remove-dep DEP=requests  # 移除依赖
make poetry-show              # 查看依赖信息
```

### 🛠️ 环境要求

- **Python**: 3.8+
- **Poetry**: 1.4+ (Python 依赖管理)
- **Node.js**: 16+
- **npm**: 8+

**Poetry 安装：**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 🔍 日志和调试

详细的日志系统使用请参考：[日志系统使用指南](./LOGGING_GUIDE.md)

**快速使用**：
```bash
make logs                    # 查看实时日志
tail -f logs/app.log        # 查看应用日志
tail -f logs/error.log      # 查看错误日志
make status                 # 查看服务状态
```

**日志配置**：
```yaml
# backend/conf/settings.yaml
LOG_LEVEL: "INFO"           # 日志级别
LOG_FILE: "ai_chat.log"     # 日志文件名
```

### 🎯 已实现功能

#### 核心对话功能
- ✅ **实时流式对话**: 支持与 AI 进行实时对话交流
- ✅ **Markdown 渲染**: 支持代码高亮、表格、列表等格式
- ✅ **对话历史管理**: 保存、搜索、重命名对话记录
- ✅ **智能建议**: 预设测试相关的对话模板

#### 测试辅助功能
- ✅ **测试用例生成**: 基于需求描述生成测试用例
- ✅ **代码片段生成**: 生成自动化测试脚本代码
- ✅ **问题诊断**: 分析测试失败原因
- ✅ **最佳实践建议**: 提供测试策略建议

#### 用户体验
- ✅ **响应式界面设计**: 适配桌面和移动端
- ✅ **错误处理和重试**: 完善的异常处理机制
- ✅ **打字机效果**: 流畅的文字显示动画
- ✅ **消息操作**: 复制、点赞、重新生成等功能

### 🏗️ 架构设计

详细的架构说明请参考：[工厂模式架构说明](./FACTORY_PATTERN.md)

**核心特性**：
- 🏭 **工厂模式**: 模块化的 FastAPI 应用创建
- 🔄 **生命周期管理**: 完整的应用启动和关闭流程
- 🛡️ **异常处理**: 统一的异常处理机制
- 📝 **日志系统**: 基于 loguru 的完整日志方案
- ⚙️ **配置管理**: 灵活的配置验证和管理

---

## 📖 完整文档索引

📋 **[文档导航中心](./docs/)** - 按需求和角色快速查找文档

### 🗂️ 文档目录结构
```
docs/
├── setup/          # 项目设置和架构
├── development/    # 开发指南和技术实现
├── troubleshooting/ # 问题排查和修复
└── design/         # 设计文档和测试
```

### 🚀 快速导航
- **新手入门**: 阅读本 README → [文档中心](./docs/) → [Makefile 指南](./docs/setup/MAKEFILE_GUIDE.md)
- **架构了解**: [工厂模式架构说明](./docs/setup/FACTORY_PATTERN.md)
- **问题调试**: [日志系统使用指南](./docs/development/LOGGING_GUIDE.md)
- **深入开发**: [开发指南目录](./docs/development/)
- **故障排除**: [问题排查目录](./docs/troubleshooting/)

### 📋 项目记录
- [工程搭建记录](./MYWORK.md) - 项目搭建过程记录
- [项目定位调整](./docs/PROJECT_REPOSITIONING.md) - 从通用 AI 助手调整为测试平台模块
