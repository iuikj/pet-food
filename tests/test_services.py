"""
服务层单元测试
测试纯业务逻辑：不依赖 HTTP 层，直接测试 Service 方法
"""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Pet, MealRecord, WeightRecord


# ==================== MealService 单元测试 ====================

@pytest.mark.asyncio
class TestMealServiceHelpers:
    """MealService 辅助方法测试"""

    def _make_service(self, session):
        from src.api.services.meal_service import MealService
        return MealService(session)

    async def test_meal_order_to_type(self, test_session):
        """测试餐序号转类型映射"""
        svc = self._make_service(test_session)
        assert svc._meal_order_to_type(1) == "breakfast"
        assert svc._meal_order_to_type(2) == "lunch"
        assert svc._meal_order_to_type(3) == "dinner"
        assert svc._meal_order_to_type(4) == "snack"
        assert svc._meal_order_to_type(5) == "snack"  # 超出范围 fallback
        assert svc._meal_order_to_type(99) == "snack"

    async def test_get_meal_time(self, test_session):
        """测试餐食类型到建议时间映射"""
        svc = self._make_service(test_session)
        assert svc._get_meal_time("breakfast") == "08:00"
        assert svc._get_meal_time("lunch") == "12:00"
        assert svc._get_meal_time("dinner") == "18:00"
        assert svc._get_meal_time("snack") == "15:00"
        assert svc._get_meal_time("unknown") == ""

    async def test_generate_ai_insights_high_completion(self, test_session):
        """高完成率应生成 positive 洞察"""
        svc = self._make_service(test_session)
        insights = svc._generate_ai_insights(
            completion_rate=95, protein=500, fat=300, carbs=600, days=7
        )
        assert any(i["type"] == "positive" for i in insights)

    async def test_generate_ai_insights_low_completion(self, test_session):
        """低完成率应生成 warning 洞察"""
        svc = self._make_service(test_session)
        insights = svc._generate_ai_insights(
            completion_rate=30, protein=500, fat=300, carbs=600, days=7
        )
        assert any(i["type"] == "warning" for i in insights)

    async def test_generate_ai_insights_medium_completion(self, test_session):
        """中等完成率应生成 suggestion 洞察"""
        svc = self._make_service(test_session)
        insights = svc._generate_ai_insights(
            completion_rate=75, protein=500, fat=300, carbs=600, days=7
        )
        assert any(i["type"] == "suggestion" for i in insights)

    async def test_generate_ai_insights_low_protein(self, test_session):
        """低蛋白质摄入应给出建议"""
        svc = self._make_service(test_session)
        insights = svc._generate_ai_insights(
            completion_rate=90, protein=200, fat=300, carbs=600, days=7
        )
        protein_insights = [i for i in insights if "蛋白质" in i["content"]]
        assert len(protein_insights) >= 1

    async def test_generate_ai_insights_high_fat(self, test_session):
        """高脂肪摄入应给出警告"""
        svc = self._make_service(test_session)
        insights = svc._generate_ai_insights(
            completion_rate=90, protein=500, fat=700, carbs=600, days=7
        )
        fat_insights = [i for i in insights if "脂肪" in i["content"]]
        assert len(fat_insights) >= 1

    async def test_normalize_nutrient_dict_format(self, test_session):
        """标准化 dict 格式营养值"""
        svc = self._make_service(test_session)
        result = svc._normalize_nutrient_amount(
            {"value": 100, "unit": "mg"}, preferred_unit="mg"
        )
        assert result["value"] == 100
        assert result["unit"] == "mg"

    async def test_normalize_nutrient_raw_number(self, test_session):
        """标准化原始数字营养值"""
        svc = self._make_service(test_session)
        result = svc._normalize_nutrient_amount(
            50.5, preferred_unit="mg", legacy_unit="mg"
        )
        assert result["value"] == 50.5
        assert result["unit"] == "mg"

    async def test_normalize_nutrient_none(self, test_session):
        """标准化 None 值"""
        svc = self._make_service(test_session)
        result = svc._normalize_nutrient_amount(None, preferred_unit="mg")
        assert result["value"] == 0

    async def test_normalize_nutrient_invalid_string(self, test_session):
        """标准化无效字符串"""
        svc = self._make_service(test_session)
        result = svc._normalize_nutrient_amount(
            "invalid", preferred_unit="mg", legacy_unit="mg"
        )
        assert result["value"] == 0.0

    async def test_build_trend_chart(self, test_session):
        """测试趋势图表数据构造"""
        svc = self._make_service(test_session)
        daily_data = [
            {"date": "2026-03-01", "calories": 1000, "protein": 50, "fat": 30, "carbs": 100},
            {"date": "2026-03-02", "calories": 1100, "protein": 55, "fat": 35, "carbs": 110},
        ]
        chart = svc._build_trend_chart(daily_data)
        assert chart["labels"] == ["03-01", "03-02"]
        assert chart["calories"] == [1000, 1100]
        assert len(chart["protein"]) == 2

    async def test_infer_additional_unit(self, test_session):
        """测试额外营养素单位推断"""
        svc = self._make_service(test_session)
        assert svc._infer_additional_unit("omega_3") == "g"
        assert svc._infer_additional_unit("DHA") == "g"
        assert svc._infer_additional_unit("selenium") == "ug"
        assert svc._infer_additional_unit("unknown_nutrient") == "mg"


