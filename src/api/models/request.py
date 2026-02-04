"""
请求模型（Pydantic）
定义 API 请求的数据结构
"""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('用户名只能包含字母、数字、下划线和连字符')
        return v


class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class CreatePlanRequest(BaseModel):
    """创建饮食计划请求"""
    pet_type: str = Field(..., description="宠物类型 (cat, dog)")
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: int = Field(..., gt=0, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, description="宠物体重（克或千克）")
    health_status: Optional[str] = Field(None, description="健康状况描述")
    stream: bool = Field(default=False, description="是否使用流式输出")


class UpdatePlanRequest(BaseModel):
    """更新饮食计划请求"""
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: Optional[int] = Field(None, gt=0, description="宠物年龄（月）")
    pet_weight: Optional[float] = Field(None, gt=0, description="宠物体重（克或千克）")
    health_status: Optional[str] = Field(None, description="健康状况描述")


class TaskListRequest(BaseModel):
    """任务列表查询请求"""
    status: Optional[str] = Field(None, description="任务状态筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页大小")


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code_type: str = Field(..., description="验证码类型: register/password_reset")


class VerifyCodeRequest(BaseModel):
    """验证验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    code_type: str = Field(..., description="验证码类型: register/password_reset")


class RegisterWithCodeRequest(BaseModel):
    """使用验证码注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('用户名只能包含字母、数字、下划线和连字符')
        return v


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class ChangePasswordRequest(BaseModel):
    """修改密码请求（需登录）"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")
