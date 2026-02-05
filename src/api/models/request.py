"""
请求模型（Pydantic）
定义 API 请求的数据结构
"""
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, field_validator


# ==================== 枚举定义 ====================

class PetType(str, Enum):
    """宠物类型"""
    CAT = "cat"
    DOG = "dog"


class CodeType(str, Enum):
    """验证码类型"""
    REGISTER = "register"
    PASSWORD_RESET = "password_reset"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """任务类型"""
    CREATE_PLAN = "create_plan"
    GENERATE_REPORT = "generate_report"


class PlanSortBy(str, Enum):
    """计划排序方式"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class SortOrder(str, Enum):
    """排序方向"""
    ASC = "asc"
    DESC = "desc"


# ==================== 请求模型 ====================

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
    pet_type: PetType = Field(..., description="宠物类型")
    pet_breed: Optional[str] = Field(None, max_length=50, description="宠物品种")
    pet_age: int = Field(..., gt=0, le=300, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, le=1000, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")
    stream: bool = Field(default=False, description="是否使用流式输出")


class UpdatePlanRequest(BaseModel):
    """更新饮食计划请求"""
    pet_breed: Optional[str] = Field(None, max_length=50, description="宠物品种")
    pet_age: Optional[int] = Field(None, gt=0, le=300, description="宠物年龄（月）")
    pet_weight: Optional[float] = Field(None, gt=0, le=1000, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")


class TaskListRequest(BaseModel):
    """任务列表查询请求"""
    status: Optional[TaskStatus] = Field(None, description="任务状态筛选")
    task_type: Optional[TaskType] = Field(None, description="任务类型筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页大小")


class PlanListRequest(BaseModel):
    """饮食计划列表查询请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页大小")
    sort_by: PlanSortBy = Field(PlanSortBy.CREATED_AT, description="排序字段")
    order: SortOrder = Field(SortOrder.DESC, description="排序方向")


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code_type: CodeType = Field(..., description="验证码类型")


class VerifyCodeRequest(BaseModel):
    """验证验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")
    code_type: CodeType = Field(..., description="验证码类型")


class RegisterWithCodeRequest(BaseModel):
    """使用验证码注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")

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
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class ChangePasswordRequest(BaseModel):
    """修改密码请求（需登录）"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")
