from typing import Any, List, Sequence


class DashscopeEmbeddings:
    """OpenAI-compatible embeddings wrapper."""

    def __init__(self, **kwargs: Any) -> None:
        self._client: OpenAI = OpenAI(
            api_key=kwargs.get("api_key", ""), base_url=kwargs.get("base_url", "")
        )
        self._model: str = kwargs.get("model", "")
        self._encoding_format: str = kwargs.get("encoding_format", "float")

    def embed_documents(self, texts: Sequence) -> List[List[float]]:
        """
        接受 Document、dict 或 str 列表，生成 embeddings。
        """
        # 统一提取文本
        clean_texts = []
        for t in texts:
            if isinstance(t, Document):
                clean_texts.append(t.page_content)
            elif isinstance(t, dict) and "page_content" in t:
                clean_texts.append(str(t["page_content"]))
            else:
                clean_texts.append(str(t))

        # 调用内部嵌入函数
        return self._embed(clean_texts)

    def _embed(self, texts: Sequence[str]) -> List[List[float]]:
        """
        实际执行 embedding API 调用，带自动分批处理。
        """
        clean_texts = [t if isinstance(t, str) else str(t) for t in texts]
        if not clean_texts:
            return []

        batch_size = 10  # OpenAI embeddings API 限制
        all_embeddings: List[List[float]] = []

        for i in range(0, len(clean_texts), batch_size):
            batch = clean_texts[i:i + batch_size]

            print(f"[Embedding] 批次 {i // batch_size + 1} / {(len(clean_texts) + batch_size - 1) // batch_size} "
                  f"（本批 {len(batch)} 条）")

            resp = self._client.embeddings.create(
                model=self._model,
                input=batch,
                encoding_format=self._encoding_format,
            )

            all_embeddings.extend([d.embedding for d in resp.data])

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Return embedding for a given text."""
        embeddings = self._embed([text])
        return embeddings[0] if embeddings else []


import time
import logging
from typing import Any, List, Optional
from openai import OpenAI
from langchain_core.documents import Document
from langchain.retrievers.document_compressors.base import BaseDocumentCompressor

logger = logging.getLogger(__name__)


class DashscopeReranker(BaseDocumentCompressor):
    """
    使用 API 调用的 Reranker 模型。
    与本地 QwenReranker 不同，它通过 DashScope 或 OpenAI 接口调用模型完成重排。

    特点：
    - 支持批量文档打分
    - 自动重试机制
    - 兼容 LangChain 文档压缩接口
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        top_n: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.5,
    ):
        super().__init__()
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.top_n = top_n
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        logger.info(f"[DashscopeReranker] 模型 {model} 初始化成功。")

    def _score_batch(
        self, query: str, documents: List[Document], attempt: int = 1
    ) -> List[float]:
        """
        调用 API 进行一批文档的打分。
        假设模型接受类似于 "query" + "document list" 的输入。
        """
        try:
            # 构造输入格式（按不同 API 可能需要调整）
            inputs = [
                {"query": query, "document": doc.page_content}
                for doc in documents
            ]
            response = self.client.rerankings.create(
                model=self.model,
                query=query,
                documents=[doc.page_content for doc in documents],
            )

            # 返回每个文档的分数
            scores = [item.relevance_score for item in response.data]
            return scores

        except Exception as e:
            if attempt <= self.max_retries:
                logger.warning(f"[Reranker] 请求失败，第 {attempt} 次重试中... 错误：{e}")
                time.sleep(self.retry_delay * attempt)
                return self._score_batch(query, documents, attempt + 1)
            else:
                logger.error(f"[Reranker] 请求失败，已超出最大重试次数：{e}")
                raise

    def compress_documents(
        self, documents: List[Document], query: str, callbacks: Optional[Any] = None
    ) -> List[Document]:
        """
        对输入文档进行重排序，保留 top_n。
        """
        if not documents:
            return []

        logger.info(f"[Reranker] 开始对 {len(documents)} 篇文档进行重排...")

        scores = self._score_batch(query, documents)

        for doc, score in zip(documents, scores):
            doc.metadata["rerank_score"] = float(score)

        sorted_docs = sorted(
            documents, key=lambda x: x.metadata["rerank_score"], reverse=True
        )

        logger.info(
            f"[Reranker] 重排完成。Top {self.top_n} 文档平均得分："
            f"{sum([d.metadata['rerank_score'] for d in sorted_docs[:self.top_n]]) / self.top_n:.4f}"
        )

        return sorted_docs[: self.top_n]
