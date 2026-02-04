"""
认证相关测试
测试用户注册、登录、Token 刷新等功能
"""
import pytest
from httpx import AsyncClient

from src.api.main import app


@pytest.mark.asyncio
class TestAuthEndpoints:
    """认证接口测试"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_register_success(self, client: AsyncClient, test_user_data: dict):
        """测试用户注册成功"""
        response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "user" in data["data"]
        assert "tokens" in data["data"]
        assert "access_token" in data["data"]["tokens"]
        assert "refresh_token" in data["data"]["tokens"]

    async def test_register_duplicate_username(self, client: AsyncClient, test_user_data: dict):
        """测试用户名重复"""
        # 首次注册
        await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )

        # 再次注册（应该失败）
        response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )

        assert response.status_code == 409
        data = response.json()
        assert "已存在" in data["message"]

    async def test_register_invalid_username(self, client: AsyncClient):
        """测试无效用户名"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user@name",  # 包含非法字符
                "email": "test@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == 422

    async def test_login_success(self, client: AsyncClient, test_user_data: dict):
        """测试用户登录成功"""
        # 先注册
        await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )

        # 登录
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "tokens" in data["data"]

    async def test_login_invalid_credentials(self, client: AsyncClient):
        """测试无效登录凭据"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "wrongpass"
            }
        )

        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401

    async def test_refresh_token_success(self, client: AsyncClient, test_user_data: dict):
        """测试刷新 Token 成功"""
        # 先注册
        register_response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        refresh_token = register_response.json()["data"]["tokens"]["refresh_token"]

        # 刷新 Token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]

    async def test_refresh_token_invalid(self, client: AsyncClient):
        """测试无效的刷新 Token"""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "无效" in data["message"] or "过期" in data["message"]

    async def test_get_current_user_success(
        self,
        client: AsyncClient,
        test_user_data: dict
    ):
        """测试获取当前用户成功"""
        # 先注册
        register_response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        access_token = register_response.json()["data"]["tokens"]["access_token"]

        # 获取用户信息
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["username"] == test_user_data["username"]

    async def test_get_current_user_without_token(self, client: AsyncClient):
        """测试未提供 Token 获取用户"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401


@pytest.mark.asyncio
class TestAuthValidators:
    """认证验证器测试"""

    async def test_password_hashing(self):
        """测试密码哈希"""
        from src.api.utils.security import hash_password, verify_password

        password = "testpassword"
        hashed = hash_password(password)

        assert hashed != password
        assert isinstance(hashed, str)
        assert len(hashed) > 50

        # 验证密码
        assert verify_password(password, hashed)
        assert not verify_password("wrongpassword", hashed)

    async def test_token_generation(self):
        """测试 Token 生成"""
        from src.api.utils.security import create_access_token, decode_token

        user_id = "test-user-id"
        username = "testuser"

        # 生成 Access Token
        access_token = create_access_token(user_id, username)

        assert isinstance(access_token, str)
        assert len(access_token) > 50

        # 解码 Token
        payload = decode_token(access_token)

        assert payload["sub"] == user_id
        assert payload["username"] == username
        assert "type" in payload
        assert payload["type"] == "access"

    async def test_token_validation(self):
        """测试 Token 验证"""
        from src.api.utils.security import (
            create_access_token,
            create_refresh_token,
            verify_token
        )

        user_id = "test-user-id"
        username = "testuser"

        # 生成 Access Token 和 Refresh Token
        access_token = create_access_token(user_id, username)
        refresh_token = create_refresh_token(user_id, username)

        # 验证 Access Token
        access_payload = verify_token(access_token, "access")
        assert access_payload["type"] == "access"

        # 验证 Refresh Token
        refresh_payload = verify_token(refresh_token, "refresh")
        assert refresh_payload["type"] == "refresh"

        # 验证类型不匹配应该失败
        with pytest.raises(ValueError, match="类型错误"):
            verify_token(access_token, "refresh")
