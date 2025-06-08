from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserLogin(BaseModel):
    """用户登录请求模型"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class UserRegister(BaseModel):
    """用户注册请求模型"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")


class UserUpdate(BaseModel):
    """用户更新请求模型"""

    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    avatar_url: Optional[str] = Field(None, max_length=255, description="头像URL")


class PasswordChange(BaseModel):
    """密码修改请求模型"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class UserResponse(BaseModel):
    """用户响应模型"""

    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """登录响应模型"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """令牌数据模型"""

    user_id: Optional[int] = None
    username: Optional[str] = None
