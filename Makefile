# AI Chat 项目管理 Makefile
.PHONY: help install install-backend install-frontend start-backend start-frontend start stop-backend stop-frontend stop clean logs

# 默认目标
help:
	@echo "🚀 AI Chat 项目管理命令"
	@echo ""
	@echo "📦 环境管理:"
	@echo "  make install          - 安装所有依赖"
	@echo "  make install-backend  - 安装后端依赖"
	@echo "  make install-frontend - 安装前端依赖"
	@echo ""
	@echo "🌐 服务管理:"
	@echo "  make start           - 启动所有服务"
	@echo "  make start-backend   - 启动后端服务 (nohup)"
	@echo "  make start-frontend  - 启动前端服务"
	@echo ""
	@echo "🛑 停止服务:"
	@echo "  make stop            - 停止所有服务"
	@echo "  make stop-backend    - 停止后端服务"
	@echo "  make stop-frontend   - 停止前端服务"
	@echo ""
	@echo "🔧 其他:"
	@echo "  make status          - 查看服务状态"
	@echo "  make logs            - 查看后端日志"
	@echo "  make clean           - 清理临时文件"
	@echo "  make force-clean     - 强制清理所有进程"
	@echo "  make force-clean-backend  - 强制清理后端进程"
	@echo "  make force-clean-frontend - 强制清理前端进程"
	@echo "  make show-processes  - 显示所有相关进程"
	@echo "  make test-config     - 测试配置"
	@echo ""
	@echo "📚 Poetry 管理:"
	@echo "  make poetry-shell    - 进入 Poetry 虚拟环境"
	@echo "  make poetry-show     - 显示依赖信息"
	@echo "  make poetry-update   - 更新依赖"

# 安装所有依赖
install: install-backend install-frontend
	@echo "✅ 所有依赖安装完成"

# 安装后端依赖
install-backend:
	@echo "📦 安装后端依赖..."
	@if ! command -v poetry &> /dev/null; then \
		echo "❌ Poetry 未安装，请先安装 Poetry"; \
		echo "💡 安装命令: curl -sSL https://install.python-poetry.org | python3 -"; \
		exit 1; \
	fi
	@if [ -f "pyproject.toml" ]; then \
		poetry install --no-root; \
		echo "✅ 后端依赖安装完成"; \
	else \
		echo "❌ 找不到 pyproject.toml"; \
		exit 1; \
	fi

# 安装前端依赖
install-frontend:
	@echo "📦 安装前端依赖..."
	@if [ -d "frontend" ]; then \
		cd frontend && npm install; \
		echo "✅ 前端依赖安装完成"; \
	else \
		echo "❌ 找不到 frontend 目录"; \
		exit 1; \
	fi

# 启动所有服务
start: start-backend start-frontend
	@echo "🎉 所有服务启动完成"
	@echo "🌐 前端地址: http://localhost:3000"
	@echo "🔧 后端地址: http://localhost:8000"
	@echo "📚 API 文档: http://localhost:8000/docs"

# 启动后端服务 (使用 nohup)
start-backend:
	@echo "🚀 启动后端服务..."
	@if [ -f "backend.pid" ]; then \
		echo "⚠️  后端服务已在运行 (PID: $$(cat backend.pid))"; \
	else \
		nohup poetry run python main.py > backend.log 2>&1 & echo $$! > backend.pid; \
		sleep 2; \
		if [ -f "backend.pid" ] && kill -0 $$(cat backend.pid) 2>/dev/null; then \
			echo "✅ 后端服务启动成功 (PID: $$(cat backend.pid))"; \
		else \
			echo "❌ 后端服务启动失败"; \
			rm -f backend.pid; \
			exit 1; \
		fi \
	fi

# 启动前端服务
start-frontend:
	@echo "🎨 启动前端服务..."
	@if [ -f "frontend.pid" ] && kill -0 $$(cat frontend.pid) 2>/dev/null; then \
		echo "⚠️  前端服务已在运行 (PID: $$(cat frontend.pid))"; \
	else \
		rm -f frontend.pid; \
		cd frontend && nohup npm run dev > ../frontend.log 2>&1 & \
		FRONTEND_PID=$$!; \
		echo $$FRONTEND_PID > ../frontend.pid; \
		echo "🚀 前端服务启动中 (PID: $$FRONTEND_PID)..."; \
		sleep 5; \
		if kill -0 $$FRONTEND_PID 2>/dev/null; then \
			echo "✅ 前端服务启动成功 (PID: $$FRONTEND_PID)"; \
			echo "🌐 前端地址: http://localhost:3000"; \
		else \
			echo "❌ 前端服务启动失败，请查看日志: tail -f frontend.log"; \
			rm -f frontend.pid; \
			exit 1; \
		fi \
	fi

