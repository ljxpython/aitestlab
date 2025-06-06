"""
    Dynaconf 初始配置
"""

from pathlib import Path

from dynaconf import Dynaconf

# 获取 backend/conf 目录的路径
root_path = Path(__file__).parent.absolute()

settings = Dynaconf(
    root_path=str(root_path),  # 解决 PyCharm OSError: Starting path not found
    envvar_prefix="DYNACONF",
    settings_files=["settings.yaml", "settings.local.yaml"],
    environments=True,
    load_dotenv=True,
    env="test",
)

# 添加应用默认配置
if not hasattr(settings, "APP_TITLE"):
    settings.APP_TITLE = "AI Chat API"
if not hasattr(settings, "APP_DESCRIPTION"):
    settings.APP_DESCRIPTION = "基于 AutoGen 的智能聊天 API"
if not hasattr(settings, "VERSION"):
    settings.VERSION = "1.0.0"

if __name__ == "__main__":
    print(root_path)
    print(settings.aimodel.api_key)
    # for k,v in settings.items():
    #     print(k, v)
