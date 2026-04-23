"""
食材库服务

支持系统食材（只读）与用户自定义食材（增删改）共存：
- 列表：系统食材 + 当前用户自己的自定义
- 创建：强制写入 user_id 与 is_system=False
- 更新/删除：仅允许操作归属当前用户的自定义食材
"""
import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, delete, distinct, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func as sa_func

from src.db.models import Ingredient


# 全量营养字段（与 Ingredient 模型对齐）
NUTRITION_FIELDS: tuple[str, ...] = (
    "calories", "carbohydrates", "protein", "fat", "dietary_fiber",
    "iron", "zinc", "manganese", "magnesium", "sodium", "calcium",
    "phosphorus", "copper", "iodine", "potassium", "selenium",
    "vitamin_b1", "vitamin_e", "vitamin_a", "vitamin_d",
    "epa", "dha", "epa_dha",
    "bone_content", "water", "choline", "taurine", "cholesterol",
)

# 基础描述字段
BASIC_FIELDS: tuple[str, ...] = ("name", "category", "sub_category", "note", "has_nutrition_data", "icon_key")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _ingredient_to_dict(ing: Ingredient) -> dict:
    """ORM 对象转 dict，数值字段统一 float。"""
    result: dict[str, Any] = {
        "id": ing.id,
        "name": ing.name,
        "category": ing.category,
        "sub_category": ing.sub_category,
        "has_nutrition_data": ing.has_nutrition_data,
        "note": ing.note,
        "user_id": ing.user_id,
        "is_system": ing.is_system,
        "icon_key": ing.icon_key,
        "image_url": ing.image_url,
        "created_at": ing.created_at.isoformat() if ing.created_at else None,
        "updated_at": ing.updated_at.isoformat() if ing.updated_at else None,
    }
    for field in NUTRITION_FIELDS:
        result[field] = _to_float(getattr(ing, field, None))
    return result


