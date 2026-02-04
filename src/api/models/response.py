"""
响应模型（Pydantic）
定义 API 响应的数据结构
"""
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field


# 泛型类型
T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = Field(0, description="业务状态码（0 表示成功）")
    message: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否超级管理员")
    created_at: datetime = Field(..., description="创建时间")


class RegisterResponse(BaseModel):
    """注册响应"""
    user: UserResponse = Field(..., description="用户信息")
    tokens: TokenResponse = Field(..., description="令牌信息")


class LoginResponse(BaseModel):
    """登录响应"""
    user: UserResponse = Field(..., description="用户信息")
    tokens: TokenResponse = Field(..., description="令牌信息")


class TaskResponse(BaseModel):
    """任务响应"""
    id: str = Field(..., description="任务 ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度（0-100）")
    current_node: Optional[str] = Field(None, description="当前执行节点")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    items: list[TaskResponse] = Field(..., description="任务列表")


class DietPlanSummaryResponse(BaseModel):
    """饮食计划摘要响应"""
    id: str = Field(..., description="计划 ID")
    pet_type: str = Field(..., description="宠物类型")
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: int = Field(..., description="宠物年龄（月）")
    pet_weight: float = Field(..., description="宠物体重")
    created_at: datetime = Field(..., description="创建时间")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="健康状态")
    version: str = Field(..., description="版本号")
    timestamp: Optional[datetime] = Field(None, description="检查时间")


class HealthCheckDetailResponse(HealthCheckResponse):
    """详细健康检查响应"""
    components: dict = Field(..., description="各组件状态")


class SendCodeResponse(BaseModel):
    """发送验证码响应"""
    email: str = Field(..., description="邮箱地址")
    code_type: str = Field(..., description="验证码类型")
    cooldown_seconds: int = Field(..., description="冷却时间（秒）")
    remaining_daily_sends: int = Field(..., description="今日剩余发送次数")
    expire_minutes: int = Field(..., description="验证码有效期（分钟）")


class VerifyCodeResponse(BaseModel):
    """验证验证码响应"""
    is_valid: bool = Field(..., description="是否验证成功")
    message: str = Field(..., description="提示信息")
