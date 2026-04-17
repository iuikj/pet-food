"""
LangChain 模型提供商懒注册。

将 langchain_qwq / langchain_siliconflow / langchain_dev_utils 等重型依赖
从 `src/__init__.py` 的顶层 import 中解耦：只有在真正构建 Agent 图时
才触发一次注册，其他纯 API 路径（登录、查宠物、看餐食等）无需为 LLM
栈付冷启动代价。

使用方式：在每个 build_*_graph(...) 函数入口调用 `ensure_providers_registered()` 即可，
内部通过模块级标志保证幂等。
"""
from __future__ import annotations

import threading

_providers_registered = False
_dotenv_loaded = False
_lock = threading.Lock()


def ensure_dotenv_loaded(dotenv_path: str = ".env", override: bool = True) -> None:
    """按需加载 .env，避免 import 期触发文件 IO。幂等。"""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    with _lock:
        if _dotenv_loaded:
            return
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=dotenv_path, override=override)
        _dotenv_loaded = True


def ensure_providers_registered() -> None:
    """按需注册 LangChain 厂商；重复调用开销为 O(1)。"""
    global _providers_registered
    if _providers_registered:
        return
    with _lock:
        if _providers_registered:
            return

        from langchain_dev_utils.chat_models import batch_register_model_provider
        from langchain_qwq import ChatQwen
        from langchain_siliconflow import ChatSiliconFlow

        batch_register_model_provider(
            providers=[
                {
                    "provider_name": "dashscope",
                    "chat_model": ChatQwen,
                },
                {
                    "provider_name": "siliconflow",
                    "chat_model": ChatSiliconFlow,
                },
                {
                    "provider_name": "zai",
                    "chat_model": "openai-compatible",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                },
                {
                    "provider_name": "moonshot",
                    "chat_model": "openai-compatible",
                    "base_url": "https://api.moonshot.cn/v1",
                },
            ]
        )
        _providers_registered = True
