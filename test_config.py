#!/usr/bin/env python3
"""
测试配置是否正确
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.conf.config import settings

    print("✅ 配置加载成功")
    print(f"模型: {settings.aimodel.model}")
    print(f"API 地址: {settings.aimodel.base_url}")
    print(f"API Key: {settings.aimodel.api_key[:10]}...")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    sys.exit(1)

try:
    from backend.models.chat import ChatRequest, ChatResponse, StreamChunk

    print("✅ 模型导入成功")
except Exception as e:
    print(f"❌ 模型导入失败: {e}")
    sys.exit(1)

try:
    from backend.services.autogen_service import autogen_service

    print("✅ AutoGen 服务导入成功")
except Exception as e:
    print(f"❌ AutoGen 服务导入失败: {e}")
    sys.exit(1)

try:
    from backend import app

    print("✅ FastAPI 应用导入成功")
except Exception as e:
    print(f"❌ FastAPI 应用导入失败: {e}")
    sys.exit(1)

print("\n🎉 所有组件测试通过！")
