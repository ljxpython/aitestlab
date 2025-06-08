from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from loguru import logger

from backend.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.models.auth import PasswordChange, UserLogin, UserRegister, UserUpdate
from backend.models.user import User


class AuthService:
    """认证服务"""

    @staticmethod
    async def authenticate_user(username: str, password: str) -> Optional[User]:
        """验证用户"""
        try:
            user = await User.get_or_none(username=username)
            if not user:
                return None

            if not user.check_password(password):
                return None

            if not user.is_active:
                return None

            # 更新最后登录时间
            await user.update_last_login()

            return user
        except Exception as e:
            logger.error(f"用户验证失败: {e}")
            return None

    @staticmethod
    async def create_user(user_data: UserRegister) -> User:
        """创建用户"""
        try:
            # 检查用户名是否已存在
            existing_user = await User.get_or_none(username=user_data.username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
                )

            # 检查邮箱是否已存在
            if user_data.email:
                existing_email = await User.get_or_none(email=user_data.email)
                if existing_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已存在"
                    )

            # 创建用户
            user = User(
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                password_hash=get_password_hash(user_data.password),
            )
            await user.save()

            logger.info(f"用户创建成功: {user.username}")
            return user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"用户创建失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用户创建失败"
            )

    @staticmethod
    async def login(login_data: UserLogin) -> dict:
        """用户登录"""
        user = await AuthService.authenticate_user(
            login_data.username, login_data.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 创建访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id, "username": user.username},
            expires_delta=access_token_expires,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user.to_dict(),
        }

    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        try:
            return await User.get_or_none(id=user_id)
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    @staticmethod
    async def get_user_by_username(username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            return await User.get_or_none(username=username)
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    @staticmethod
    async def update_user(user: User, update_data: UserUpdate) -> User:
        """更新用户信息"""
        try:
            # 检查邮箱是否已被其他用户使用
            if update_data.email and update_data.email != user.email:
                existing_email = await User.get_or_none(email=update_data.email)
                if existing_email and existing_email.id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="邮箱已被其他用户使用",
                    )

            # 更新用户信息
            if update_data.email is not None:
                user.email = update_data.email
            if update_data.full_name is not None:
                user.full_name = update_data.full_name
            if update_data.avatar_url is not None:
                user.avatar_url = update_data.avatar_url

            await user.save()
            logger.info(f"用户信息更新成功: {user.username}")
            return user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"用户信息更新失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用户信息更新失败",
            )

    @staticmethod
    async def change_password(user: User, password_data: PasswordChange) -> bool:
        """修改密码"""
        try:
            # 验证旧密码
            if not user.check_password(password_data.old_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码错误"
                )

            # 设置新密码
            user.set_password(password_data.new_password)
            await user.save()

            logger.info(f"用户密码修改成功: {user.username}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"密码修改失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="密码修改失败"
            )


# 创建服务实例
auth_service = AuthService()
