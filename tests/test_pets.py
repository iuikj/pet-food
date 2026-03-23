"""
宠物管理 API 测试
覆盖宠物 CRUD 全流程：创建、列表、详情、更新、删除
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPetCreate:
    """宠物创建测试"""

    async def test_create_pet_success(self, client: AsyncClient, auth_headers: dict):
        """创建宠物 - 正常流程"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "name": "小花",
                "type": "cat",
                "breed": "布偶",
                "age": 6,
                "weight": 3.5,
                "gender": "female",
                "health_status": "健康",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        pet = data["data"]
        assert pet["name"] == "小花"
        assert pet["type"] == "cat"
        assert pet["breed"] == "布偶"
        assert pet["age"] == 6
        assert pet["weight"] == 3.5
        assert pet["is_active"] is True
        assert pet["has_plan"] is False

    async def test_create_pet_dog(self, client: AsyncClient, auth_headers: dict):
        """创建狗宠物"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "name": "大黄",
                "type": "dog",
                "breed": "拉布拉多",
                "age": 24,
                "weight": 30.0,
                "gender": "male",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["type"] == "dog"

    async def test_create_pet_minimal_fields(self, client: AsyncClient, auth_headers: dict):
        """仅提供必填字段创建宠物"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "name": "简简",
                "type": "cat",
                "age": 3,
                "weight": 2.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["breed"] is None

    async def test_create_pet_invalid_type(self, client: AsyncClient, auth_headers: dict):
        """无效宠物类型应返回 422"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "name": "小鸟",
                "type": "bird",
                "age": 6,
                "weight": 0.5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_pet_missing_name(self, client: AsyncClient, auth_headers: dict):
        """缺少必填字段应返回 422"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "type": "cat",
                "age": 6,
                "weight": 3.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_pet_no_auth(self, client: AsyncClient):
        """未认证创建宠物应返回 401"""
        response = await client.post(
            "/api/v1/pets/",
            json={
                "name": "未认证猫",
                "type": "cat",
                "age": 6,
                "weight": 3.0,
            },
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPetList:
    """宠物列表测试"""

    async def test_list_pets_empty(self, client: AsyncClient, auth_headers: dict):
        """空列表查询"""
        response = await client.get("/api/v1/pets/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0
        assert data["data"]["items"] == []

    async def test_list_pets_with_data(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """有数据时查询宠物列表"""
        response = await client.get("/api/v1/pets/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] >= 1
        items = data["data"]["items"]
        pet_ids = [p["id"] for p in items]
        assert test_pet.id in pet_ids

    async def test_list_pets_no_auth(self, client: AsyncClient):
        """未认证查询应返回 401"""
        response = await client.get("/api/v1/pets/")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPetDetail:
    """宠物详情测试"""

    async def test_get_pet_success(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """正常获取宠物详情"""
        response = await client.get(
            f"/api/v1/pets/{test_pet.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["id"] == test_pet.id
        assert data["data"]["name"] == "测试猫咪"

    async def test_get_pet_not_found(self, client: AsyncClient, auth_headers: dict):
        """查询不存在的宠物应返回 404"""
        response = await client.get(
            "/api/v1/pets/nonexistent-id", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_get_pet_other_user(
        self, client: AsyncClient, second_auth_headers: dict, test_pet
    ):
        """其他用户无法访问别人的宠物"""
        response = await client.get(
            f"/api/v1/pets/{test_pet.id}", headers=second_auth_headers
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestPetUpdate:
    """宠物更新测试"""

    async def test_update_pet_name(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """更新宠物名称"""
        response = await client.put(
            f"/api/v1/pets/{test_pet.id}",
            json={"name": "新名字"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "新名字"

    async def test_update_pet_weight(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """更新宠物体重"""
        response = await client.put(
            f"/api/v1/pets/{test_pet.id}",
            json={"weight": 5.2},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["weight"] == 5.2

    async def test_update_pet_not_found(self, client: AsyncClient, auth_headers: dict):
        """更新不存在的宠物"""
        response = await client.put(
            "/api/v1/pets/nonexistent-id",
            json={"name": "不存在"},
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestPetDelete:
    """宠物删除测试"""

    async def test_delete_pet_success(
        self, client: AsyncClient, auth_headers: dict, test_pet
    ):
        """正常删除宠物（软删除）"""
        response = await client.delete(
            f"/api/v1/pets/{test_pet.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["pet_id"] == test_pet.id

        # 验证已无法通过详情接口获取
        detail_resp = await client.get(
            f"/api/v1/pets/{test_pet.id}", headers=auth_headers
        )
        assert detail_resp.status_code == 404

    async def test_delete_pet_not_found(self, client: AsyncClient, auth_headers: dict):
        """删除不存在的宠物"""
        response = await client.delete(
            "/api/v1/pets/nonexistent-id", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_pet_other_user(
        self, client: AsyncClient, second_auth_headers: dict, test_pet
    ):
        """其他用户无法删除别人的宠物"""
        response = await client.delete(
            f"/api/v1/pets/{test_pet.id}", headers=second_auth_headers
        )
        assert response.status_code == 404
