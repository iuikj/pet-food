import os
from typing import List

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
from langchain_core.documents import Document
from langchain_milvus import Milvus, BM25BuiltInFunction
from langchain_openai import OpenAIEmbeddings
from pymilvus import DataType, MilvusClient

from src.rag.component import DashscopeEmbeddings


class MilvusManager:
    """
    Milvus
    """

    def __init__(self):
        # todo：需要从配置文件中加载获取配置
        self.connect = {
            "uri": os.getenv("MILVUS_URI"),
            "user": os.getenv("MILVUS_USER"),
            "password": os.getenv("MILVUS_PASSWORD"),
        }
        # --- Embedding 设置 ---
        self.embedding_model = os.getenv("MILVUS_EMBEDDING_MODEL")
        self.embedding_model_instance = None
        self.embedding_api_key = os.getenv("MILVUS_EMBEDDING_API_KEY")
        self.embedding_base_url = os.getenv("MILVUS_EMBEDDING_BASE_URL")
        self.embedding_dim: int = self._get_embedding_dimension(self.embedding_model)
        self.embedding_provider = os.getenv("MILVUS_EMBEDDING_PROVIDER", "openai")
        self.collection_name = os.getenv("MILVUS_COLLECTION")
        self._init_embedding_model()
        # ----rerank-----
        self.rerank_model=os.getenv("MILVUS_RERANK_MODEL")
        self.rerank_api_key = os.getenv("MILVUS_RERANK_API_KEY")
        # 向量库
        self.client = MilvusClient(
            **self.connect,
        )

    def _init_embedding_model(self) -> None:
        """Initialize the embedding model based on configuration."""
        kwargs = {
            "api_key": self.embedding_api_key,
            "model": self.embedding_model,
            "base_url": self.embedding_base_url,
            "model_kwargs": {
                "encoding_format": "float",
            },
            "dimensions": self.embedding_dim,
        }
        if self.embedding_provider.lower() == "openai":
            self.embedding_model_instance = OpenAIEmbeddings(**kwargs)
        elif self.embedding_provider.lower() == "dashscope":
            self.embedding_model_instance = DashscopeEmbeddings(**kwargs)
        else:
            raise ValueError(
                f"Unsupported embedding provider: {self.embedding_provider}. "
                "Supported providers: openai,dashscope"
            )

    def _get_embedding_dimension(self, model_name: str) -> int:
        """Return embedding dimension for the supplied model name."""
        # Common OpenAI embedding model dimensions
        embedding_dims = {
            "text-embedding-ada-002": 1536,
            "text-embedding-v4": 2048,
        }

        # Check if user has explicitly set the dimension
        explicit_dim = os.getenv("MILVUS_EMBEDDING_DIM", 0)
        if explicit_dim > 0:
            return explicit_dim
        # Return the dimension for the specified model
        return embedding_dims.get(model_name, 1536)  # Default to 1536

    async def _init_contextual_compression_retriever(self, k: int) -> ContextualCompressionRetriever:
        try:
            v = await self.get_vector_store()
            # compressor = RankLLMRerank(top_n=k, model="gpt", gpt_model="gpt-4o-mini")  # 使用的rerank模型,且最终返回多少值取决于这个
            compressor = DashScopeRerank(
                top_n=k,
                model=self.rerank_model,
                dashscope_api_key=self.rerank_api_key
            )
            compression_retriever = ContextualCompressionRetriever(
                base_compressor=compressor, base_retriever=v.as_retriever(
                    search_kwargs={  # 传递搜索参数，采取权重的rerank方式
                        "k": k,
                        "ranker_type": "weighted",
                        "ranker_params": {"weights": [0.6, 0.4]}
                    }
                )
            )
            return compression_retriever
        except Exception as e:
            print(f"Error initializing ContextualCompressionRetriever: {e}")

    async def create_vector_store_from_documents(self, documents, connect=None, drop=False):
        analyzer_params = {
            "tokenizer": "jieba",  # 使用中文分词
            "filter": [
                "lowercase",
                {
                    "type": "stop",
                    "stop_words": [
                        "，",
                        "。",
                        "；",
                        "：",
                    ]
                }
            ]
        }
        # 创建向量存储
        vector_store = Milvus.from_documents(
            documents=documents,
            embedding=self.embedding_model_instance,
            builtin_function=BM25BuiltInFunction(analyzer_params=analyzer_params),
            vector_field=["dense", "sparse"],  # 同时存储密集向量和稀疏向量
            connection_args=connect if connect else self.connect,
            collection_name=self.collection_name,
            enable_dynamic_field=True,  # 添加此参数
        )
        return vector_store

    async def get_vector_store(self, connect=None):
        embeddings = self.embedding_model_instance
        analyzer_params = {
            "tokenizer": "jieba",  # 使用中文分词
            "filter": [
                "lowercase",
                {
                    "type": "stop",
                    "stop_words": [
                        "，",
                        "。",
                        "；",
                        "：",
                    ]
                }
            ]
        }
        # 创建向量存储
        vector_store = Milvus(
            embedding_function=embeddings,
            builtin_function=BM25BuiltInFunction(analyzer_params=analyzer_params),
            vector_field=["dense", "sparse"],  # 同时存储密集向量和稀疏向量
            connection_args=connect if connect else self.connect,
            collection_name=self.collection_name,
        )
        return vector_store

    async def drop_collection(self):
        """
        删除向量库
        """
        client = MilvusClient(
            **self.connect,
        )
        client.drop_collection(collection_name=self.collection_name)
        print(f"已删除向量库：{self.collection_name}")

    async def _init_collection(self):
        """
        用于初始化collection
        """
        milvus = Milvus(
            connection_args=self.connect,
            collection_name=self.collection_name,
            embedding_function=self.embedding_model_instance
        ).client
        schema = milvus.create_schema(
            auto_id=False,
            enable_dynamic_field=True,
        )
        schema.add_field(field_name="pk", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="dense", datatype=DataType.FLOAT_VECTOR)
        schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field()

    async def show_schema(self):
        """
        查看schema
        """
        client = MilvusClient(
            **self.connect,
        )
        client.list_collections()
        print(client.describe_collection(self.collection_name))

    # async def search_with_hybrid_rerank(self, query: str, k: int = 3) -> list[RagClause]:
    #     # 混合检索
    #     vector_store = await self.get_vector_store()
    #     col_search_res: List[Document] = vector_store.similarity_search(
    #         query=query,
    #         k=k,
    #         ranker_type="weighted",
    #         ranker_params={"weights": [0.6, 0.4]}
    #     )
    #     print(
    #         f"混合检索结果：{col_search_res}"
    #     )
    #     result: list[RagClause] = []
    #     if col_search_res:
    #         for res in col_search_res:
    #             pk = res.metadata.get("pk")
    #             # 使用 pk 查询完整数据
    #             full_data = vector_store.col.query(
    #                 expr=f"pk == {pk}",
    #                 output_fields=["text", "law_name", "part_name", "chapter_name", "article_number"],
    #                 limit=1
    #             )[0]
    #             result.append(
    #                 RagClause(
    #                     law_name=full_data.get("law_name"),
    #                     part_name=full_data.get("part_name"),
    #                     chapter_name=full_data.get("chapter_name"),
    #                     article_number=full_data.get("article_number"),
    #                     content=full_data.get("text")
    #                 )
    #             )
    #     return result
    #
    # async def search_with_model_rerank(self, query: str, k: int = 3) -> list[RagClause]:
    #     """
    #     使用rerank模型
    #     """
    #     compression_retriever = await self._init_contextual_compression_retriever(k)
    #     col_search_res: List[Document] = compression_retriever.invoke(
    #         input=query,
    #         k=k,
    #     )
    #     vector_store = await self.get_vector_store()
    #     result: list[RagClause] = []
    #     if col_search_res:
    #         for res in col_search_res:
    #             pk = res.metadata.get("pk")
    #             # 使用 pk 查询完整数据
    #             full_data = vector_store.col.query(
    #                 expr=f"pk == {pk}",
    #                 output_fields=["text", "law_name", "part_name", "chapter_name", "article_number"],
    #                 limit=1
    #             )[0]
    #             result.append(
    #                 RagClause(
    #                     law_name=full_data.get("law_name"),
    #                     part_name=full_data.get("part_name"),
    #                     chapter_name=full_data.get("chapter_name"),
    #                     article_number=full_data.get("article_number"),
    #                     content=full_data.get("text")
    #                 )
    #             )
    #     return result
