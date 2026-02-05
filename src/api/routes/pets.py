"""
宠物管理路由

处理宠物的 CRUD 操作
"""
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.request import CreatePetRequest, UpdatePetRequest, PetListRequest
from src.api.models.response import (
    ApiResponse,
    PetResponse,
    PetListResponse,
    AvatarUploadResponse
)
from src.api.services.pet_service import PetService


router = APIRouter()


def pet_to_response(pet: "Pet", has_plan: bool = False) -> PetResponse:
    """将 Pet 实体转换为 PetResponse"""
    return PetResponse(
        id=pet.id,
        user_id=pet.user_id,
        name=pet.name,
        type=pet.type,
        breed=pet.breed,
        age=pet.age,
        weight=float(pet.weight) if pet.weight else 0,
        gender=pet.gender,
        avatar_url=pet.avatar_url,
        health_status=pet.health_status,
        special_requirements=pet.special_requirements,
        is_active=pet.is_active,
        has_plan=has_plan,
        created_at=pet.created_at,
        updated_at=pet.updated_at
    )


@router.get("/", response_model=ApiResponse[PetListResponse], summary="获取宠物列表")
async def list_pets(
    is_active: Optional[bool] = Query(True, description="是否仅返回未删除的宠物"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取当前用户的宠物列表

    - **is_active**: 是否仅返回未删除的宠物（默认 true）
    """
    try:
        pet_service = PetService(db)
        pets_with_status = await pet_service.get_pets_with_plan_status(
            user_id=current_user_id,
            is_active=is_active
        )

        items = [
            PetResponse(
                id=pet["id"],
                user_id=pet["user_id"],
                name=pet["name"],
                type=pet["type"],
                breed=pet["breed"],
                age=pet["age"],
                weight=pet["weight"],
                gender=pet["gender"],
                avatar_url=pet["avatar_url"],
                health_status=pet["health_status"],
                special_requirements=pet["special_requirements"],
                is_active=pet["is_active"],
                has_plan=pet["has_plan"],
                created_at=pet["created_at"],
                updated_at=pet["updated_at"]
            )
            for pet in pets_with_status
        ]

        return ApiResponse(
            code=0,
            message="获取成功",
            data=PetListResponse(
                total=len(items),
                items=items
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取宠物列表失败",
                "detail": str(e)
            }
        )


@router.post("/", response_model=ApiResponse[PetResponse], summary="创建宠物")
async def create_pet(
    request: CreatePetRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    创建新宠物

    - **name**: 宠物名称（必填）
    - **type**: 宠物类型 cat/dog（必填）
    - **breed**: 品种（可选）
    - **age**: 年龄/月（必填）
    - **weight**: 体重/千克（必填）
    - **gender**: 性别 male/female（可选）
    - **health_status**: 健康状况（可选）
    - **special_requirements**: 特殊需求（可选）
    """
    try:
        pet_service = PetService(db)

        pet = await pet_service.create_pet(
            user_id=current_user_id,
            name=request.name,
            type=request.type,
            breed=request.breed,
            age=request.age,
            weight=request.weight,
            gender=request.gender,
            health_status=request.health_status,
            special_requirements=request.special_requirements
        )

        return ApiResponse(
            code=0,
            message="创建成功",
            data=pet_to_response(pet, has_plan=False)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 3000,
                "message": "创建宠物失败",
                "detail": str(e)
            }
        )


@router.get("/{pet_id}", response_model=ApiResponse[PetResponse], summary="获取宠物详情")
async def get_pet(
    pet_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取单个宠物的详细信息

    - **pet_id**: 宠物 ID
    """
    try:
        pet_service = PetService(db)
        pet = await pet_service.get_pet(current_user_id, pet_id)

        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        # 检查是否有计划
        from sqlalchemy import select, func
        from src.db.models import DietPlan

        plan_result = await db.execute(
            select(func.count(DietPlan.id)).where(
                DietPlan.pet_id == pet_id
            )
        )
        plan_count = plan_result.scalar()

        return ApiResponse(
            code=0,
            message="获取成功",
            data=pet_to_response(pet, has_plan=plan_count > 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取宠物详情失败",
                "detail": str(e)
            }
        )


@router.put("/{pet_id}", response_model=ApiResponse[PetResponse], summary="更新宠物")
async def update_pet(
    pet_id: str,
    request: UpdatePetRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    更新宠物信息

    - **pet_id**: 宠物 ID
    - **name**: 宠物名称
    - **type**: 宠物类型 cat/dog
    - **breed**: 品种
    - **age**: 年龄/月
    - **weight**: 体重/千克
    - **gender**: 性别 male/female
    - **health_status**: 健康状况
    - **special_requirements**: 特殊需求
    """
    try:
        pet_service = PetService(db)
        pet = await pet_service.update_pet(
            user_id=current_user_id,
            pet_id=pet_id,
            name=request.name,
            type=request.type,
            breed=request.breed,
            age=request.age,
            weight=request.weight,
            gender=request.gender,
            health_status=request.health_status,
            special_requirements=request.special_requirements
        )

        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        # 检查是否有计划
        from sqlalchemy import select, func
        from src.db.models import DietPlan

        plan_result = await db.execute(
            select(func.count(DietPlan.id)).where(
                DietPlan.pet_id == pet_id
            )
        )
        plan_count = plan_result.scalar()

        return ApiResponse(
            code=0,
            message="更新成功",
            data=pet_to_response(pet, has_plan=plan_count > 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "更新宠物失败",
                "detail": str(e)
            }
        )


@router.delete("/{pet_id}", response_model=ApiResponse[dict], summary="删除宠物")
async def delete_pet(
    pet_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    删除宠物（软删除）

    - **pet_id**: 宠物 ID

    注意：删除后无法恢复
    """
    try:
        pet_service = PetService(db)
        success = await pet_service.delete_pet(current_user_id, pet_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="删除成功",
            data={"pet_id": pet_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "删除宠物失败",
                "detail": str(e)
            }
        )


@router.post("/{pet_id}/avatar", response_model=ApiResponse[AvatarUploadResponse], summary="上传宠物头像")
async def upload_pet_avatar(
    pet_id: str,
    file: UploadFile = File(..., description="头像文件"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    上传宠物头像

    - **pet_id**: 宠物 ID
    - **file**: 头像文件（支持 jpg, png, webp，最大 2MB）

    注意：生产环境建议使用 OSS 服务
    """
    try:
        # 验证文件类型
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 5002,
                    "message": f"不支持的文件类型: {file.content_type}",
                    "detail": f"支持的类型: {', '.join(allowed_types)}"
                }
            )

        # 验证文件大小（2MB）
        MAX_FILE_SIZE = 2 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 5003,
                    "message": "文件大小超过限制",
                    "detail": "最大支持 2MB"
                }
            )

        # 创建上传目录
        upload_dir = "uploads/avatars/pets"
        os.makedirs(upload_dir, exist_ok=True)

        # 生成文件名
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{pet_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
        file_path = os.path.join(upload_dir, filename)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)

        # 生成访问 URL
        avatar_url = f"/static/uploads/avatars/pets/{filename}"

        # 更新宠物信息
        pet_service = PetService(db)
        pet = await pet_service.update_avatar(current_user_id, pet_id, avatar_url)

        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="上传成功",
            data=AvatarUploadResponse(avatar_url=avatar_url)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "上传头像失败",
                "detail": str(e)
            }
        )