# 停止所有服务
stop: stop-backend stop-frontend
	@echo "🛑 所有服务已停止"

# 停止后端服务
stop-backend:
	@echo "🛑 停止后端服务..."
	@# 首先尝试通过 PID 文件停止
	@if [ -f "backend.pid" ]; then \
		PID=$$(cat backend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "✅ 后端主进程已停止 (PID: $$PID)"; \
		else \
			echo "⚠️  PID 文件中的进程不存在"; \
		fi; \
		rm -f backend.pid; \
	fi
	@# 查找并停止所有相关进程
	@echo "🔍 查找所有后端相关进程..."
	@PIDS=$$(ps -ef | grep -E "([Pp]ython.*main\.py|uvicorn.*main|fastapi.*main)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
	if [ -n "$$PIDS" ]; then \
		echo "发现后端进程: $$PIDS"; \
		for pid in $$PIDS; do \
			if kill -0 $$pid 2>/dev/null; then \
				kill $$pid; \
				echo "✅ 已停止进程 $$pid"; \
			fi; \
		done; \
		sleep 2; \
		REMAINING=$$(ps -ef | grep -E "([Pp]ython.*main\.py|uvicorn.*main|fastapi.*main)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
		if [ -n "$$REMAINING" ]; then \
			echo "⚠️  强制停止剩余进程: $$REMAINING"; \
			for pid in $$REMAINING; do \
				kill -9 $$pid 2>/dev/null; \
			done; \
		fi; \
		echo "✅ 所有后端服务已停止"; \
	else \
		echo "⚠️  未发现运行中的后端服务"; \
	fi

# 停止前端服务
stop-frontend:
	@echo "🛑 停止前端服务..."
	@# 首先尝试通过 PID 文件停止
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
	@# 查找并停止所有相关进程
	@echo "🔍 查找所有前端相关进程..."
	@PIDS=$$(ps -ef | grep -E "(npm run dev|vite|esbuild)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
	if [ -n "$$PIDS" ]; then \
		echo "发现前端进程: $$PIDS"; \
		for pid in $$PIDS; do \
			if kill -0 $$pid 2>/dev/null; then \
				kill $$pid; \
				echo "✅ 已停止进程 $$pid"; \
			fi; \
		done; \
		sleep 2; \
		REMAINING=$$(ps -ef | grep -E "(npm run dev|vite|esbuild)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
		if [ -n "$$REMAINING" ]; then \
			echo "⚠️  强制停止剩余进程: $$REMAINING"; \
			for pid in $$REMAINING; do \
				kill -9 $$pid 2>/dev/null; \
			done; \
		fi; \
		echo "✅ 所有前端服务已停止"; \
	else \
		echo "⚠️  未发现运行中的前端服务"; \
	fi

# 查看后端日志
logs:
	@echo "📋 查看后端日志 (按 Ctrl+C 退出):"
	@if [ -f "backend.log" ]; then \
		tail -f backend.log; \
	else \
		echo "❌ 找不到后端日志文件"; \
	fi

# 测试配置
test-config:
	@echo "🧪 测试配置..."
	@poetry run python test_config.py

# 清理临时文件
clean:
	@echo "🧹 清理临时文件..."
	@rm -f *.pid *.log
	@rm -rf __pycache__ */__pycache__ */*/__pycache__
	@rm -rf .pytest_cache
	@echo "✅ 清理完成"

# 强制清理后端进程
force-clean-backend:
	@echo "🧹 强制清理所有后端进程..."
	@BACKEND_PIDS=$$(ps -ef | grep -E "([Pp]ython.*main\.py|uvicorn.*main|fastapi.*main)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
	if [ -n "$$BACKEND_PIDS" ]; then \
		echo "发现后端进程: $$BACKEND_PIDS"; \
		for pid in $$BACKEND_PIDS; do \
			if ps -p $$pid > /dev/null 2>&1; then \
				echo "强制停止后端进程: $$pid"; \
				kill -9 $$pid 2>/dev/null; \
			fi; \
		done; \
		echo "✅ 所有后端进程已清理"; \
	else \
		echo "⚠️  未发现运行中的后端进程"; \
	fi
	@rm -f backend.pid backend.log
	@echo "✅ 后端进程强制清理完成"

# 强制清理前端进程
force-clean-frontend:
	@echo "🧹 强制清理所有前端进程..."
	@FRONTEND_PIDS=$$(ps -ef | grep -E "(npm run dev|vite|esbuild|node.*frontend)" | grep -v grep | awk '{print $$2}' | tr '\n' ' '); \
	if [ -n "$$FRONTEND_PIDS" ]; then \
		echo "发现前端进程: $$FRONTEND_PIDS"; \
		for pid in $$FRONTEND_PIDS; do \
			if ps -p $$pid > /dev/null 2>&1; then \
				echo "强制停止前端进程: $$pid"; \
				kill -9 $$pid 2>/dev/null; \
			fi; \
		done; \
		echo "✅ 所有前端进程已清理"; \
	else \
		echo "⚠️  未发现运行中的前端进程"; \
	fi
	@rm -f frontend.pid frontend.log
	@echo "✅ 前端进程强制清理完成"

# 强制清理所有进程
force-clean:
	@echo "🧹 强制清理所有相关进程..."
	@$(MAKE) force-clean-backend
	@$(MAKE) force-clean-frontend
	@echo "✅ 所有进程强制清理完成"

# 显示所有相关进程
show-processes:
	@echo "📊 当前运行的相关进程:"
	@echo ""
	@echo "🔧 后端进程:"
	@ps -ef | grep -E "([Pp]ython.*main\.py|uvicorn.*main|fastapi.*main)" | grep -v grep || echo "  无后端进程"
	@echo ""
	@echo "🎨 前端进程:"
	@ps -ef | grep -E "(npm run dev|vite|esbuild)" | grep -v grep || echo "  无前端进程"
	@echo ""
	@echo "📁 PID 文件:"
	@ls -la *.pid 2>/dev/null || echo "  无 PID 文件"

# 检查服务状态
status:
	@echo "📊 服务状态:"
	@if [ -f "backend.pid" ]; then \
		PID=$$(cat backend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "🟢 后端服务运行中 (PID: $$PID)"; \
		else \
			echo "🔴 后端服务已停止"; \
			rm -f backend.pid; \
		fi; \
	else \
		echo "🔴 后端服务未运行"; \
	fi
	@if [ -f "frontend.pid" ]; then \
		PID=$$(cat frontend.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "🟢 前端服务运行中 (PID: $$PID)"; \
		else \
			echo "🔴 前端服务已停止"; \
			rm -f frontend.pid; \
		fi; \
	else \
		echo "🔴 前端服务未运行"; \
	fi

# Poetry 管理命令
poetry-shell:
	@echo "🐚 进入 Poetry 虚拟环境..."
	@poetry shell

poetry-show:
	@echo "📋 显示依赖信息..."
	@poetry show

poetry-update:
	@echo "🔄 更新依赖..."
	@poetry update
	@echo "✅ 依赖更新完成"

# 添加依赖
add-dep:
	@echo "📦 添加新依赖..."
	@if [ -z "$(DEP)" ]; then \
		echo "❌ 请指定依赖名称: make add-dep DEP=package_name"; \
		exit 1; \
	fi
	@poetry add $(DEP)
	@echo "✅ 依赖 $(DEP) 添加完成"

# 添加开发依赖
add-dev-dep:
	@echo "📦 添加开发依赖..."
	@if [ -z "$(DEP)" ]; then \
		echo "❌ 请指定依赖名称: make add-dev-dep DEP=package_name"; \
		exit 1; \
	fi
	@poetry add --group dev $(DEP)
	@echo "✅ 开发依赖 $(DEP) 添加完成"

# 移除依赖
remove-dep:
	@echo "🗑️  移除依赖..."
	@if [ -z "$(DEP)" ]; then \
		echo "❌ 请指定依赖名称: make remove-dep DEP=package_name"; \
		exit 1; \
	fi
	@poetry remove $(DEP)
	@echo "✅ 依赖 $(DEP) 移除完成"
