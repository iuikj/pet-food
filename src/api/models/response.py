"""
响应模型（Pydantic）
定义 API 响应的数据结构
"""
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ==================== 枚举定义 ====================

class PetType(str, Enum):
    """宠物类型"""
    CAT = "cat"
    DOG = "dog"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """任务类型"""
    DIET_PLAN = "diet_plan"
    RESEARCH = "research"


# ==================== 泛型与基础模型 ====================

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = Field(0, description="业务状态码（0 表示成功）")
    message: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")


# ==================== 认证相关响应 ====================

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
    nickname: Optional[str] = Field(None, description="昵称")
    phone: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
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


# ==================== 验证码相关响应 ====================

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


class PasswordResetResponse(BaseModel):
    """密码重置响应"""
    message: str = Field(..., description="提示信息")


class ChangePasswordResponse(BaseModel):
    """修改密码响应"""
    message: str = Field(..., description="提示信息")


# ==================== 任务相关响应 ====================

class TaskResponse(BaseModel):
    """任务响应"""
    id: str = Field(..., description="任务 ID")
    task_type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    progress: int = Field(..., ge=0, le=100, description="任务进度（0-100）")
    current_node: Optional[str] = Field(None, description="当前执行节点")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页")
    page_size: int = Field(..., ge=1, le=100, description="每页大小")
    items: list[TaskResponse] = Field(..., description="任务列表")


class TaskCancelResponse(BaseModel):
    """任务取消响应"""
    task_id: str = Field(..., description="任务 ID")
    status: TaskStatus = Field(..., description="任务状态")


class TaskResultResponse(BaseModel):
    """任务结果响应"""
    task_id: str = Field(..., description="任务 ID")
    output: dict = Field(..., description="任务输出数据")


class CreateTaskResponse(BaseModel):
    """创建任务响应"""
    task_id: str = Field(..., description="任务 ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")


# ==================== 饮食计划相关响应 ====================