class IngredientService:
    """食材库业务服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ───────────────── 查询 ─────────────────

    async def list_ingredients(
        self,
        *,
        user_id: str,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        scope: str = "all",  # all | system | custom
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """当前用户可见的食材列表。

        scope:
          - all:    系统 + 自己创建的
          - system: 仅系统食材
          - custom: 仅自己创建的自定义食材
        """
        # 归属过滤
        if scope == "system":
            scope_cond = Ingredient.is_system.is_(True)
        elif scope == "custom":
            scope_cond = and_(Ingredient.is_system.is_(False), Ingredient.user_id == user_id)
        else:  # all
            scope_cond = or_(
                Ingredient.is_system.is_(True),
                and_(Ingredient.is_system.is_(False), Ingredient.user_id == user_id),
            )

        conditions = [scope_cond]
        if keyword:
            conditions.append(Ingredient.name.ilike(f"%{keyword}%"))
        if category:
            conditions.append(Ingredient.category == category)
        if sub_category:
            conditions.append(Ingredient.sub_category == sub_category)

        base_stmt = select(Ingredient).where(and_(*conditions))

        # 总数
        count_stmt = select(sa_func.count()).select_from(base_stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # 分页 + 排序（系统优先、按名称字典序）
        list_stmt = (
            base_stmt
            .order_by(Ingredient.is_system.desc(), Ingredient.category, Ingredient.name)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(list_stmt)).scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_ingredient_to_dict(r) for r in rows],
        }

    async def list_categories(self, *, user_id: str) -> list[dict]:
        """当前用户可见的类别/子类别聚合统计。"""
        scope_cond = or_(
            Ingredient.is_system.is_(True),
            and_(Ingredient.is_system.is_(False), Ingredient.user_id == user_id),
        )
        stmt = (
            select(
                Ingredient.category,
                Ingredient.sub_category,
                sa_func.count(Ingredient.id).label("count"),
            )
            .where(scope_cond)
            .group_by(Ingredient.category, Ingredient.sub_category)
            .order_by(Ingredient.category, Ingredient.sub_category)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            {"category": r.category, "sub_category": r.sub_category, "count": int(r.count)}
            for r in rows
        ]

    async def get_ingredient(self, *, user_id: str, ingredient_id: str) -> Optional[dict]:
        """查询单个食材（仅对当前用户可见）。"""
        scope_cond = or_(
            Ingredient.is_system.is_(True),
            and_(Ingredient.is_system.is_(False), Ingredient.user_id == user_id),
        )
        stmt = select(Ingredient).where(
            and_(Ingredient.id == ingredient_id, scope_cond)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        return _ingredient_to_dict(row) if row else None

    # ───────────────── 创建 ─────────────────

    async def create_ingredient(self, *, user_id: str, payload: dict) -> dict:
        """创建自定义食材。user_id 强制为当前用户，is_system=False。"""
        name = (payload.get("name") or "").strip()
        category = (payload.get("category") or "").strip()
        sub_category = (payload.get("sub_category") or "").strip()
        if not name or not category or not sub_category:
            raise ValueError("name / category / sub_category 必填")

        # 重名校验（同一用户下）
        dup_stmt = select(Ingredient.id).where(
            and_(Ingredient.user_id == user_id, Ingredient.name == name)
        )
        if (await self.db.execute(dup_stmt)).scalar():
            raise ValueError(f"已存在同名自定义食材：{name}")

        ing = Ingredient(
            id=str(uuid.uuid4()),
            user_id=user_id,
            is_system=False,
            name=name,
            category=category,
            sub_category=sub_category,
            note=payload.get("note"),
            has_nutrition_data=bool(payload.get("has_nutrition_data", True)),
            icon_key=_normalize_icon_key(payload.get("icon_key")),
        )
        # image_url 仅由上传端点控制，此处不接受用户直接传入
        for field in NUTRITION_FIELDS:
            value = payload.get(field)
            if value is not None:
                setattr(ing, field, value)

        self.db.add(ing)
        await self.db.commit()
        await self.db.refresh(ing)
        return _ingredient_to_dict(ing)

    # ───────────────── 更新 ─────────────────

    async def update_ingredient(
        self, *, user_id: str, ingredient_id: str, payload: dict
    ) -> Optional[dict]:
        """更新自己创建的自定义食材。系统食材返回 None 表示拒绝。"""
        stmt = select(Ingredient).where(
            and_(
                Ingredient.id == ingredient_id,
                Ingredient.user_id == user_id,
                Ingredient.is_system.is_(False),
            )
        )
        ing = (await self.db.execute(stmt)).scalars().first()
        if not ing:
            return None

        # 更新基础字段（排除 is_system / user_id / image_url）
        for field in BASIC_FIELDS:
            if field in payload and payload[field] is not None:
                value = payload[field]
                if field == "icon_key":
                    value = _normalize_icon_key(value)
                setattr(ing, field, value)

        # 更新营养字段（None 表示清空）
        for field in NUTRITION_FIELDS:
            if field in payload:
                setattr(ing, field, payload[field])

        await self.db.commit()
        await self.db.refresh(ing)
        return _ingredient_to_dict(ing)

    # ───────────────── 删除 ─────────────────

    async def delete_ingredient(self, *, user_id: str, ingredient_id: str) -> bool:
        """删除自己创建的自定义食材。系统食材返回 False 表示拒绝。"""
        stmt = select(Ingredient).where(
            and_(
                Ingredient.id == ingredient_id,
                Ingredient.user_id == user_id,
                Ingredient.is_system.is_(False),
            )
        )
        ing = (await self.db.execute(stmt)).scalars().first()
        if not ing:
            return False

        await self.db.execute(delete(Ingredient).where(Ingredient.id == ingredient_id))
        await self.db.commit()
        return True

    # ───────────────── 批量图标解析 ─────────────────

    async def resolve_icons(
        self, *, user_id: str, names: list[str]
    ) -> dict[str, Optional[dict]]:
        """按食材名批量查询 icon_key / image_url。

        用于食谱展示时把 FoodItem.name 映射到图标资源。
        查询范围遵守列表的归属约束（系统 + 当前用户自己的）。

        Args:
            user_id:  当前用户 ID
            names:    食材名称列表

        Returns:
            dict: { name: { icon_key, image_url } | None }
                  未命中的 name 值为 None。
        """
        # 去重 + 过滤空串
        dedup = [n for n in {str(x).strip() for x in names} if n]
        if not dedup:
            return {}

        scope_cond = or_(
            Ingredient.is_system.is_(True),
            and_(Ingredient.is_system.is_(False), Ingredient.user_id == user_id),
        )
        stmt = select(
            Ingredient.name,
            Ingredient.icon_key,
            Ingredient.image_url,
            Ingredient.is_system,
        ).where(and_(scope_cond, Ingredient.name.in_(dedup)))
        rows = (await self.db.execute(stmt)).all()

        # 优先级：自定义食材 > 系统食材（同名时自定义胜出）
        result: dict[str, dict] = {}
        for r in rows:
            payload = {
                "icon_key": r.icon_key,
                "image_url": r.image_url,
                "is_system": bool(r.is_system),
            }
            existing = result.get(r.name)
            if existing is None or (existing.get("is_system") and not r.is_system):
                result[r.name] = payload

        # 构造完整返回：未命中的 name 返回 None
        out: dict[str, Optional[dict]] = {}
        for n in dedup:
            hit = result.get(n)
            out[n] = (
                {"icon_key": hit["icon_key"], "image_url": hit["image_url"]}
                if hit
                else None
            )
        return out


# ─────────────────────── 辅助函数 ───────────────────────


def _normalize_icon_key(value: Optional[str]) -> Optional[str]:
    """校验并规范化 icon_key。格式: <library>:<name>

    返回：
      - None / 空字符串 → None
      - 合法格式 → trim 后返回
      - 非法格式 → 抛 ValueError
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if ":" not in s:
        raise ValueError(f"icon_key 格式非法（期望 <library>:<name>）：{s}")
    lib, _, name = s.partition(":")
    lib = lib.strip().lower()
    name = name.strip()
    if not lib or not name:
        raise ValueError(f"icon_key 格式非法：{s}")
    if lib not in {"emoji", "mi"}:
        raise ValueError(f"不支持的 icon library：{lib}")
    return f"{lib}:{name}"
