from pathlib import Path

from langchain_core.documents.base import Blob, Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

KNOWLEDGE_BASE_DIR = PROJECT_ROOT / '' / 'knowledge_base'


class KnowledgeManager:
    """
    知识管理
    """

    # todo: 暂时只做静态知识管理，后续可添加动态知识管理，且都是md文件
    def __init__(self):
        pass

    def load_markdown_document(self, directory) -> list[Document]:
        """
        加载目录下的所有markdown文件
        """
        # 从文件路径创建 Blob
        blob = Blob.from_path(directory)

        # 读取为字符串(保留原始 Markdown 格式)
        markdown_text = blob.as_string()
        headers_to_split_on = [
            ("#", "law_name"),
            ("##", "part_name"),
            ("###", "chapter_name"),
            ("####", "article_number"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
        return markdown_splitter.split_text(markdown_text)
