# 开发环境搭建指南

## 系统要求

### 基础环境
- **Node.js**: 16.0+
- **Python**: 3.8+
- **Git**: 2.0+
- **操作系统**: macOS / Linux / Windows

### 推荐工具
- **IDE**: VS Code / PyCharm / WebStorm
- **终端**: iTerm2 (macOS) / Windows Terminal
- **包管理**: npm / yarn (前端), pip / poetry (后端)

## 环境搭建步骤

### 1. 克隆项目
```bash
git clone https://github.com/ljxpython/aitestlab.git
cd aitestlab
```

### 2. 后端环境配置

#### 创建虚拟环境
```bash
cd backend

# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 或使用 conda
conda create -n aitestlab python=3.8
conda activate aitestlab
```

#### 安装依赖
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 或使用 poetry
poetry install
```

#### 初始化数据库
```bash
# 运行数据库初始化脚本
python init_db.py

# 验证数据库创建
ls -la data/  # 应该看到 aitestlab.db 文件
```

### 3. 前端环境配置

#### 安装 Node.js 依赖
```bash
cd frontend

# 使用 npm
npm install

# 或使用 yarn
yarn install

# 或使用 pnpm
pnpm install
```

#### 配置环境变量
创建 `frontend/.env.local` 文件：
```env
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_ENV=development
REACT_APP_VERSION=1.0.0
```

### 4. 配置文件设置

#### 后端配置
编辑 `backend/conf/settings.yaml`：
```yaml
test:
  # AI模型配置
  aimodel:
    model: "deepseek-chat"
    base_url: "https://api.deepseek.com/v1"
    api_key: "your-deepseek-api-key"  # 替换为实际API密钥

  # JWT配置
  SECRET_KEY: "your-secret-key-change-in-production-aitestlab-2024"
  ACCESS_TOKEN_EXPIRE_MINUTES: 1440  # 24小时

  # 数据库配置
  DATABASE_URL: "sqlite://./data/aitestlab.db"

  # 日志配置
  LOG_LEVEL: "DEBUG"
  LOG_FILE: "./logs/app.log"
```

#### API密钥获取
1. **DeepSeek API**:
   - 访问 https://platform.deepseek.com/
   - 注册账号并获取API密钥
   - 将密钥填入配置文件

2. **其他AI服务** (可选):
   - OpenAI: https://platform.openai.com/
   - Claude: https://console.anthropic.com/

## 启动开发服务

### 使用 Makefile (推荐)
```bash
# 查看所有可用命令
make help

# 启动所有服务
make start

# 单独启动后端
make backend

# 单独启动前端
make frontend

# 停止所有服务
make stop

# 重启服务
make restart
```

### 手动启动

#### 后端服务
```bash
cd backend

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 启动 FastAPI 服务
uvicorn __init__:app --host 0.0.0.0 --port 8000 --reload

# 或使用 Python 直接运行
python -m uvicorn __init__:app --host 0.0.0.0 --port 8000 --reload
```

#### 前端服务
```bash
cd frontend

# 启动 React 开发服务器
npm start

# 或使用 yarn
yarn start
```

### 验证服务启动

#### 访问地址
- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **API重定向文档**: http://localhost:8000/redoc

#### 健康检查
```bash
# 检查后端服务
curl http://localhost:8000/health

# 检查前端服务
curl http://localhost:3000
```

## 开发工具配置

### VS Code 配置

#### 推荐扩展
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next",
    "ms-vscode.vscode-json"
  ]
}
```

#### 工作区设置
创建 `.vscode/settings.json`：
```json
{
  "python.defaultInterpreterPath": "./backend/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### Git 配置

#### Git Hooks
创建 `.git/hooks/pre-commit`：
```bash
#!/bin/sh
# 代码格式化检查
echo "Running pre-commit checks..."

# Python 代码检查
cd backend
black --check .
isort --check-only .

# TypeScript 代码检查
cd ../frontend
npm run lint
npm run type-check

echo "Pre-commit checks passed!"
```

#### .gitignore 补充
确保以下内容在 `.gitignore` 中：
```gitignore
# 环境变量
.env
.env.local
.env.production

# 数据库
*.db
*.sqlite

# 日志文件
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# 操作系统
.DS_Store
Thumbs.db
```

## 常见问题解决

### 端口冲突
```bash
# 查看端口占用
lsof -i :3000  # 前端端口
lsof -i :8000  # 后端端口

# 杀死占用进程
kill -9 <PID>

# 或使用不同端口启动
PORT=3001 npm start  # 前端
uvicorn __init__:app --port 8001  # 后端
```

### 依赖安装失败
```bash
# 清理缓存
npm cache clean --force  # 前端
pip cache purge          # 后端

# 重新安装
rm -rf node_modules package-lock.json
npm install

rm -rf venv
python -m venv venv
pip install -r requirements.txt
```

### 数据库问题
```bash
# 重新初始化数据库
rm -f backend/data/aitestlab.db
cd backend && python init_db.py

# 检查数据库内容
sqlite3 backend/data/aitestlab.db ".tables"
sqlite3 backend/data/aitestlab.db "SELECT * FROM users;"
```

### 权限问题
```bash
# macOS/Linux 权限修复
chmod +x scripts/*.sh
sudo chown -R $USER:$USER .

# Windows 权限问题
# 以管理员身份运行终端
```

## 开发最佳实践

### 代码规范
- **Python**: 遵循 PEP 8，使用 Black 格式化
- **TypeScript**: 遵循 ESLint 规则，使用 Prettier 格式化
- **提交信息**: 使用约定式提交格式

### 分支管理
```bash
# 创建功能分支
git checkout -b feature/user-authentication

# 提交代码
git add .
git commit -m "feat: 添加用户认证功能"

# 推送分支
git push origin feature/user-authentication
```

### 调试技巧
```bash
# 后端调试
python -m pdb script.py

# 前端调试
# 使用浏览器开发者工具
# React DevTools 扩展
```

## 下一步

环境搭建完成后，建议阅读：
- [API开发指南](./API_GUIDE.md)
- [前端开发指南](./FRONTEND_GUIDE.md)
- [数据库设计](./DATABASE_GUIDE.md)
- [测试指南](./TESTING_GUIDE.md)

## 获取帮助

如果遇到问题：
1. 查看 [故障排查文档](../troubleshooting/README.md)
2. 搜索 [GitHub Issues](https://github.com/ljxpython/aitestlab/issues)
3. 提交新的 Issue 或联系维护者
