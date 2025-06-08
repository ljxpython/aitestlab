#!/usr/bin/env python3
"""
AI 测试用例生成模块测试脚本
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """测试模块导入"""
    print("🔍 测试模块导入...")

    try:
        # 测试后端模块导入
        from backend.models.chat import (
            AgentMessage,
            AgentType,
            FileUpload,
            TestCaseRequest,
            TestCaseResponse,
            TestCaseStreamChunk,
        )

        print("✅ 后端模型导入成功")

        from backend.services.testcase_service import testcase_service

        print("✅ 测试用例服务导入成功")

        from backend.api.testcase import router

        print("✅ 测试用例API路由导入成功")

        return True
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_models():
    """测试数据模型"""
    print("\n🔍 测试数据模型...")

    try:
        from datetime import datetime

        from backend.models.chat import (
            AgentMessage,
            AgentType,
            FileUpload,
            TestCaseRequest,
        )

        # 测试 AgentType 枚举
        assert AgentType.REQUIREMENT_AGENT == "requirement_agent"
        assert AgentType.TESTCASE_AGENT == "testcase_agent"
        assert AgentType.USER_PROXY == "user_proxy"
        print("✅ AgentType 枚举测试通过")

        # 测试 FileUpload 模型
        file_upload = FileUpload(
            filename="test.txt",
            content_type="text/plain",
            size=1024,
            content="dGVzdCBjb250ZW50",  # base64 encoded "test content"
        )
        assert file_upload.filename == "test.txt"
        print("✅ FileUpload 模型测试通过")

        # 测试 TestCaseRequest 模型
        request = TestCaseRequest(
            conversation_id="test-123",
            files=[file_upload],
            text_content="测试需求",
            round_number=1,
        )
        assert request.conversation_id == "test-123"
        assert len(request.files) == 1
        print("✅ TestCaseRequest 模型测试通过")

        # 测试 AgentMessage 模型
        message = AgentMessage(
            id="msg-123",
            content="测试消息",
            agent_type=AgentType.REQUIREMENT_AGENT,
            agent_name="requirement_analyst",
            timestamp=datetime.now(),
            conversation_id="test-123",
            round_number=1,
        )
        assert message.agent_type == AgentType.REQUIREMENT_AGENT
        print("✅ AgentMessage 模型测试通过")

        return True
    except Exception as e:
        print(f"❌ 数据模型测试失败: {e}")
        return False


def test_service():
    """测试服务类"""
    print("\n🔍 测试服务类...")

    try:
        from backend.services.testcase_service import TestCaseService

        # 创建服务实例
        service = TestCaseService()
        assert service.max_rounds == 3
        assert isinstance(service.active_conversations, dict)
        print("✅ TestCaseService 初始化测试通过")

        # 测试辅助方法
        from backend.models.chat import FileUpload, TestCaseRequest

        request = TestCaseRequest(
            text_content="测试需求描述",
            files=[
                FileUpload(
                    filename="test.txt",
                    content_type="text/plain",
                    size=100,
                    content="dGVzdA==",
                )
            ],
            round_number=1,
        )

        content = service._prepare_content(request)
        assert "测试需求描述" in content
        assert "上传了 1 个文件" in content
        print("✅ _prepare_content 方法测试通过")

        files_info = service._prepare_files_info(request.files)
        assert len(files_info) == 1
        assert files_info[0]["filename"] == "test.txt"
        print("✅ _prepare_files_info 方法测试通过")

        return True
    except Exception as e:
        print(f"❌ 服务类测试失败: {e}")
        return False


def test_api_routes():
    """测试API路由"""
    print("\n🔍 测试API路由...")

    try:
        from fastapi import FastAPI

        from backend.api.testcase import router

        # 创建测试应用
        app = FastAPI()
        app.include_router(router)

        # 检查路由是否正确注册
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/api/testcase/upload",
            "/api/testcase/generate/stream",
            "/api/testcase/generate",
            "/api/testcase/feedback",
            "/api/testcase/stats",
        ]

        for expected_route in expected_routes:
            if not any(expected_route in route for route in routes):
                print(f"❌ 路由 {expected_route} 未找到")
                return False

        print("✅ API路由注册测试通过")
        return True
    except Exception as e:
        print(f"❌ API路由测试失败: {e}")
        return False


def test_configuration():
    """测试配置"""
    print("\n🔍 测试配置...")

    try:
        # 检查配置文件
        config_file = project_root / "backend" / "conf" / "settings.yaml"
        if not config_file.exists():
            print("❌ 配置文件不存在")
            return False

        print("✅ 配置文件存在")

        # 检查依赖文件
        requirements_file = project_root / "backend" / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file, "r") as f:
                content = f.read()
                if "loguru" in content:
                    print("✅ loguru 依赖已添加")
                else:
                    print("⚠️  loguru 依赖未找到")

        return True
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False


def test_frontend_files():
    """测试前端文件"""
    print("\n🔍 测试前端文件...")

    try:
        frontend_dir = project_root / "frontend" / "src"

        # 检查关键文件
        required_files = [
            "components/FileUpload.tsx",
            "components/AgentMessage.tsx",
            "pages/TestCasePage.tsx",
            "services/testcase.ts",
        ]

        for file_path in required_files:
            full_path = frontend_dir / file_path
            if not full_path.exists():
                print(f"❌ 前端文件不存在: {file_path}")
                return False
            print(f"✅ 前端文件存在: {file_path}")

        return True
    except Exception as e:
        print(f"❌ 前端文件测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 AI 测试用例生成模块测试开始")
    print("=" * 50)

    tests = [
        ("模块导入", test_imports),
        ("数据模型", test_models),
        ("服务类", test_service),
        ("API路由", test_api_routes),
        ("配置", test_configuration),
        ("前端文件", test_frontend_files),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")

    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！AI 测试用例生成模块配置正确")
        print("\n🚀 可以开始使用以下命令启动服务:")
        print("   make install  # 安装依赖")
        print("   make start    # 启动服务")
        print("\n🌐 访问地址:")
        print("   前端: http://localhost:3000")
        print("   后端: http://localhost:8000")
        print("   API文档: http://localhost:8000/docs")
        return True
    else:
        print("❌ 部分测试失败，请检查配置")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
