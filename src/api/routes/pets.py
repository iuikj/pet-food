"""
宠物管理路由

处理宠物的 CRUD 操作
"""
import mimetypes
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_minio_storage
from src.api.infrastructure.minio_storage import MinioManager
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


@router.get(
    "/avatar/object/{object_name:path}",
    include_in_schema=False,
    name="get_pet_avatar_object",
)
async def get_pet_avatar_object(
    object_name: str,
    storage: MinioManager = Depends(get_minio_storage),
):
    """通过后端统一主机地址代理 MinIO 中的宠物头像。"""
    file_content = await storage.adownload_file(object_name)
    if file_content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 3001,
                "message": "头像文件不存在",
                "detail": None,
            }
        )

    file_info = await storage.aget_file_info(object_name) or {}
    media_type = (
        file_info.get("content_type")
        or mimetypes.guess_type(object_name)[0]
        or "application/octet-stream"
    )

    return Response(
        content=file_content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _resolve_avatar_url(
    avatar_url: Optional[str],
    storage: MinioManager,
    request: Request | None = None,
) -> Optional[str]:
    """解析头像访问地址"""
    object_name = storage.extract_object_name(avatar_url)
    if object_name and request:
        return str(request.url_for("get_pet_avatar_object", object_name=object_name))

    request_host = request.url.hostname if request else None
    return storage.resolve_file_url(avatar_url, request_host=request_host)


def pet_to_response(
    pet: "Pet",
    storage: MinioManager,
    request: Request | None = None,
    has_plan: bool = False,
) -> PetResponse:
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
        avatar_url=_resolve_avatar_url(pet.avatar_url, storage, request=request),
        health_status=pet.health_status,
        special_requirements=pet.special_requirements,
        is_active=pet.is_active,
        has_plan=has_plan,
        created_at=pet.created_at,
        updated_at=pet.updated_at
    )


@router.get("/", response_model=ApiResponse[PetListResponse], summary="获取宠物列表")
async def list_pets(
    http_request: Request,
    is_active: Optional[bool] = Query(True, description="是否仅返回未删除的宠物"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage)
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
                avatar_url=_resolve_avatar_url(pet["avatar_url"], storage, request=http_request),
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
    http_request: Request,
    payload: CreatePetRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage)
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
            name=payload.name,
            type=payload.type,
            breed=payload.breed,
            age=payload.age,
            weight=payload.weight,
            gender=payload.gender,
            health_status=payload.health_status,
            special_requirements=payload.special_requirements
        )

        return ApiResponse(
            code=0,
            message="创建成功",
            data=pet_to_response(pet, storage=storage, request=http_request, has_plan=False)
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
    http_request: Request,
    pet_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage)
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
            data=pet_to_response(pet, storage=storage, request=http_request, has_plan=plan_count > 0)
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
    http_request: Request,
    pet_id: str,
    payload: UpdatePetRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage)
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
            name=payload.name,
            type=payload.type,
            breed=payload.breed,
            age=payload.age,
            weight=payload.weight,
            gender=payload.gender,
            health_status=payload.health_status,
            special_requirements=payload.special_requirements
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
            data=pet_to_response(pet, storage=storage, request=http_request, has_plan=plan_count > 0)
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
    http_request: Request,
    pet_id: str,
    file: UploadFile = File(..., description="头像文件"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    上传宠物头像

    - **pet_id**: 宠物 ID
    - **file**: 头像文件（支持 jpg、png、webp，最大 2MB）

    注意：生产环境建议使用 OSS 服务
    """
    uploaded_object_name: Optional[str] = None
    try:
        storage = get_minio_storage()
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
        max_file_size = 2 * 1024 * 1024
        content = await file.read()
        if len(content) > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 5003,
                    "message": "文件大小超过限制",
                    "detail": "最大支持 2MB"
                }
            )

        # 生成对象名
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        file_ext = ""
        if file.filename:
            filename_parts = file.filename.rsplit(".", maxsplit=1)
            if len(filename_parts) == 2:
                file_ext = f".{filename_parts[1].lower()}"
        if file_ext not in allowed_extensions:
            content_type_to_ext = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }
            file_ext = content_type_to_ext[file.content_type]

        uploaded_object_name = f"avatars/pets/{pet_id}/{uuid4().hex}{file_ext}"
        upload_success = await storage.aupload_file(
            object_name=uploaded_object_name,
            file_data=content,
            content_type=file.content_type,
        )
        if not upload_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 5004,
                    "message": "头像文件上传失败",
                    "detail": "MinIO 存储写入失败"
                }
            )

        old_avatar_reference = pet.avatar_url
        avatar_reference = storage.build_object_reference(uploaded_object_name)
        pet = await pet_service.update_avatar(current_user_id, pet_id, avatar_reference)
        if not pet:
            await storage.adelete_file(uploaded_object_name)
            uploaded_object_name = None
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        old_object_name = storage.extract_object_name(old_avatar_reference)
        if old_object_name and old_object_name != uploaded_object_name:
            await storage.adelete_file(old_object_name)

        avatar_url = _resolve_avatar_url(pet.avatar_url, storage, request=http_request)
        if not avatar_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 5005,
                    "message": "头像访问地址生成失败",
                    "detail": "MinIO 预签名 URL 生成失败"
                }
            )

        return ApiResponse(
            code=0,
            message="上传成功",
            data=AvatarUploadResponse(avatar_url=avatar_url)
        )
    except HTTPException:
        if uploaded_object_name:
            await storage.adelete_file(uploaded_object_name)
        raise
    except Exception as e:
        if uploaded_object_name:
            await storage.adelete_file(uploaded_object_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "上传头像失败",
                "detail": str(e)
            }
        )
