"""
Alembic 环境配置
"""
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 导入配置和模型
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.config import settings
from src.db.session import Base
from src.db.models import User, Task, DietPlan, RefreshToken  # 导入所有模型

# Alembic 配置对象
config = context.config

# 设置数据库 URL（使用同步连接字符串用于 Alembic）
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# 解析日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 模型的元数据（用于自动生成迁移）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式运行迁移（不连接数据库）
    生成 SQL 脚本而不是直接执行
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    在线模式运行迁移（连接数据库）
    使用异步引擎
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url_sync

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式运行迁移"""
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
