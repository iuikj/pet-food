"""
餐食记录与日历 API 测试
覆盖餐食查询、完成标记、历史记录、日历视图
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTodayMeals:
    """今日餐食测试"""

    async def test_get_today_meals(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """获取今日餐食列表"""
        response = await client.get(
            f"/api/v1/meals/today?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        meals_data = data["data"]
        assert meals_data["date"] == date.today().isoformat()
        assert len(meals_data["meals"]) == 3

        # 验证营养摘要结构
        summary = meals_data["nutrition_summary"]
        assert "total_calories" in summary
        assert "protein" in summary
        assert "fat" in summary
        assert "carbs" in summary

    async def test_get_today_meals_empty(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """无餐食数据时查询"""
        response = await client.get(
            f"/api/v1/meals/today?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["meals"] == []

    async def test_get_today_meals_invalid_pet(
        self, client: AsyncClient, auth_headers: dict
    ):
        """查询不存在宠物的餐食"""
        response = await client.get(
            f"/api/v1/meals/today?pet_id={uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_get_today_meals_no_auth(self, client: AsyncClient, test_pet):
        """未认证查询今日餐食"""
        response = await client.get(f"/api/v1/meals/today?pet_id={test_pet.id}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestMealsByDate:
    """按日期查询餐食测试"""

    async def test_get_meals_by_date(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """按日期查询餐食"""
        today = date.today().isoformat()
        response = await client.get(
            f"/api/v1/meals/date?pet_id={test_pet.id}&target_date={today}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]["meals"]) == 3

    async def test_get_meals_invalid_date_format(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """无效日期格式"""
        response = await client.get(
            f"/api/v1/meals/date?pet_id={test_pet.id}&target_date=invalid",
            headers=auth_headers,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestMealComplete:
    """餐食完成标记测试"""

    async def test_complete_meal(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """标记餐食完成"""
        meal_id = test_meals[0].id
        response = await client.post(
            f"/api/v1/meals/{meal_id}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["is_completed"] is True
        assert data["data"]["completed_at"] is not None

    async def test_uncomplete_meal(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """取消餐食完成标记"""
        meal_id = test_meals[0].id
        # 先标记完成
        await client.post(
            f"/api/v1/meals/{meal_id}/complete", headers=auth_headers
        )
        # 再取消
        response = await client.delete(
            f"/api/v1/meals/{meal_id}/complete", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["is_completed"] is False

    async def test_complete_nonexistent_meal(
        self, client: AsyncClient, auth_headers: dict
    ):
        """标记不存在的餐食"""
        response = await client.post(
            f"/api/v1/meals/{uuid.uuid4()}/complete",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMealHistory:
    """餐食历史测试"""

    async def test_get_meal_history(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """获取餐食历史"""
        response = await client.get(
            f"/api/v1/meals/history?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] >= 3
        assert data["data"]["page"] == 1

    async def test_get_meal_history_pagination(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """餐食历史分页"""
        response = await client.get(
            f"/api/v1/meals/history?pet_id={test_pet.id}&page=1&page_size=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page_size"] == 2
        assert len(data["data"]["items"]) <= 2

    async def test_get_meal_history_with_date_range(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """按日期范围查询餐食历史"""
        today = date.today().isoformat()
        response = await client.get(
            f"/api/v1/meals/history?pet_id={test_pet.id}&start_date={today}&end_date={today}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_get_meal_history_invalid_date(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """无效日期格式"""
        response = await client.get(
            f"/api/v1/meals/history?pet_id={test_pet.id}&start_date=bad-date",
            headers=auth_headers,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestMonthlyCalendar:
    """月度日历测试"""

    async def test_get_monthly_calendar(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """获取月度日历"""
        today = date.today()
        response = await client.get(
            f"/api/v1/calendar/monthly?pet_id={test_pet.id}&year={today.year}&month={today.month}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        calendar = data["data"]
        assert calendar["year"] == today.year
        assert calendar["month"] == today.month
        assert len(calendar["days"]) >= 28

    async def test_monthly_calendar_with_meals(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_meals
    ):
        """有餐食数据的月度日历"""
        today = date.today()
        response = await client.get(
            f"/api/v1/calendar/monthly?pet_id={test_pet.id}&year={today.year}&month={today.month}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        days = data["data"]["days"]
        # 找到今天的数据
        today_data = next(
            (d for d in days if d["date"] == today.isoformat()), None
        )
        assert today_data is not None
        assert today_data["has_plan"] is True
        assert today_data["total_meals"] == 3

    async def test_monthly_calendar_default_params(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """不传年月参数，使用默认值"""
        response = await client.get(
            f"/api/v1/calendar/monthly?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_monthly_calendar_invalid_pet(
        self, client: AsyncClient, auth_headers: dict
    ):
        """查询不存在宠物的日历"""
        response = await client.get(
            f"/api/v1/calendar/monthly?pet_id={uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestWeeklyCalendar:
    """周度日历测试"""

    async def test_get_weekly_calendar(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """获取周度日历"""
        response = await client.get(
            f"/api/v1/calendar/weekly?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        week = data["data"]
        assert "days" in week
        assert len(week["days"]) == 7

    async def test_weekly_calendar_with_start_date(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """指定起始日期的周度日历"""
        today = date.today().isoformat()
        response = await client.get(
            f"/api/v1/calendar/weekly?pet_id={test_pet.id}&start_date={today}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["start_date"] == today

    async def test_weekly_calendar_invalid_pet(
        self, client: AsyncClient, auth_headers: dict
    ):
        """查询不存在宠物的周历"""
        response = await client.get(
            f"/api/v1/calendar/weekly?pet_id={uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404
