"""
MinIO 文件存储封装
"""
import io
import logging
from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from src.api.config import settings

logger = logging.getLogger(__name__)

MINIO_REFERENCE_PREFIX = "minio://"


class MinioConfig:
    """MinIO配置类"""

    def __init__(self):
        self.endpoint = settings.minio_endpoint
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.secure = settings.minio_secure
        self.bucket_name = settings.minio_bucket

    def get_client(self) -> Minio:
        """获取MinIO客户端"""
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )


class MinioManager:
    """MinIO管理器"""

    def __init__(self, config: MinioConfig | None = None):
        self.config = config or MinioConfig()
        self.client: Minio | None = None
        self.bucket_name = self.config.bucket_name
        self._initialized = False

    def _ensure_initialized(self):
        """确保客户端已初始化"""
        if self._initialized:
            return

        try:
            self.client = self.config.get_client()
            self._ensure_bucket_exists()
            self._initialized = True
        except Exception:
            logger.exception("MinIO initialization failed")
            self._initialized = False
            raise

    def _ensure_bucket_exists(self):
        """确保bucket存在"""
        if self.client is None:
            raise RuntimeError("MinIO client is not initialized")

        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket: %s", self.bucket_name)
        except S3Error:
            logger.exception("Error creating MinIO bucket: %s", self.bucket_name)
            raise

    def upload_file(
        self,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """上传文件"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            file_stream = io.BytesIO(file_data)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_stream,
                length=len(file_data),
                content_type=content_type,
            )
            return True
        except S3Error:
            logger.exception("Error uploading file: %s", object_name)
            return False

    def upload_file_from_path(
        self,
        object_name: str,
        file_path: str,
        content_type: str | None = None,
    ) -> bool:
        """从路径上传文件"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type,
            )
            return True
        except S3Error:
            logger.exception("Error uploading file from path: %s", object_name)
            return False

    def download_file(self, object_name: str) -> Optional[bytes]:
        """下载文件"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            response = self.client.get_object(self.bucket_name, object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error:
            logger.exception("Error downloading file: %s", object_name)
            return None

    def download_file_to_path(self, object_name: str, file_path: str) -> bool:
        """下载文件到路径"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            self.client.fget_object(self.bucket_name, object_name, file_path)
            return True
        except S3Error:
            logger.exception("Error downloading file to path: %s", object_name)
            return False

    def delete_file(self, object_name: str) -> bool:
        """删除文件"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error:
            logger.exception("Error deleting file: %s", object_name)
            return False

    def list_files(self, prefix: str = "") -> list[str]:
        """列出文件"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error:
            logger.exception("Error listing files with prefix: %s", prefix)
            return []

    def get_file_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(days=7),
    ) -> Optional[str]:
        """获取文件的预签名URL"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires,
            )
        except S3Error:
            logger.exception("Error getting file URL: %s", object_name)
            return None

    def get_upload_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> Optional[str]:
        """获取上传的预签名URL"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            return self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires,
            )
        except S3Error:
            logger.exception("Error getting upload URL: %s", object_name)
            return None

    def file_exists(self, object_name: str) -> bool:
        """检查文件是否存在"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False

    def get_file_info(self, object_name: str) -> Optional[dict]:
        """获取文件信息"""
        try:
            self._ensure_initialized()
            if self.client is None:
                raise RuntimeError("MinIO client is not initialized")

            stat = self.client.stat_object(self.bucket_name, object_name)
            return {
                "object_name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type,
                "metadata": stat.metadata,
            }
        except S3Error:
            logger.exception("Error getting file info: %s", object_name)
            return None

    def build_object_reference(self, object_name: str) -> str:
        """构建数据库中保存的MinIO对象引用"""
        return f"{MINIO_REFERENCE_PREFIX}{self.bucket_name}/{object_name}"

    def extract_object_name(self, file_reference: Optional[str]) -> Optional[str]:
        """从数据库中的对象引用或URL提取object_name"""
        if not file_reference:
            return None

        if file_reference.startswith(MINIO_REFERENCE_PREFIX):
            raw_value = file_reference[len(MINIO_REFERENCE_PREFIX):]
            bucket_prefix = f"{self.bucket_name}/"
            if raw_value.startswith(bucket_prefix):
                return raw_value[len(bucket_prefix):]
            return None

        parsed = urlparse(file_reference)
        if not parsed.path:
            return None

        bucket_prefix = f"/{self.bucket_name}/"
        if bucket_prefix not in parsed.path:
            return None

        _, object_name = parsed.path.split(bucket_prefix, maxsplit=1)
        return object_name or None

    def resolve_file_url(self, file_reference: Optional[str]) -> Optional[str]:
        """将数据库中的文件引用解析为可访问URL"""
        if not file_reference:
            return None

        object_name = self.extract_object_name(file_reference)
        if not object_name:
            return file_reference

        return self.get_file_url(object_name) or file_reference


def get_minio_client() -> MinioManager:
    """获取MinIO客户端实例"""
    global _minio_client
    if "_minio_client" not in globals():
        _minio_client = MinioManager()
    return _minio_client


minio_client = get_minio_client()