@pytest.mark.asyncio
class TestMealServiceDB:
    """MealService 数据库操作测试"""

    async def test_complete_and_uncomplete_meal(
        self, test_session, test_user, test_pet, test_meals
    ):
        """测试完成/取消完成餐食"""
        from src.api.services.meal_service import MealService

        svc = MealService(test_session)
        meal = test_meals[0]

        # 完成餐食
        completed = await svc.complete_meal(test_user.id, meal.id, notes="好吃")
        assert completed is not None
        assert completed.is_completed is True
        assert completed.completed_at is not None
        assert completed.notes == "好吃"

        # 取消完成
        uncompleted = await svc.uncomplete_meal(test_user.id, meal.id)
        assert uncompleted is not None
        assert uncompleted.is_completed is False
        assert uncompleted.completed_at is None

    async def test_complete_nonexistent_meal(self, test_session, test_user):
        """完成不存在的餐食"""
        from src.api.services.meal_service import MealService

        svc = MealService(test_session)
        result = await svc.complete_meal(test_user.id, str(uuid.uuid4()))
        assert result is None

    async def test_calculate_nutrition_summary(self, test_session, test_meals):
        """测试营养摘要计算"""
        from src.api.services.meal_service import MealService

        svc = MealService(test_session)
        summary = await svc._calculate_nutrition_summary(test_meals)

        # 3 餐 x 200/350/300 = 850 总卡路里
        assert summary["total_calories"] == 850
        # 均未完成，consumed 应为 0
        assert summary["consumed_calories"] == 0
        # 3 餐 x 20g protein = 60g
        assert summary["protein"]["target"] == 60.0
        assert summary["protein"]["consumed"] == 0.0


# ==================== PetService 单元测试 ====================

