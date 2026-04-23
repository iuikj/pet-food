"""
食材库路由

/api/v1/ingredients/
  GET    /              列表（支持搜索、分类筛选、分页）
  GET    /categories    类别聚合
  GET    /{id}          详情
  POST   /              创建自定义食材
  PUT    /{id}          更新自定义食材
  DELETE /{id}          删除自定义食材
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import ApiResponse
from src.api.services.ingredient_service import IngredientService, NUTRITION_FIELDS


router = APIRouter()


# ───────────────────────── 请求/响应模型 ─────────────────────────


class IngredientBase(BaseModel):
    """基础字段。营养字段全部可选，便于“主要字段必填 + 次要字段选填”策略。"""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    sub_category: str = Field(..., min_length=1, max_length=50)
    note: Optional[str] = Field(None, max_length=100)
    has_nutrition_data: bool = True

    # 图标（image_url 由 thumbnail 端点维护，不在创建/更新请求暴露）
    icon_key: Optional[str] = Field(
        None, max_length=64, description="图标 key，格式 <library>:<name>，如 emoji:fish / mi:restaurant"
    )

    # 宏量营养素
    calories: Optional[float] = None
    carbohydrates: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    dietary_fiber: Optional[float] = None

    # 矿物质
    iron: Optional[float] = None
    zinc: Optional[float] = None
    manganese: Optional[float] = None
    magnesium: Optional[float] = None
    sodium: Optional[float] = None
    calcium: Optional[float] = None
    phosphorus: Optional[float] = None
    copper: Optional[float] = None
    iodine: Optional[float] = None
    potassium: Optional[float] = None
    selenium: Optional[float] = None

    # 维生素
    vitamin_a: Optional[float] = None
    vitamin_d: Optional[float] = None
    vitamin_e: Optional[float] = None
    vitamin_b1: Optional[float] = None

    # 脂肪酸
    epa: Optional[float] = None
    dha: Optional[float] = None
    epa_dha: Optional[float] = None

    # 其他
    bone_content: Optional[float] = None
    water: Optional[float] = None
    choline: Optional[float] = None
    taurine: Optional[float] = None
    cholesterol: Optional[float] = None


class CreateIngredientRequest(IngredientBase):
    """创建自定义食材"""


class UpdateIngredientRequest(BaseModel):
    """更新自定义食材（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    sub_category: Optional[str] = Field(None, min_length=1, max_length=50)
    note: Optional[str] = Field(None, max_length=100)
    has_nutrition_data: Optional[bool] = None
    icon_key: Optional[str] = Field(None, max_length=64)

    calories: Optional[float] = None
    carbohydrates: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    dietary_fiber: Optional[float] = None

    iron: Optional[float] = None
    zinc: Optional[float] = None
    manganese: Optional[float] = None
    magnesium: Optional[float] = None
    sodium: Optional[float] = None
    calcium: Optional[float] = None
    phosphorus: Optional[float] = None
    copper: Optional[float] = None
    iodine: Optional[float] = None
    potassium: Optional[float] = None
    selenium: Optional[float] = None

    vitamin_a: Optional[float] = None
    vitamin_d: Optional[float] = None
    vitamin_e: Optional[float] = None
    vitamin_b1: Optional[float] = None

    epa: Optional[float] = None
    dha: Optional[float] = None
    epa_dha: Optional[float] = None

    bone_content: Optional[float] = None
    water: Optional[float] = None
    choline: Optional[float] = None
    taurine: Optional[float] = None
    cholesterol: Optional[float] = None


class IngredientResponse(IngredientBase):
    id: str
    user_id: Optional[str] = None
    is_system: bool
    image_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IngredientListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[IngredientResponse]


class IngredientCategoryItem(BaseModel):
    category: str
    sub_category: str
    count: int


class ResolveIconsRequest(BaseModel):
    """批量按食材名解析图标资源。"""
    model_config = ConfigDict(extra="ignore")
    names: list[str] = Field(..., min_length=1, max_length=100, description="食材名列表（最多 100）")


class ResolvedIconItem(BaseModel):
    icon_key: Optional[str] = None
    image_url: Optional[str] = None


