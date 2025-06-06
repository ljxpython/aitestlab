"""
这个模块将常量固定
框架项目的顶层目录
一定要注意，所有功能最好不好耦合，各个模块单独运行，有利于系统的良好运行
只有该模块，对相关环境的路径进行明确，与其他模块进行必要的联系
"""

import os
from pathlib import Path

# 根目录
root_path = Path(__file__).parent.parent.parent.absolute()
# 后端目录
backend_path = root_path / "backend"
# 前端目录
frontend_path = root_path / "frontend"
# 日志目录
log_path = root_path / "logs"
# 例子目录
examples_path = root_path / "examples"

if __name__ == "__main__":
    print(root_path)
    print(backend_path)
    print(frontend_path)
    print(log_path)
