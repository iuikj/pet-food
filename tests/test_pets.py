"""
宠物管理 API 测试
覆盖宠物 CRUD 全流程：创建、列表、详情、更新、删除
"""
import pytest
from httpx import AsyncClient

import src.api.routes.pets as pets_route_module
import src.api.infrastructure.minio_storage as minio_storage_module


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


class FakeMinioStorage:
    def __init__(self):
        self.uploaded = {}
        self.deleted = []

    def upload_file(self, object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> bool:
        self.uploaded[object_name] = {
            "data": file_data,
            "content_type": content_type,
        }
        return True

    def delete_file(self, object_name: str) -> bool:
        self.deleted.append(object_name)
        self.uploaded.pop(object_name, None)
        return True

    def build_object_reference(self, object_name: str) -> str:
        return f"minio://petfood-bucket/{object_name}"

    def extract_object_name(self, file_reference):
        prefix = "minio://petfood-bucket/"
        if not file_reference or not file_reference.startswith(prefix):
            return None
        return file_reference.removeprefix(prefix)

    def resolve_file_url(self, file_reference, request_host=None):
        object_name = self.extract_object_name(file_reference)
        if object_name:
            host_prefix = request_host or "minio.test"
            return f"https://{host_prefix}/petfood-bucket/{object_name}"
        return file_reference

    def download_file(self, object_name: str):
        stored = self.uploaded.get(object_name)
        if not stored:
            return None
        return stored["data"]

    def get_file_info(self, object_name: str):
        stored = self.uploaded.get(object_name)
        if not stored:
            return None
        return {
            "object_name": object_name,
            "content_type": stored["content_type"],
        }


class FakePresignMinioClient:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool):
        self.endpoint = endpoint
        self.secure = secure

    def presigned_get_object(self, bucket_name: str, object_name: str, expires):
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}/{bucket_name}/{object_name}"


@pytest.mark.asyncio
class TestPetAvatarUpload:
    async def test_upload_pet_avatar_success(
        self, client: AsyncClient, auth_headers: dict, test_pet, monkeypatch
    ):
        fake_storage = FakeMinioStorage()
        monkeypatch.setattr(pets_route_module, "get_minio_storage", lambda: fake_storage)

        response = await client.post(
            f"/api/v1/pets/{test_pet.id}/avatar",
            files={"file": ("avatar.png", b"fake-image-bytes", "image/png")},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["avatar_url"].startswith("http://test/api/v1/pets/avatar/object/avatars/pets/")
        assert len(fake_storage.uploaded) == 1

    async def test_get_pet_avatar_object_success(
        self, client: AsyncClient, monkeypatch
    ):
        fake_storage = FakeMinioStorage()
        object_name = "avatars/pets/demo/avatar.png"
        fake_storage.uploaded[object_name] = {
            "data": b"fake-image-bytes",
            "content_type": "image/png",
        }
        monkeypatch.setattr(pets_route_module, "get_minio_storage", lambda: fake_storage)

        response = await client.get(f"/api/v1/pets/avatar/object/{object_name}")

        assert response.status_code == 200
        assert response.content == b"fake-image-bytes"
        assert response.headers["content-type"].startswith("image/png")
        assert response.headers["cache-control"] == "public, max-age=3600"

    async def test_upload_pet_avatar_invalid_content_type(
        self, client: AsyncClient, auth_headers: dict, test_pet, monkeypatch
    ):
        fake_storage = FakeMinioStorage()
        monkeypatch.setattr(pets_route_module, "get_minio_storage", lambda: fake_storage)

        response = await client.post(
            f"/api/v1/pets/{test_pet.id}/avatar",
            files={"file": ("avatar.gif", b"gif-bytes", "image/gif")},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["message"]["code"] == 5002
        assert fake_storage.uploaded == {}

    async def test_upload_pet_avatar_too_large(
        self, client: AsyncClient, auth_headers: dict, test_pet, monkeypatch
    ):
        fake_storage = FakeMinioStorage()
        monkeypatch.setattr(pets_route_module, "get_minio_storage", lambda: fake_storage)

        response = await client.post(
            f"/api/v1/pets/{test_pet.id}/avatar",
            files={"file": ("avatar.jpg", b"a" * (2 * 1024 * 1024 + 1), "image/jpeg")},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["message"]["code"] == 5003
        assert fake_storage.uploaded == {}


class TestMinioPresignEndpoint:
    def test_get_file_url_uses_request_host_when_endpoint_is_localhost(self, monkeypatch):
        monkeypatch.setattr(minio_storage_module, "Minio", FakePresignMinioClient)

        config = minio_storage_module.MinioConfig()
        config.endpoint = "localhost:9000"
        config.secure = False
        config.public_endpoint = ""

        storage = minio_storage_module.MinioManager(config=config)
        file_url = storage.get_file_url("avatars/pets/demo.png", request_host="10.16.48.216")

        assert file_url == "http://10.16.48.216:9000/petfood-bucket/avatars/pets/demo.png"

    def test_get_file_url_prefers_public_endpoint(self, monkeypatch):
        monkeypatch.setattr(minio_storage_module, "Minio", FakePresignMinioClient)

        config = minio_storage_module.MinioConfig()
        config.endpoint = "localhost:9000"
        config.secure = False
        config.public_endpoint = "https://cdn.example.com:9443"

        storage = minio_storage_module.MinioManager(config=config)
        file_url = storage.get_file_url("avatars/pets/demo.png", request_host="10.16.48.216")

        assert file_url == "https://cdn.example.com:9443/petfood-bucket/avatars/pets/demo.png"
