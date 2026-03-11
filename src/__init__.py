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
