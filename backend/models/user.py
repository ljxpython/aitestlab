import hashlib
from datetime import datetime
from typing import Optional

from tortoise import fields
from tortoise.models import Model


class User(Model):
    """用户模型"""

    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True, description="用户名")
    email = fields.CharField(max_length=100, unique=True, null=True, description="邮箱")
    password_hash = fields.CharField(max_length=255, description="密码哈希")
    full_name = fields.CharField(max_length=100, null=True, description="全名")
    avatar_url = fields.CharField(max_length=255, null=True, description="头像URL")
    is_active = fields.BooleanField(default=True, description="是否激活")
    is_superuser = fields.BooleanField(default=False, description="是否超级用户")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    last_login = fields.DatetimeField(null=True, description="最后登录时间")

    class Meta:
        table = "users"
        table_description = "用户表"

    def __str__(self):
        return f"User(id={self.id}, username={self.username})"

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return cls.get_password_hash(plain_password) == hashed_password

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        """获取密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        """检查密码"""
        return self.verify_password(password, self.password_hash)

    def set_password(self, password: str):
        """设置密码"""
        self.password_hash = self.get_password_hash(password)

    async def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.now()
        await self.save(update_fields=["last_login"])

    def to_dict(self) -> dict:
        """转换为字典（不包含敏感信息）"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class UserSession(Model):
    """用户会话模型"""

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="sessions", description="用户"
    )
    token = fields.CharField(max_length=255, unique=True, description="会话令牌")
    expires_at = fields.DatetimeField(description="过期时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    is_active = fields.BooleanField(default=True, description="是否激活")

    class Meta:
        table = "user_sessions"
        table_description = "用户会话表"

    def __str__(self):
        return f"UserSession(id={self.id}, user_id={self.user_id})"

    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now() > self.expires_at

    async def deactivate(self):
        """停用会话"""
        self.is_active = False
        await self.save(update_fields=["is_active"])
