#!/bin/bash

echo "🧪 测试 Makefile 功能"

# 检查 make 命令是否可用
if ! command -v make &> /dev/null; then
    echo "❌ make 命令未找到，请安装 make"
    exit 1
fi

echo "✅ make 命令可用"

# 测试 help 命令
echo "📋 测试 help 命令..."
make help

echo ""
echo "🎉 Makefile 测试完成！"
echo ""
echo "💡 使用建议："
echo "1. 首次使用：make install"
echo "2. 启动服务：make start"
echo "3. 查看状态：make status"
echo "4. 停止服务：make stop"