# ───────────────────────── 路由 ─────────────────────────


@router.get(
    "/",
    response_model=ApiResponse[IngredientListResponse],
    summary="食材列表",
)
async def list_ingredients(
    keyword: Optional[str] = Query(None, max_length=100, description="名称模糊搜索"),
    category: Optional[str] = Query(None, max_length=50, description="按大类别筛选"),
    sub_category: Optional[str] = Query(None, max_length=50, description="按子类别筛选"),
    scope: Literal["all", "system", "custom"] = Query("all", description="归属范围"),
    limit: int = Query(50, ge=1, le=200, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    try:
        data = await service.list_ingredients(
            user_id=current_user_id,
            keyword=keyword,
            category=category,
            sub_category=sub_category,
            scope=scope,
            limit=limit,
            offset=offset,
        )
        return ApiResponse(code=0, message="获取成功", data=data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "获取食材列表失败", "detail": str(exc)},
        )


@router.get(
    "/categories",
    response_model=ApiResponse[list[IngredientCategoryItem]],
    summary="食材分类聚合",
)
async def list_categories(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    try:
        data = await service.list_categories(user_id=current_user_id)
        return ApiResponse(code=0, message="获取成功", data=data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "获取分类失败", "detail": str(exc)},
        )


@router.post(
    "/resolve-icons",
    response_model=ApiResponse[dict[str, Optional[ResolvedIconItem]]],
    summary="按食材名批量解析图标资源",
)
async def resolve_icons(
    body: ResolveIconsRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """给定一组食材名，返回每个名字对应的 icon_key / image_url（未命中返回 null）。

    用于食谱展示时把 FoodItem.name 一次性映射成图标资源。
    查询范围：系统食材 + 当前用户自定义食材（同名时自定义优先）。
    """
    service = IngredientService(db)
    try:
        data = await service.resolve_icons(user_id=current_user_id, names=body.names)
        return ApiResponse(code=0, message="获取成功", data=data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "图标解析失败", "detail": str(exc)},
        )


@router.get(
    "/{ingredient_id}",
    response_model=ApiResponse[IngredientResponse],
    summary="食材详情",
)
async def get_ingredient(
    ingredient_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    data = await service.get_ingredient(user_id=current_user_id, ingredient_id=ingredient_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 4001, "message": "食材不存在", "detail": None},
        )
    return ApiResponse(code=0, message="获取成功", data=data)


@router.post(
    "/",
    response_model=ApiResponse[IngredientResponse],
    summary="创建自定义食材",
)
async def create_ingredient(
    body: CreateIngredientRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    try:
        payload = body.model_dump(exclude_unset=False)
        data = await service.create_ingredient(user_id=current_user_id, payload=payload)
        return ApiResponse(code=0, message="创建成功", data=data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 4000, "message": str(exc), "detail": None},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "创建食材失败", "detail": str(exc)},
        )


@router.put(
    "/{ingredient_id}",
    response_model=ApiResponse[IngredientResponse],
    summary="更新自定义食材",
)
async def update_ingredient(
    ingredient_id: str,
    body: UpdateIngredientRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    try:
        payload = body.model_dump(exclude_unset=True)
        data = await service.update_ingredient(
            user_id=current_user_id,
            ingredient_id=ingredient_id,
            payload=payload,
        )
        if not data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 4003, "message": "系统食材不可编辑或无权限", "detail": None},
            )
        return ApiResponse(code=0, message="更新成功", data=data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "更新食材失败", "detail": str(exc)},
        )


@router.delete(
    "/{ingredient_id}",
    response_model=ApiResponse[dict],
    summary="删除自定义食材",
)
async def delete_ingredient(
    ingredient_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    service = IngredientService(db)
    try:
        ok = await service.delete_ingredient(
            user_id=current_user_id, ingredient_id=ingredient_id
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 4003, "message": "系统食材不可删除或无权限", "detail": None},
            )
        return ApiResponse(code=0, message="删除成功", data={"id": ingredient_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "删除食材失败", "detail": str(exc)},
        )