@pytest.mark.asyncio
class TestPetServiceDB:
    """PetService 数据库操作测试"""

    async def test_create_and_get_pet(self, test_session, test_user):
        """创建并获取宠物"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        pet = await svc.create_pet(
            user_id=test_user.id,
            name="单元测试猫",
            type="cat",
            breed="橘猫",
            age=6,
            weight=3.0,
        )
        assert pet.id is not None
        assert pet.name == "单元测试猫"

        # 获取
        fetched = await svc.get_pet(test_user.id, pet.id)
        assert fetched is not None
        assert fetched.id == pet.id

    async def test_get_pet_other_user(self, test_session, test_user, second_user):
        """其他用户无法获取宠物"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        pet = await svc.create_pet(
            user_id=test_user.id, name="我的猫", type="cat", age=6, weight=3.0
        )
        assert await svc.get_pet(second_user.id, pet.id) is None

    async def test_update_pet(self, test_session, test_user):
        """更新宠物信息"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        pet = await svc.create_pet(
            user_id=test_user.id, name="旧名", type="dog", age=12, weight=10.0
        )
        updated = await svc.update_pet(test_user.id, pet.id, name="新名", weight=11.5)
        assert updated.name == "新名"
        assert float(updated.weight) == 11.5

    async def test_soft_delete_pet(self, test_session, test_user):
        """软删除宠物"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        pet = await svc.create_pet(
            user_id=test_user.id, name="待删除", type="cat", age=3, weight=2.0
        )
        assert await svc.delete_pet(test_user.id, pet.id) is True
        # 删除后无法通过普通查询获取
        assert await svc.get_pet(test_user.id, pet.id) is None

    async def test_get_pet_for_plan(self, test_session, test_user):
        """获取用于创建计划的宠物信息"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        pet = await svc.create_pet(
            user_id=test_user.id,
            name="计划猫",
            type="cat",
            breed="美短",
            age=12,
            weight=4.0,
            health_status="偏胖",
        )
        info = await svc.get_pet_for_plan(test_user.id, pet.id)
        assert info is not None
        assert info["pet_type"] == "cat"
        assert info["pet_breed"] == "美短"
        assert info["pet_weight"] == 4.0
        assert info["health_status"] == "偏胖"

    async def test_get_pet_for_plan_nonexistent(self, test_session, test_user):
        """不存在的宠物返回 None"""
        from src.api.services.pet_service import PetService

        svc = PetService(test_session)
        assert await svc.get_pet_for_plan(test_user.id, str(uuid.uuid4())) is None


# ==================== WeightService 单元测试 ====================

@pytest.mark.asyncio
class TestWeightServiceDB:
    """WeightService 数据库操作测试"""

    async def test_record_and_get_weight(self, test_session, test_user, test_pet):
        """记录并查询体重"""
        from src.api.services.weight_service import WeightService

        svc = WeightService(test_session)
        result = await svc.record_weight(test_user.id, test_pet.id, 5.0)
        assert result["weight"] == 5.0
        assert result["pet_id"] == test_pet.id

        # 获取最新
        latest = await svc.get_latest_weight(test_user.id, test_pet.id)
        assert latest is not None
        assert latest["weight"] == 5.0

    async def test_record_weight_updates_pet(self, test_session, test_user, test_pet):
        """记录体重应同步更新 Pet.weight"""
        from src.api.services.weight_service import WeightService

        svc = WeightService(test_session)
        await svc.record_weight(test_user.id, test_pet.id, 6.0)
        await test_session.refresh(test_pet)
        assert float(test_pet.weight) == 6.0

    async def test_weight_history_ordering(self, test_session, test_user, test_pet):
        """体重历史应按日期降序排列"""
        from src.api.services.weight_service import WeightService

        svc = WeightService(test_session)
        today = date.today()

        await svc.record_weight(
            test_user.id, test_pet.id, 4.0, recorded_date=today - timedelta(days=2)
        )
        await svc.record_weight(
            test_user.id, test_pet.id, 4.5, recorded_date=today - timedelta(days=1)
        )
        await svc.record_weight(test_user.id, test_pet.id, 5.0, recorded_date=today)

        history = await svc.get_weight_history(test_user.id, test_pet.id, days=30)
        assert len(history) >= 3
        # 验证降序
        dates = [h["recorded_date"] for h in history]
        assert dates == sorted(dates, reverse=True)

    async def test_record_weight_nonexistent_pet(self, test_session, test_user):
        """给不存在的宠物记录体重应抛出 ValueError"""
        from src.api.services.weight_service import WeightService

        svc = WeightService(test_session)
        with pytest.raises(ValueError, match="宠物不存在"):
            await svc.record_weight(test_user.id, str(uuid.uuid4()), 5.0)


# ==================== TaskService._sanitize_for_json 测试 ====================

@pytest.mark.asyncio
class TestSanitizeForJson:
    """JSON 清洗函数测试"""

    async def test_primitive_types(self):
        """基本类型直通"""
        from src.api.services.task_service import _sanitize_for_json

        assert _sanitize_for_json(None) is None
        assert _sanitize_for_json(True) is True
        assert _sanitize_for_json(42) == 42
        assert _sanitize_for_json(3.14) == 3.14
        assert _sanitize_for_json("hello") == "hello"

    async def test_dict_recursive(self):
        """dict 递归清洗"""
        from src.api.services.task_service import _sanitize_for_json

        result = _sanitize_for_json({"a": 1, "b": {"c": "deep"}})
        assert result == {"a": 1, "b": {"c": "deep"}}

    async def test_list_recursive(self):
        """list 递归清洗"""
        from src.api.services.task_service import _sanitize_for_json

        result = _sanitize_for_json([1, "two", [3]])
        assert result == [1, "two", [3]]

    async def test_set_to_list(self):
        """set 转为 list"""
        from src.api.services.task_service import _sanitize_for_json

        result = _sanitize_for_json({1, 2, 3})
        assert set(result) == {1, 2, 3}

    async def test_non_serializable_fallback(self):
        """不可序列化对象 fallback 到 str()"""
        from src.api.services.task_service import _sanitize_for_json

        class Custom:
            def __str__(self):
                return "custom_object"

        result = _sanitize_for_json(Custom())
        assert result == "custom_object"

    async def test_pydantic_model(self):
        """Pydantic 模型通过 model_dump 转换"""
        from src.api.services.task_service import _sanitize_for_json
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        result = _sanitize_for_json(TestModel(name="test", value=42))
        assert result == {"name": "test", "value": 42}
