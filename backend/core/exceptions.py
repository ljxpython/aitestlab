"""
Custom exceptions for the application
"""


class SettingNotFound(Exception):
    """Raised when settings cannot be imported or found"""

    pass


class ConfigurationError(Exception):
    """Raised when there's a configuration error"""

    pass


class ServiceError(Exception):
    """Raised when there's a service-related error"""

    pass