class DietPlanSummaryResponse(BaseModel):
    """饮食计划摘要响应"""
    id: str = Field(..., description="计划 ID")
    task_id: Optional[str] = Field(None, description="关联任务 ID")
    pet_type: PetType = Field(..., description="宠物类型")
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: int = Field(..., gt=0, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, description="宠物体重（千克）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class DietPlanDetailResponse(BaseModel):
    """饮食计划详情响应"""
    id: str = Field(..., description="计划 ID")
    task_id: Optional[str] = Field(None, description="关联任务 ID")
    user_id: str = Field(..., description="用户 ID")
    pet_type: PetType = Field(..., description="宠物类型")
    pet_breed: Optional[str] = Field(None, description="宠物品种")
    pet_age: int = Field(..., gt=0, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, description="健康状况描述")
    plan_data: dict = Field(..., description="计划数据（JSON）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class DietPlanListResponse(BaseModel):
    """饮食计划列表响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页")
    page_size: int = Field(..., ge=1, le=100, description="每页大小")
    items: list[DietPlanSummaryResponse] = Field(..., description="计划列表")


# ==================== 健康检查相关响应 ====================

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="健康状态")
    version: str = Field(..., description="版本号")
    timestamp: Optional[datetime] = Field(None, description="检查时间")


class HealthCheckDetailResponse(HealthCheckResponse):
    """详细健康检查响应"""
    components: dict = Field(..., description="各组件状态")


class ComponentStatusResponse(BaseModel):
    """组件状态响应"""
    status: str = Field(..., description="状态: healthy/unhealthy")
    message: Optional[str] = Field(None, description="状态描述")
    latency_ms: Optional[float] = Field(None, description="延迟（毫秒）")


# ==================== 宠物管理相关响应 ====================

class PetResponse(BaseModel):
    """宠物信息响应"""
    id: str = Field(..., description="宠物 ID")
    user_id: str = Field(..., description="用户 ID")
    name: str = Field(..., description="宠物名称")
    type: str = Field(..., description="宠物类型: cat/dog")
    breed: Optional[str] = Field(None, description="宠物品种")
    age: int = Field(..., description="宠物年龄（月）")
    weight: float = Field(..., description="宠物体重（千克）")
    gender: Optional[str] = Field(None, description="性别: male/female")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
    health_status: Optional[str] = Field(None, description="健康状况")
    special_requirements: Optional[str] = Field(None, description="特殊需求")
    is_active: bool = Field(..., description="是否激活（未删除）")
    has_plan: bool = Field(False, description="是否有饮食计划")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class PetListResponse(BaseModel):
    """宠物列表响应"""
    total: int = Field(..., description="总数")
    items: list[PetResponse] = Field(..., description="宠物列表")


class AvatarUploadResponse(BaseModel):
    """头像上传响应"""
    avatar_url: str = Field(..., description="头像 URL")


# ==================== 用户信息管理相关响应 ====================

class UserProfileResponse(BaseModel):
    """用户信息响应"""
    id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    phone: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
    is_pro: bool = Field(False, description="是否 PRO 会员")
    plan_type: Optional[str] = Field(None, description="会员类型: monthly/yearly")
    subscription_expired_at: Optional[datetime] = Field(None, description="会员过期时间")
    created_at: datetime = Field(..., description="创建时间")


# ==================== 饮食记录相关响应 ====================

class MealNutritionSummary(BaseModel):
    """营养摘要响应（用于餐食记录）"""
    total_calories: int = Field(..., description="总卡路里目标")
    consumed_calories: int = Field(..., description="已摄入卡路里")
    protein: dict = Field(..., description="蛋白质信息: {target, consumed}")
    fat: dict = Field(..., description="脂肪信息: {target, consumed}")
    carbs: dict = Field(..., description="碳水化合物信息: {target, consumed}")
    fiber: Optional[dict] = Field(None, description="膳食纤维信息: {target, consumed}")


class MealDetail(BaseModel):
    """餐食详情响应"""
    id: str = Field(..., description="餐食 ID")
    type: str = Field(..., description="餐食类型: breakfast/lunch/dinner/snack")
    name: Optional[str] = Field(None, description="餐食名称")
    time: Optional[str] = Field(None, description="推荐时间")
    description: Optional[str] = Field(None, description="描述")
    calories: Optional[int] = Field(None, description="卡路里")
    is_completed: bool = Field(False, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    notes: Optional[str] = Field(None, description="备注")
    # 兼容 PetDietPlan 的营养数据结构
    food_items: Optional[list] = Field(None, description="食物列表")
    nutrition_data: Optional[dict] = Field(None, description="营养数据")
    ai_tip: Optional[str] = Field(None, description="AI 建议")


class TodayMealsResponse(BaseModel):
    """今日餐食响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    meals: list[MealDetail] = Field(..., description="餐食列表")
    nutrition_summary: MealNutritionSummary = Field(..., description="营养摘要")


class MealHistoryItem(BaseModel):
    """餐食历史记录响应"""
    id: str = Field(..., description="餐食 ID")
    pet_id: str = Field(..., description="宠物 ID")
    meal_date: str = Field(..., description="日期 YYYY-MM-DD")
    meal_type: str = Field(..., description="餐食类型")
    calories: Optional[int] = Field(None, description="卡路里")
    is_completed: bool = Field(False, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class MealHistoryResponse(BaseModel):
    """餐食历史响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    items: list[MealHistoryItem] = Field(..., description="历史记录列表")


# ==================== 日历相关响应 ====================

class CalendarDayResponse(BaseModel):
    """日历日期响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    has_plan: bool = Field(False, description="是否有计划")
    completion_rate: int = Field(0, ge=0, le=100, description="完成率（百分比）")
    total_meals: int = Field(0, description="总餐数")
    completed_meals: int = Field(0, description="已完成餐数")
    status: str = Field("none", description="状态: excellent/good/normal/poor/none")


class MonthlyCalendarResponse(BaseModel):
    """月度日历响应"""
    year: int = Field(..., description="年份")
    month: int = Field(..., description="月份")
    days: list[CalendarDayResponse] = Field(..., description="日期列表")


class WeeklyDayResponse(BaseModel):
    """周视图日期响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_of_week: int = Field(..., description="星期几（1-7）")
    has_plan: bool = Field(False, description="是否有计划")
    completion_rate: int = Field(0, ge=0, le=100, description="完成率")
    meals: list[MealDetail] = Field(..., description="餐食列表")


class WeeklyCalendarResponse(BaseModel):
    """周视图响应"""
    week_number: int = Field(..., description="周数")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: list[WeeklyDayResponse] = Field(..., description="日期列表")


# ==================== 营养分析相关响应 ====================

class NutritionSummary(BaseModel):
    """营养统计摘要"""
    avg_calories: float = Field(..., description="平均卡路里")
    avg_completion_rate: float = Field(..., description="平均完成率")
    calorie_trend: str = Field(..., description="卡路里趋势: stable/increasing/decreasing")
    protein_target: float = Field(..., description="蛋白质目标")
    protein_consumed: float = Field(..., description="蛋白质摄入")
    fat_target: float = Field(..., description="脂肪目标")
    fat_consumed: float = Field(..., description="脂肪摄入")
    carbs_target: float = Field(..., description="碳水目标")
    carbs_consumed: float = Field(..., description="碳水摄入")


class DailyNutritionData(BaseModel):
    """每日营养数据"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    calories: float = Field(..., description="卡路里")
    protein: float = Field(..., description="蛋白质 (克)")
    fat: float = Field(..., description="脂肪 (克)")
    carbs: float = Field(..., description="碳水 (克)")
    completion_rate: float = Field(..., description="完成率")


class TrendChart(BaseModel):
    """趋势图表数据"""
    labels: list[str] = Field(..., description="标签列表")
    calories: list[float] = Field(..., description="卡路里数据")
    protein: list[float] = Field(..., description="蛋白质数据")
    fat: list[float] = Field(..., description="脂肪数据")
    carbs: list[float] = Field(..., description="碳水数据")


class AIInsight(BaseModel):
    """AI 洞察建议"""
    type: str = Field(..., description="类型: positive/suggestion/warning")
    content: str = Field(..., description="建议内容")


class NutritionAnalysisResponse(BaseModel):
    """营养分析响应"""
    period: str = Field(..., description="分析周期: week/month/year")
    summary: NutritionSummary = Field(..., description="营养摘要")
    daily_data: list[DailyNutritionData] = Field(..., description="每日数据")
    trend_chart: TrendChart = Field(..., description="趋势图表")
    ai_insights: list[AIInsight] = Field(..., description="AI 建议")
