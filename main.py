"""
项目主入口
可以直接运行此文件启动 FastAPI 服务
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn


def main():
    """主函数"""
    print("=" * 60)
    print("启动宠物饮食计划智能助手 API 服务")
    print("=" * 60)
    print()

    # 导入配置
    try:
        from src.api.config import settings
    except ImportError as e:
        print(f"配置导入失败: {e}")
        print("请确保已安装所有依赖：uv pip install -e .")
        sys.exit(1)

    # 显示服务信息
    print("服务信息:")
    print(f"   地址: http://{settings.api_host}:{settings.api_port}")
    print(f"   环境: {'开发' if settings.is_dev else '生产'}")
    print()
    print("API 文档:")
    print(f"   Swagger UI: http://{settings.api_host}:{settings.api_port}/docs")
    print(f"   ReDoc:      http://{settings.api_host}:{settings.api_port}/redoc")
    print()
    print("=" * 60)
    print()

    # 启动服务
    try:
        uvicorn.run(
            "src.api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.api_reload,
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        print("\n\n服务已停止")
    except Exception as e:
        print(f"\n\n服务启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
