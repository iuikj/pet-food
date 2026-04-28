"""
体重记录 API 测试
覆盖体重记录、历史查询、最新体重、删除、同日多条记录
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestWeightRecord:
    """体重记录测试"""

    async def test_record_weight_success(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """正常记录体重"""
        response = await client.post(
            "/api/v1/weights/",
            json={
                "pet_id": test_pet.id,
                "weight": 4.8,
                "notes": "饭后称重",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["weight"] == 4.8
        assert data["data"]["pet_id"] == test_pet.id

    async def test_record_weight_with_date(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """指定日期记录体重"""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        response = await client.post(
            "/api/v1/weights/",
            json={
                "pet_id": test_pet.id,
                "weight": 4.6,
                "recorded_date": yesterday,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["recorded_date"] == yesterday

    async def test_record_weight_same_day_keeps_multiple_records(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """同日重复记录应保留多条历史"""
        first = await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": 4.5},
            headers=auth_headers,
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": 4.7},
            headers=auth_headers,
        )
        assert second.status_code == 200
        assert second.json()["data"]["weight"] == 4.7

        history = await client.get(
            f"/api/v1/weights/history?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert history.status_code == 200
        assert len(history.json()["data"]) == 2

    async def test_record_weight_invalid_pet(
        self, client: AsyncClient, auth_headers: dict
    ):
        """给不存在的宠物记录体重"""
        response = await client.post(
            "/api/v1/weights/",
            json={"pet_id": str(uuid.uuid4()), "weight": 5.0},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_record_weight_invalid_value(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """无效体重值（<=0 或 >500）"""
        response = await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": -1.0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_record_weight_no_auth(self, client: AsyncClient, test_pet):
        """未认证记录体重"""
        response = await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": 4.5},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestWeightHistory:
    """体重历史查询测试"""

    async def test_get_history_empty(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """空历史记录"""
        response = await client.get(
            f"/api/v1/weights/history?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    async def test_get_history_with_data(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_weight_record
    ):
        """有数据的历史查询"""
        response = await client.get(
            f"/api/v1/weights/history?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) >= 1

    async def test_get_history_custom_days(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """自定义天数范围"""
        response = await client.get(
            f"/api/v1/weights/history?pet_id={test_pet.id}&days=7",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_get_history_invalid_pet(
        self, client: AsyncClient, auth_headers: dict
    ):
        """不存在的宠物查询历史"""
        response = await client.get(
            f"/api/v1/weights/history?pet_id={uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestWeightLatest:
    """最新体重测试"""

    async def test_get_latest_weight(
        self, client: AsyncClient, auth_headers: dict, test_pet, test_weight_record
    ):
        """获取最新体重"""
        response = await client.get(
            f"/api/v1/weights/latest?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["weight"] == 4.5

    async def test_get_latest_weight_prefers_latest_created_same_day(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """同一天多次记录时，最新体重应返回最后一次创建的记录"""
        await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": 4.5},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/weights/",
            json={"pet_id": test_pet.id, "weight": 4.9},
            headers=auth_headers,
        )

        response = await client.get(
            f"/api/v1/weights/latest?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["weight"] == 4.9

    async def test_get_latest_weight_no_records(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """无记录时获取最新体重"""
        response = await client.get(
            f"/api/v1/weights/latest?pet_id={test_pet.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"] is None


@pytest.mark.asyncio
class TestWeightDelete:
    """体重记录删除测试"""

    async def test_delete_weight_record(
        self, client: AsyncClient, auth_headers: dict, test_weight_record
    ):
        """正常删除体重记录"""
        response = await client.delete(
            f"/api/v1/weights/{test_weight_record.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["record_id"] == test_weight_record.id

    async def test_delete_nonexistent_record(
        self, client: AsyncClient, auth_headers: dict
    ):
        """删除不存在的记录"""
        response = await client.delete(
            f"/api/v1/weights/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404
