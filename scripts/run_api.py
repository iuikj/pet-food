#!/usr/bin/env python3
"""
FastAPI 开发服务器启动脚本
"""
import subprocess
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """启动 FastAPI 开发服务器"""
    print("=" * 50)
    print("启动 FastAPI 开发服务器")
    print("=" * 50)
    print()

    # 检查 .env 文件
    env_file = project_root / ".env"
    if not env_file.exists():
        print("❌ 错误: 未找到 .env 文件")
        print("请先运行: scripts/start-dev.bat (Windows) 或 scripts/start-dev.sh (Linux/macOS)")
        sys.exit(1)

    # 显示服务信息
    print("📝 服务信息:")
    print("   地址: http://0.0.0.0:8000")
    print("   本地: http://localhost:8000")
    print()
    print("📚 API 文档:")
    print("   Swagger UI: http://localhost:8000/docs")
    print("   ReDoc:      http://localhost:8000/redoc")
    print()
    print("🔧 开发模式:")
    print("   ✅ 自动重载已启用")
    print("   ✅ 详细日志已启用")
    print()
    print("=" * 50)
    print()

    # 启动 uvicorn
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "src.api.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "info"
        ], check=True)
    except KeyboardInterrupt:
        print("\n\n✅ 服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n\n❌ 服务器启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
