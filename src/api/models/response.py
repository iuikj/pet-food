"""
API response models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class PetType(str, Enum):
    CAT = "cat"
    DOG = "dog"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    DIET_PLAN = "diet_plan"
    RESEARCH = "research"


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(0, description="Business status code")
    message: str = Field("success", description="Response message")
    data: Optional[T] = Field(None, description="Response payload")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    nickname: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_pro: bool = False
    plan_type: Optional[str] = None
    subscription_expired_at: Optional[datetime] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime


class RegisterResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class LoginResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class SendCodeResponse(BaseModel):
    email: str
    code_type: str
    cooldown_seconds: int
    remaining_daily_sends: int
    expire_minutes: int


class VerifyCodeResponse(BaseModel):
    is_valid: bool
    message: str


class PasswordResetResponse(BaseModel):
    message: str


class ChangePasswordResponse(BaseModel):
    message: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: TaskType
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    current_node: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TaskListResponse(BaseModel):
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    items: list[TaskResponse]


class TaskCancelResponse(BaseModel):
    task_id: str
    status: TaskStatus


class TaskResultResponse(BaseModel):
    task_id: str
    output: dict[str, Any]


class CreateTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class DietPlanSummaryResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    pet_id: Optional[str] = None
    pet_type: PetType
    pet_breed: Optional[str] = None
    pet_age: int = Field(..., gt=0)
    pet_weight: float = Field(..., gt=0)
    health_status: Optional[str] = None
    is_active: bool = False
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DietPlanDetailResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    user_id: str
    pet_type: PetType
    pet_breed: Optional[str] = None
    pet_age: int = Field(..., gt=0)
    pet_weight: float = Field(..., gt=0)
    health_status: Optional[str] = None
    plan_data: dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None


class DietPlanListResponse(BaseModel):
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    items: list[DietPlanSummaryResponse]


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    timestamp: Optional[datetime] = None


class HealthCheckDetailResponse(HealthCheckResponse):
    components: dict[str, Any]


class ComponentStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    latency_ms: Optional[float] = None


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    type: str
    breed: Optional[str] = None
    age: int
    weight: float
    gender: Optional[str] = None
    avatar_url: Optional[str] = None
    health_status: Optional[str] = None
    special_requirements: Optional[str] = None
    is_active: bool
    has_plan: bool = False
    created_at: datetime
    updated_at: datetime


class PetListResponse(BaseModel):
    total: int
    items: list[PetResponse]


class AvatarUploadResponse(BaseModel):
    avatar_url: str


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    nickname: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_pro: bool = False
    plan_type: Optional[str] = None
    subscription_expired_at: Optional[datetime] = None
    created_at: datetime


class MealNutritionSummary(BaseModel):
    total_calories: int
    consumed_calories: int
    protein: dict[str, Any]
    fat: dict[str, Any]
    carbs: dict[str, Any]
    fiber: Optional[dict[str, Any]] = None


class MealDetail(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    time: Optional[str] = None
    description: Optional[str] = None
    calories: Optional[int] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    food_items: Optional[list[Any]] = None
    nutrition_data: Optional[dict[str, Any]] = None
    ai_tip: Optional[str] = None


class TodayMealsResponse(BaseModel):
    date: str
    meals: list[MealDetail]
    nutrition_summary: MealNutritionSummary


class MealHistoryItem(BaseModel):
    id: str
    pet_id: str
    meal_date: str
    meal_type: str
    calories: Optional[int] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None


class MealHistoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MealHistoryItem]


class CalendarDayResponse(BaseModel):
    date: str
    has_plan: bool = False
    completion_rate: int = Field(0, ge=0, le=100)
    total_meals: int = 0
    completed_meals: int = 0
    status: str = "none"


class MonthlyCalendarResponse(BaseModel):
    year: int
    month: int
    days: list[CalendarDayResponse]


class WeeklyDayResponse(BaseModel):
    date: str
    day_of_week: int
    has_plan: bool = False
    completion_rate: int = Field(0, ge=0, le=100)
    meals: list[MealDetail]


class WeeklyCalendarResponse(BaseModel):
    week_number: int
    start_date: str
    end_date: str
    days: list[WeeklyDayResponse]


class NutritionSummary(BaseModel):
    avg_calories: float
    avg_completion_rate: float
    calorie_trend: str
    protein_target: float
    protein_consumed: float
    fat_target: float
    fat_consumed: float
    carbs_target: float
    carbs_consumed: float


class DailyNutritionData(BaseModel):
    date: str
    calories: float
    protein: float
    fat: float
    carbs: float
    completion_rate: float


class TrendChart(BaseModel):
    labels: list[str]
    calories: list[float]
    protein: list[float]
    fat: list[float]
    carbs: list[float]


class AIInsight(BaseModel):
    type: str
    content: str


class NutritionAnalysisResponse(BaseModel):
    period: str
    summary: NutritionSummary
    daily_data: list[DailyNutritionData]
    trend_chart: TrendChart
    ai_insights: list[AIInsight]
