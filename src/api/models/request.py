"""
请求模型（Pydantic）
定义 API 请求的数据结构
"""
import re
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, field_validator
from src.utils.strtuct import PetInformation


_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$")
_MAX_PASSWORD_BYTES = 72


def _normalize_and_validate_username(value: str) -> str:
    """规范化并校验用户名。"""
    normalized = value.strip()

    if len(normalized) < 3 or len(normalized) > 50:
        raise ValueError("用户名长度需为 3-50 个字符")

    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("用户名只能包含中文、字母、数字、下划线和连字符")

    return normalized


def _normalize_email(value: EmailStr | str) -> str:
    """统一邮箱格式，避免大小写和首尾空格带来的歧义。"""
    return str(value).strip().lower()


def _validate_password(value: str) -> str:
    """校验密码长度，避免 bcrypt 静默截断。"""
    password_bytes = len(value.encode("utf-8"))
    if password_bytes > _MAX_PASSWORD_BYTES:
        raise ValueError("密码最多支持 72 字节（UTF-8）")
    return value


# ==================== 枚举定义 ====================


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
    password: str = Field(..., min_length=6, description="密码（至少 6 个字符，最多 72 字节 UTF-8）")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        return _normalize_and_validate_username(v)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """统一邮箱格式。"""
        return _normalize_email(v)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码字节长度。"""
        return _validate_password(v)


class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")

    @field_validator('username')
    @classmethod
    def normalize_username(cls, v: str) -> str:
        """登录标识统一去掉首尾空格。"""
        return v.strip()


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class CreatePlanRequest(BaseModel):
    """创建饮食计划请求"""
    pet_id: Optional[str] = Field(None, description="宠物 ID（优先使用）")
    # 以下字段兼容旧版本，当没有 pet_id 时使用
    pet_type: Optional[str] = Field(None, description="宠物类型 cat/dog")
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: Optional[int] = Field(None, gt=0, description="宠物年龄（月）")
    pet_weight: Optional[float] = Field(None, gt=0, le=1000, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")
    special_requirements: Optional[str] = Field(None, max_length=500, description="本次生成的定制需求")
    stream: bool = Field(default=False, description="是否使用流式输出")


class UpdatePlanRequest(BaseModel):
    """更新饮食计划请求"""
    pet_breed: Optional[str] = Field(None, max_length=100, description="宠物品种")
    pet_age: Optional[int] = Field(None, gt=0, description="宠物年龄（月）")
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

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """统一邮箱格式。"""
        return _normalize_email(v)


class VerifyCodeRequest(BaseModel):
    """验证验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")
    code_type: CodeType = Field(..., description="验证码类型")

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """统一邮箱格式。"""
        return _normalize_email(v)


class RegisterWithCodeRequest(BaseModel):
    """使用验证码注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, description="密码（至少 6 个字符，最多 72 字节 UTF-8）")
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        return _normalize_and_validate_username(v)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """统一邮箱格式。"""
        return _normalize_email(v)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码字节长度。"""
        return _validate_password(v)


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$', description="6位数字验证码")
    new_password: str = Field(..., min_length=6, description="新密码（至少 6 个字符，最多 72 字节 UTF-8）")

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """统一邮箱格式。"""
        return _normalize_email(v)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """验证新密码字节长度。"""
        return _validate_password(v)


class ChangePasswordRequest(BaseModel):
    """修改密码请求（需登录）"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码（至少 6 个字符，最多 72 字节 UTF-8）")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """验证新密码字节长度。"""
        return _validate_password(v)


# ==================== 宠物管理相关请求 ====================

class CreatePetRequest(BaseModel):
    """创建宠物请求"""
    name: str = Field(..., min_length=1, max_length=50, description="宠物名称")
    type: str = Field(..., pattern=r'^(cat|dog)$', description="宠物类型: cat 或 dog")
    breed: Optional[str] = Field(None, max_length=100, description="宠物品种")
    age: int = Field(..., gt=0, description="宠物年龄（月）")
    weight: float = Field(..., gt=0, le=1000, description="宠物体重（千克）")
    gender: Optional[str] = Field(None, pattern=r'^(male|female)?$', description="性别: male 或 female")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")
    special_requirements: Optional[str] = Field(None, max_length=500, description="特殊需求")
    allergens: Optional[List[str]] = Field(None, description="过敏原列表")
    health_issues: Optional[List[str]] = Field(None, description="健康问题列表")


class UpdatePetRequest(BaseModel):
    """更新宠物请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="宠物名称")
    type: Optional[str] = Field(None, pattern=r'^(cat|dog)$', description="宠物类型: cat 或 dog")
    breed: Optional[str] = Field(None, max_length=100, description="宠物品种")
    age: Optional[int] = Field(None, gt=0, description="宠物年龄（月）")
    weight: Optional[float] = Field(None, gt=0, le=1000, description="宠物体重（千克）")
    gender: Optional[str] = Field(None, pattern=r'^(male|female)?$', description="性别: male 或 female")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")
    special_requirements: Optional[str] = Field(None, max_length=500, description="特殊需求")
    allergens: Optional[List[str]] = Field(None, description="过敏原列表")
    health_issues: Optional[List[str]] = Field(None, description="健康问题列表")


class PetListRequest(BaseModel):
    """宠物列表查询请求"""
    is_active: Optional[bool] = Field(True, description="是否仅返回未删除的宠物")


# ==================== 用户信息管理相关请求 ====================

class UpdateProfileRequest(BaseModel):
    """更新用户信息请求"""
    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="昵称")
    phone: Optional[str] = Field(None, pattern=r'^\d{11}$', description="手机号（11位数字）")


# ==================== 饮食记录相关请求 ====================

class CompleteMealRequest(BaseModel):
    """完成餐食请求"""
    notes: Optional[str] = Field(None, max_length=500, description="备注")


class MealListRequest(BaseModel):
    """餐食记录列表查询请求"""
    pet_id: str = Field(..., description="宠物 ID")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页大小")


# ==================== 日历相关请求 ====================

class MonthlyCalendarRequest(BaseModel):
    """月度日历查询请求"""
    pet_id: str = Field(..., description="宠物 ID")
    year: Optional[int] = Field(None, ge=2020, le=2100, description="年份，默认当前年")
    month: Optional[int] = Field(None, ge=1, le=12, description="月份，默认当前月")


class WeeklyCalendarRequest(BaseModel):
    """周视图查询请求"""
    pet_id: str = Field(..., description="宠物 ID")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")


# ==================== 营养分析相关请求 ====================

class NutritionAnalysisRequest(BaseModel):
    """营养分析查询请求"""
    pet_id: str = Field(..., description="宠物 ID")
    period: str = Field("week", pattern=r'^(week|month|year)$', description="时间周期: week/month/year")
