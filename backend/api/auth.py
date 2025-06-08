from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from backend.core.deps import get_current_active_user
from backend.models.auth import (
    LoginResponse,
    PasswordChange,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from backend.models.user import User
from backend.services.auth_service import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(login_data: UserLogin):
    """
    用户登录

    - **username**: 用户名
    - **password**: 密码
    """
    try:
        result = await auth_service.login(login_data)
        logger.info(f"用户登录成功: {login_data.username}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="登录失败"
        )


@router.post("/register", response_model=UserResponse, summary="用户注册")
async def register(user_data: UserRegister):
    """
    用户注册

    - **username**: 用户名（3-50字符）
    - **password**: 密码（至少6字符）
    - **email**: 邮箱（可选）
    - **full_name**: 全名（可选）
    """
    try:
        user = await auth_service.create_user(user_data)
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="注册失败"
        )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse, summary="更新当前用户信息")
async def update_current_user(
    update_data: UserUpdate, current_user: User = Depends(get_current_active_user)
):
    """
    更新当前用户信息

    - **email**: 邮箱
    - **full_name**: 全名
    - **avatar_url**: 头像URL
    """
    try:
        updated_user = await auth_service.update_user(current_user, update_data)
        return UserResponse.from_orm(updated_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户信息更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="用户信息更新失败"
        )


@router.post("/change-password", summary="修改密码")
async def change_password(
    password_data: PasswordChange, current_user: User = Depends(get_current_active_user)
):
    """
    修改密码

    - **old_password**: 旧密码
    - **new_password**: 新密码（至少6字符）
    """
    try:
        await auth_service.change_password(current_user, password_data)
        return {"message": "密码修改成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"密码修改失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="密码修改失败"
        )


@router.post("/logout", summary="用户登出")
async def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出（客户端需要删除本地token）"""
    logger.info(f"用户登出: {current_user.username}")
    return {"message": "登出成功"}
