"""
宠物管理服务

处理宠物的 CRUD 操作
"""
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Pet, DietPlan, User


class PetService:
    """宠物管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pet(
        self,
        user_id: str,
        name: str,
        type: str,
        breed: Optional[str] = None,
        age: int = 0,
        weight: float = 0,
        gender: Optional[str] = None,
        health_status: Optional[str] = None,
        special_requirements: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Pet:
        """
        创建宠物

        Args:
            user_id: 用户 ID
            name: 宠物名称
            type: 宠物类型 cat/dog
            breed: 品种
            age: 年龄（月）
            weight: 体重（千克）
            gender: 性别 male/female
            health_status: 健康状况
            special_requirements: 特殊需求
            avatar_url: 头像 URL

        Returns:
            Pet 实体
        """
        pet = Pet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            type=type,
            breed=breed,
            age=age,
            weight=weight,
            gender=gender,
            health_status=health_status,
            special_requirements=special_requirements,
            avatar_url=avatar_url,
            is_active=True
        )
        self.db.add(pet)
        await self.db.commit()
        await self.db.refresh(pet)
        return pet

    async def get_pet(self, user_id: str, pet_id: str) -> Optional[Pet]:
        """
        获取单个宠物

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID

        Returns:
            Pet 实体，不存在返回 None
        """
        result = await self.db.execute(
            select(Pet).where(
                and_(
                    Pet.id == pet_id,
                    Pet.user_id == user_id,
                    Pet.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_pets_by_user(
        self,
        user_id: str,
        is_active: Optional[bool] = True
    ) -> list[Pet]:
        """
        获取用户的宠物列表

        Args:
            user_id: 用户 ID
            is_active: 是否仅返回未删除的宠物

        Returns:
            宠物列表
        """
        query = select(Pet).where(Pet.user_id == user_id)
        if is_active is not None:
            query = query.where(Pet.is_active == is_active)

        query = query.order_by(Pet.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_pet(
        self,
        user_id: str,
        pet_id: str,
        name: Optional[str] = None,
        type: Optional[str] = None,
        breed: Optional[str] = None,
        age: Optional[int] = None,
        weight: Optional[float] = None,
        gender: Optional[str] = None,
        health_status: Optional[str] = None,
        special_requirements: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Optional[Pet]:
        """
        更新宠物信息

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            name: 宠物名称
            type: 宠物类型
            breed: 品种
            age: 年龄
            weight: 体重
            gender: 性别
            health_status: 健康状况
            special_requirements: 特殊需求
            avatar_url: 头像 URL

        Returns:
            更新后的 Pet 实体，不存在返回 None
        """
        pet = await self.get_pet(user_id, pet_id)
        if not pet:
            return None

        if name is not None:
            pet.name = name
        if type is not None:
            pet.type = type
        if breed is not None:
            pet.breed = breed
        if age is not None:
            pet.age = age
        if weight is not None:
            pet.weight = weight
        if gender is not None:
            pet.gender = gender
        if health_status is not None:
            pet.health_status = health_status
        if special_requirements is not None:
            pet.special_requirements = special_requirements
        if avatar_url is not None:
            pet.avatar_url = avatar_url

        pet.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(pet)
        return pet

    async def update_avatar(
        self,
        user_id: str,
        pet_id: str,
        avatar_url: str
    ) -> Optional[Pet]:
        """
        更新宠物头像

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            avatar_url: 头像 URL

        Returns:
            更新后的 Pet 实体，不存在返回 None
        """
        return await self.update_pet(user_id, pet_id, avatar_url=avatar_url)

    async def delete_pet(self, user_id: str, pet_id: str) -> bool:
        """
        软删除宠物（设置 is_active = False）

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID

        Returns:
            删除成功返回 True，不存在返回 False
        """
        pet = await self.get_pet(user_id, pet_id)
        if not pet:
            return False

        pet.is_active = False
        pet.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def get_pets_with_plan_status(
        self,
        user_id: str,
        is_active: Optional[bool] = True
    ) -> list[dict]:
        """
        获取宠物列表，包含是否有计划的状态

        Args:
            user_id: 用户 ID
            is_active: 是否仅返回未删除的宠物

        Returns:
            包含计划状态的宠物信息列表
        """
        pets = await self.get_pets_by_user(user_id, is_active)

        # 批量查询每个宠物是否有计划
        result_list = []
        for pet in pets:
            # 查询该宠物是否有饮食计划
            plan_result = await self.db.execute(
                select(func.count(DietPlan.id)).where(
                    and_(
                        DietPlan.pet_id == pet.id,
                        DietPlan.user_id == user_id
                    )
                )
            )
            plan_count = plan_result.scalar()
            has_plan = plan_count > 0

            result_list.append({
                "id": pet.id,
                "user_id": pet.user_id,
                "name": pet.name,
                "type": pet.type,
                "breed": pet.breed,
                "age": pet.age,
                "weight": float(pet.weight) if pet.weight else 0,
                "gender": pet.gender,
                "avatar_url": pet.avatar_url,
                "health_status": pet.health_status,
                "special_requirements": pet.special_requirements,
                "is_active": pet.is_active,
                "has_plan": has_plan,
                "created_at": pet.created_at,
                "updated_at": pet.updated_at
            })

        return result_list

    async def get_pet_for_plan(
        self,
        user_id: str,
        pet_id: str
    ) -> Optional[dict]:
        """
        获取用于创建计划的宠物信息

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID

        Returns:
            宠物信息字典，兼容 PetInformation 结构
        """
        pet = await self.get_pet(user_id, pet_id)
        if not pet:
            return None

        return {
            "pet_type": pet.type,
            "pet_breed": pet.breed,
            "age": pet.age,
            "pet_weight": pet.weight,
            "pet_health_status": pet.health_status or "健康"
        }
