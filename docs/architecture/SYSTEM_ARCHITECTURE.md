# 系统架构设计

## 整体架构

AI 测试平台采用前后端分离的架构设计，具有良好的可扩展性和维护性。

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 (React)   │    │  后端 (FastAPI)  │    │  AI服务 (AutoGen) │
│                 │    │                 │    │                 │
│ • 用户界面      │◄──►│ • API接口       │◄──►│ • 智能对话      │
│ • 状态管理      │    │ • 业务逻辑      │    │ • 用例生成      │
│ • 路由管理      │    │ • 数据访问      │    │ • 智能分析      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   浏览器客户端   │    │  SQLite 数据库   │    │   外部AI服务    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 前端架构

### 技术选型
- **React 18**: 现代化前端框架
- **TypeScript**: 类型安全开发
- **Ant Design**: 企业级UI组件
- **React Router**: 单页应用路由

### 目录结构
```
frontend/src/
├── components/          # 通用组件
│   ├── SideNavigation.tsx
│   ├── TopNavigation.tsx
│   └── PageLayout.tsx
├── pages/              # 页面组件
│   ├── HomePage.tsx
│   ├── ChatPage.tsx
│   ├── TestCasePage.tsx
│   ├── LoginPage.tsx
│   └── UserProfilePage.tsx
├── services/           # API服务
│   ├── auth.ts
│   ├── chat.ts
│   └── testcase.ts
├── types/              # 类型定义
├── utils/              # 工具函数
└── App.tsx             # 应用入口
```

### 状态管理
- **本地状态**: React Hooks (useState, useEffect)
- **全局状态**: Context API + localStorage
- **服务端状态**: 直接API调用

## 后端架构

### 技术选型
- **FastAPI**: 高性能异步Web框架
- **Tortoise ORM**: 异步数据库ORM
- **SQLite**: 轻量级关系数据库
- **JWT**: 无状态用户认证
- **Loguru**: 结构化日志

### 目录结构
```
backend/
├── api/                # API路由
│   ├── auth.py
│   ├── chat.py
│   └── testcase.py
├── core/               # 核心功能
│   ├── init_app.py
│   ├── security.py
│   ├── database.py
│   └── deps.py
├── models/             # 数据模型
│   ├── user.py
│   └── auth.py
├── services/           # 业务服务
│   ├── auth_service.py
│   ├── chat_service.py
│   └── testcase_service.py
├── conf/               # 配置文件
│   ├── config.py
│   └── settings.yaml
└── __init__.py         # 应用工厂
```

### 设计模式
- **工厂模式**: 应用初始化
- **依赖注入**: 服务管理
- **分层架构**: API → Service → Model

## 数据库设计

### 用户系统
```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    avatar_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- 用户会话表
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

## AI服务架构

### AutoGen集成
```python
# AI智能体配置
agents = {
    "assistant": {
        "model": "deepseek-chat",
        "system_message": "测试助手角色定义",
        "max_tokens": 2000
    },
    "user_proxy": {
        "human_input_mode": "NEVER",
        "code_execution_config": False
    }
}
```

### 服务流程
1. **用户输入** → 前端收集用户需求
2. **请求处理** → 后端验证和预处理
3. **AI调用** → AutoGen智能体对话
4. **结果处理** → 格式化和优化输出
5. **响应返回** → 流式或批量返回结果

## 安全架构

### 认证授权
- **JWT令牌**: 无状态认证
- **密码哈希**: SHA256加密存储
- **会话管理**: 令牌过期和刷新
- **权限控制**: 基于角色的访问控制

### 数据安全
- **输入验证**: Pydantic模型验证
- **SQL注入防护**: ORM参数化查询
- **XSS防护**: 前端输出转义
- **CORS配置**: 跨域请求控制

## 部署架构

### 开发环境
```
┌─────────────────┐    ┌─────────────────┐
│  前端开发服务器  │    │  后端开发服务器  │
│  localhost:3000 │    │  localhost:8000 │
│                 │    │                 │
│  • React Dev    │    │  • FastAPI      │
│  • Hot Reload   │    │  • Auto Reload  │
└─────────────────┘    └─────────────────┘
```

### 生产环境
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx 反向代理 │    │   应用服务器     │    │   数据库服务器   │
│                 │    │                 │    │                 │
│  • 静态文件服务  │    │  • FastAPI      │    │  • SQLite/      │
│  • 负载均衡     │    │  • Gunicorn     │    │    PostgreSQL   │
│  • SSL终止      │    │  • 多进程       │    │  • 备份策略     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 性能优化

### 前端优化
- **代码分割**: React.lazy + Suspense
- **缓存策略**: Service Worker
- **资源优化**: 图片压缩、CDN加速
- **渲染优化**: Virtual DOM、memo

### 后端优化
- **异步处理**: FastAPI异步特性
- **数据库优化**: 索引、查询优化
- **缓存机制**: Redis缓存
- **连接池**: 数据库连接复用

## 监控和日志

### 日志系统
```python
# 结构化日志
logger.info("用户登录", extra={
    "user_id": user.id,
    "ip_address": request.client.host,
    "user_agent": request.headers.get("user-agent")
})
```

### 监控指标
- **系统指标**: CPU、内存、磁盘
- **应用指标**: 响应时间、错误率
- **业务指标**: 用户活跃度、功能使用率

## 扩展性设计

### 水平扩展
- **无状态设计**: JWT认证
- **微服务架构**: 功能模块分离
- **负载均衡**: 多实例部署

### 功能扩展
- **插件系统**: 模块化设计
- **API版本控制**: 向后兼容
- **配置管理**: 环境变量配置

## 相关文档

- [AI模块设计](./AI_MODULES.md)
- [用户系统设计](./USER_SYSTEM.md)
- [API接口文档](../development/API_GUIDE.md)
- [部署指南](../deployment/DEPLOYMENT_GUIDE.md)
