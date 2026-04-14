"""
RAG 知识库检索工具 -- 占位实现

后续接入 src/rag/milvus.py 的 MilvusManager 实现混合检索。
当前返回提示信息，不会误导 Agent。
"""
from typing import Annotated

from langchain.tools import tool


@tool
async def rag_search_tool(
    query: Annotated[str, "搜索查询，如'猫咪牛磺酸需求量''幼犬蛋白质比例''食材钙磷比'"],
    top_k: Annotated[int, "返回结果数量"] = 5,
) -> list[dict]:
    """搜索宠物营养知识库，获取关于宠物饮食、营养需求、食材搭配等专业知识。

    注意: 此工具当前为占位实现。请优先使用 ingredient_search_tool
    和 nutrition_requirement_tool 获取结构化数据。
    """
    # TODO: 接入 MilvusManager 实现真实 RAG 检索
    # from src.rag.milvus import MilvusManager
    # mm = MilvusManager()
    # vector_store = await mm.get_vector_store()
    # results = vector_store.similarity_search(query, k=top_k)
    # return [
    #     {"content": doc.page_content, "source": doc.metadata.get("source", "")}
    #     for doc in results
    # ]

    return [{
        "content": (
            f"[RAG 占位] 未找到关于 '{query}' 的知识库内容。"
            "请使用 ingredient_search_tool 查询食材数据库，"
            "或使用 nutrition_requirement_tool 获取营养标准。"
        ),
        "source": "placeholder",
    }]
