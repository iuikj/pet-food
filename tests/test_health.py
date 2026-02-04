"""
健康检查和 API 基础测试
"""
import pytest
from httpx import AsyncClient

from src.api.main import app


@pytest.mark.asyncio
class TestHealthEndpoints:
    """健康检查接口测试"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_root_endpoint(self, client: AsyncClient):
        """测试根路由"""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert data["data"]["name"] == "Pet Food Diet Plan Assistant"

    async def test_health_check(self, client: AsyncClient):
        """测试基础健康检查"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "healthy"
        assert "version" in data["data"]

    async def test_health_check_detail(self, client: AsyncClient):
        """测试详细健康检查"""
        response = await client.get("/health/detail")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "components" in data["data"]
        assert "database" in data["data"]["components"]
        assert "redis" in data["data"]["components"]


@pytest.mark.asyncio
class TestAPIDocumentation:
    """API 文档测试"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_swagger_docs(self, client: AsyncClient):
        """测试 Swagger 文档"""
        response = await client.get("/docs")

        assert response.status_code == 200
        assert "swagger" in response.text.lower()
        assert "openapi" in response.text.lower()

    async def test_redoc_docs(self, client: AsyncClient):
        """测试 ReDoc 文档"""
        response = await client.get("/redoc")

        assert response.status_code == 200
        assert "redoc" in response.text.lower()

    async def test_openapi_schema(self, client: AsyncClient):
        """测试 OpenAPI Schema"""
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "components" in schema
        assert "/api/v1/auth" in schema["paths"]


@pytest.mark.asyncio
class TestErrorHandling:
    """错误处理测试"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_404_not_found(self, client: AsyncClient):
        """测试 404 错误"""
        response = await client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404

    async def test_405_method_not_allowed(self, client: AsyncClient):
        """测试 405 错误"""
        response = await client.put("/api/v1/auth/register")

        assert response.status_code == 405

    async def test_422_validation_error(self, client: AsyncClient):
        """测试 422 验证错误"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "",  # 必填字段为空
                "email": "not-an-email",
                "password": "123"  # 密码太短
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == 422
        assert "detail" in data

    async def test_cors_headers(self, client: AsyncClient):
        """测试 CORS 响应头"""
        response = await client.get("/")

        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
