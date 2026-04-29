"""
体重记录服务

处理宠物体重记录的 CRUD 和趋势查询
"""
import uuid
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import WeightRecord, Pet


class WeightService:
    """体重记录服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_weight(
        self,
        user_id: str,
        pet_id: str,
        weight: float,
        recorded_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        记录体重（每次新增）

        仅当记录属于最新日期时同步更新 Pet.weight。

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            weight: 体重 (kg)
            recorded_date: 记录日期，默认今天
            notes: 备注

        Returns:
            记录数据
        """
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        target_date = recorded_date or date.today()
        has_later_record = await self._has_later_record(pet_id, target_date)

        # 创建新记录
        record = WeightRecord(
            id=str(uuid.uuid4()),
            pet_id=pet_id,
            weight=weight,
            recorded_date=target_date,
            notes=notes,
        )
        self.db.add(record)

        # 只有当前记录不早于已有最新记录时，才更新宠物当前体重。
        if not has_later_record:
            pet.weight = weight

        await self.db.commit()
        await self.db.refresh(record)

        return self._to_dict(record)

    async def get_weight_history(
        self,
        user_id: str,
        pet_id: str,
        days: int = 30,
    ) -> list[dict]:
        """
        获取体重历史记录

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            days: 最近天数

        Returns:
            按日期降序的体重记录列表
        """
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        start_date = date.today() - timedelta(days=days)

        result = await self.db.execute(
            select(WeightRecord).where(
                and_(
                    WeightRecord.pet_id == pet_id,
                    WeightRecord.recorded_date >= start_date,
                )
            ).order_by(
                desc(WeightRecord.recorded_date),
                desc(WeightRecord.created_at),
                desc(WeightRecord.id),
            )
        )
        records = result.scalars().all()

        return [self._to_dict(r) for r in records]

    async def get_latest_weight(
        self,
        user_id: str,
        pet_id: str,
    ) -> Optional[dict]:
        """
        获取最新一条体重记录

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID

        Returns:
            最新体重记录，无记录返回 None
        """
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        result = await self.db.execute(
            select(WeightRecord).where(
                WeightRecord.pet_id == pet_id,
            ).order_by(
                desc(WeightRecord.recorded_date),
                desc(WeightRecord.created_at),
                desc(WeightRecord.id),
            ).limit(1)
        )
        record = result.scalars().first()

        if not record:
            return None

        return self._to_dict(record)

    async def delete_weight_record(
        self,
        user_id: str,
        record_id: str,
    ) -> str:
        """
        删除体重记录

        Args:
            user_id: 用户 ID
            record_id: 记录 ID

        Returns:
            已删除的记录 ID

        Raises:
            ValueError: 记录不存在
        """
        result = await self.db.execute(
            select(WeightRecord, Pet).join(Pet).where(
                and_(
                    WeightRecord.id == record_id,
                    Pet.user_id == user_id,
                )
            )
        )
        row = result.first()

        if not row:
            raise ValueError("体重记录不存在")
        record, pet = row

        await self.db.execute(
            delete(WeightRecord).where(WeightRecord.id == record_id)
        )
        latest_remaining = await self._get_latest_record(record.pet_id)
        if latest_remaining is not None:
            pet.weight = latest_remaining.weight
        await self.db.commit()
        return record_id

    async def _verify_pet_ownership(self, user_id: str, pet_id: str) -> Optional[Pet]:
        """验证宠物所有权"""
        result = await self.db.execute(
            select(Pet).where(
                and_(
                    Pet.id == pet_id,
                    Pet.user_id == user_id,
                    Pet.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _has_later_record(self, pet_id: str, target_date: date) -> bool:
        """判断是否已存在更晚日期的体重记录。"""
        result = await self.db.execute(
            select(WeightRecord.id).where(
                and_(
                    WeightRecord.pet_id == pet_id,
                    WeightRecord.recorded_date > target_date,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _get_latest_record(self, pet_id: str) -> Optional[WeightRecord]:
        """按记录日期和创建时间获取最新一条体重记录。"""
        result = await self.db.execute(
            select(WeightRecord).where(
                WeightRecord.pet_id == pet_id,
            ).order_by(
                desc(WeightRecord.recorded_date),
                desc(WeightRecord.created_at),
                desc(WeightRecord.id),
            ).limit(1)
        )
        return result.scalars().first()

    @staticmethod
    def _to_dict(record: WeightRecord) -> dict:
        """转换为字典"""
        return {
            "id": record.id,
            "pet_id": record.pet_id,
            "weight": float(record.weight) if isinstance(record.weight, Decimal) else record.weight,
            "recorded_date": record.recorded_date.isoformat(),
            "notes": record.notes,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
