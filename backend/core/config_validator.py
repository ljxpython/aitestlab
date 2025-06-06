"""
Configuration validation utilities
"""

from backend.core.exceptions import ConfigurationError


def validate_settings(settings):
    """Validate application settings"""
    required_fields = [
        "APP_TITLE",
        "APP_DESCRIPTION",
        "VERSION",
        "LOG_LEVEL",
        "LOG_FILE",
        "aimodel.model",
        "aimodel.base_url",
        "aimodel.api_key",
    ]

    # 可选字段（有默认值）
    optional_fields = [
        "autogen.max_agents",
        "autogen.cleanup_interval",
        "autogen.agent_ttl",
    ]

    missing_fields = []

    for field in required_fields:
        if "." in field:
            # 处理嵌套字段
            parts = field.split(".")
            current = settings
            try:
                for part in parts:
                    current = getattr(current, part)
                if not current:
                    missing_fields.append(field)
            except AttributeError:
                missing_fields.append(field)
        else:
            # 处理顶级字段
            if not hasattr(settings, field) or not getattr(settings, field):
                missing_fields.append(field)

    if missing_fields:
        raise ConfigurationError(
            f"Missing required configuration fields: {', '.join(missing_fields)}"
        )

    # 验证可选字段（记录警告但不报错）
    missing_optional = []
    for field in optional_fields:
        if "." in field:
            parts = field.split(".")
            current = settings
            try:
                for part in parts:
                    current = getattr(current, part)
                if current is None:
                    missing_optional.append(field)
            except AttributeError:
                missing_optional.append(field)

    if missing_optional:
        print(f"⚠️  可选配置字段缺失（将使用默认值）: {', '.join(missing_optional)}")

    print("✅ 配置验证通过")
    return True
