from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)


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

# from src.agent.v0.graph import build_graph_with_langgraph_studio  # noqa: E402
# from src.agent.v1.graph import build_v1_graph  # noqa: E402
# from src.agent.v2.node import plan_agent
# # 注册模型提供商并加载模型
# # register_model_provider("dashscope", "openai-compatible", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
#
#
#
#
#
#
#
# __all__ = ["build_graph_with_langgraph_studio", "build_v1_graph","plan_agent"]
