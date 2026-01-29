# RAG 模块文档

[根目录](../../CLAUDE.md) > [src](../) > **rag**

---

## 变更记录 (Changelog)

### 2025-01-29
- 初始化 RAG 模块文档
- 完成核心组件分析
- 标记待深入分析的子模块

---

## 模块职责

RAG 模块提供**检索增强生成（RAG）**功能，负责：

- 📚 **知识库管理**: 加载和管理 Markdown 格式的知识文档
- 🔍 **向量检索**: 基于 Milvus 的向量数据库集成
- 🔄 **混合检索**: 密集向量 + 稀疏向量 + BM25 全文检索
- 📊 **Rerank**: 使用 DashScope Rerank 模型重排序检索结果
- 🌐 **中文支持**: 使用 jieba 分词器优化中文检索
- 🔌 **LangChain 集成**: 提供自定义 LangChain 组件

**注意**: 当前 Agent 模块**未直接使用** RAG 模块，RAG 主要作为可扩展的知识检索基础设施。

---

## 目录结构

```
src/rag/
├── __init__.py
├── knowledge.py              # 知识库管理器
├── milvus.py                 # Milvus 向量数据库管理
├── component.py              # 自定义 Embedding 组件
├── deer_flow/                # DeerFlow 自定义检索器（待深入分析）
│   ├── __init__.py
│   ├── retriever.py          # DeerFlow 检索器实现
│   └── milvus_deerflow.py    # Milvus DeerFlow 集成
└── custom/                   # LangChain 自定义组件（待深入分析）
    ├── __init__.py
    ├── langchain_component.py  # LangChain 组件封装
    └── config_lc.py            # LangChain 配置
```

---

## 入口与启动

### 主要类和函数

| 类/函数 | 文件 | 用途 |
|---------|------|------|
| **KnowledgeManager** | `knowledge.py` | 知识库管理，加载 Markdown 文档 |
| **MilvusManager** | `milvus.py` | Milvus 向量数据库管理器 |
| **DashscopeEmbeddings** | `component.py` | DashScope Embedding 封装 |

### 使用示例

```python
# 1. 加载知识库
from src.rag.knowledge import KnowledgeManager

km = KnowledgeManager()
documents = km.load_markdown_document("path/to/knowledge.md")

# 2. 创建向量存储
from src.rag.milvus import MilvusManager

mm = MilvusManager()
await mm.create_vector_store_from_documents(documents)

# 3. 检索
vector_store = await mm.get_vector_store()
results = vector_store.similarity_search(query="宠物营养需求", k=3)
```

---

## 对外接口

### KnowledgeManager（知识库管理器）

**文件**: `knowledge.py`

**方法**:

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `load_markdown_document()` | 加载 Markdown 文档 | directory: 文件路径 | list[Document] |

**实现细节**:
```python
class KnowledgeManager:
    def load_markdown_document(self, directory) -> list[Document]:
        """
        加载目录下的所有markdown文件

        使用 MarkdownHeaderTextSplitter 按标题分割：
        - #: law_name
        - ##: part_name
        - ###: chapter_name
        - ####: article_number
        """
        blob = Blob.from_path(directory)
        markdown_text = blob.as_string()

        headers_to_split_on = [
            ("#", "law_name"),
            ("##", "part_name"),
            ("###", "chapter_name"),
            ("####", "article_number"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
        return markdown_splitter.split_text(markdown_text)
```

**使用场景**:
- 加载宠物营养知识文档
- 加载食材营养数据
- 加载宠物健康建议

### MilvusManager（向量数据库管理器）

**文件**: `milvus.py`

**方法**:

| 方法 | 说明 | 参数 | 返回 |
|------|------|------|------|
| `create_vector_store_from_documents()` | 从文档创建向量存储 | documents, connect, drop | Milvus |
| `get_vector_store()` | 获取向量存储实例 | connect | Milvus |
| `drop_collection()` | 删除向量库 | 无 | None |
| `show_schema()` | 查看向量库 schema | 无 | None |

**初始化参数**:
```python
class MilvusManager:
    def __init__(self):
        # 连接配置
        self.connect = {
            "uri": os.getenv("MILVUS_URI"),
            "user": os.getenv("MILVUS_USER"),
            "password": os.getenv("MILVUS_PASSWORD"),
        }

        # Embedding 配置
        self.embedding_model = os.getenv("MILVUS_EMBEDDING_MODEL")
        self.embedding_api_key = os.getenv("MILVUS_EMBEDDING_API_KEY")
        self.embedding_base_url = os.getenv("MILVUS_EMBEDDING_BASE_URL")
        self.embedding_dim: int = self._get_embedding_dimension(self.embedding_model)
        self.embedding_provider = os.getenv("MILVUS_EMBEDDING_PROVIDER", "openai")

        # Rerank 配置
        self.rerank_model = os.getenv("MILVUS_RERANK_MODEL")
        self.rerank_api_key = os.getenv("MILVUS_RERANK_API_KEY")

        # Collection 名称
        self.collection_name = os.getenv("MILVUS_COLLECTION")
```

**混合检索配置**:
```python
analyzer_params = {
    "tokenizer": "jieba",  # 中文分词
    "filter": [
        "lowercase",
        {
            "type": "stop",
            "stop_words": ["，", "。", "；", "："]
        }
    ]
}

# 同时存储密集向量和稀疏向量
vector_field = ["dense", "sparse"]
```

**检索示例**:
```python
# 混合检索（dense + sparse + BM25）
vector_store = await mm.get_vector_store()
results = vector_store.similarity_search(
    query="查询内容",
    k=3,
    ranker_type="weighted",  # 加权 rerank
    ranker_params={"weights": [0.6, 0.4]}  # dense 0.6, sparse 0.4
)
```

---

## 关键依赖与配置

### 依赖包

**核心依赖**:
- `langchain-milvus>=0.2.1`: Milvus 向量数据库集成
- `langchain-openai`: OpenAI Embeddings
- `langchain-community`: DashScope Rerank
- `pymilvus`: Milvus Python 客户端
- `langchain-text-splitters`: 文本分割器

**可选依赖**:
- `langchain-core`: LangChain 核心
- `langchain`: LangChain 主包

### 环境变量

```bash
# Milvus 连接配置
MILVUS_URI=<your-milvus-uri>
MILVUS_USER=<your-username>
MILVUS_PASSWORD=<your-password>

# Embedding 配置
MILVUS_EMBEDDING_MODEL=text-embedding-ada-002
MILVUS_EMBEDDING_API_KEY=<your-api-key>
MILVUS_EMBEDDING_BASE_URL=<your-base-url>
MILVUS_EMBEDDING_PROVIDER=openai  # 或 dashscope
MILVUS_EMBEDDING_DIM=1536  # 可选，自动检测

# Rerank 配置
MILVUS_RERANK_MODEL=<your-rerank-model>
MILVUS_RERANK_API_KEY=<your-api-key>

# Collection 配置
MILVUS_COLLECTION=pet_food_knowledge
```

---

## 数据模型

### Document（LangChain）

```python
from langchain_core.documents import Document

Document(
    page_content="文档内容",
    metadata={
        "law_name": "法律名称",
        "part_name": "部分名称",
        "chapter_name": "章节名称",
        "article_number": "条款编号",
        # ... 其他元数据
    }
)
```

### 向量 Schema

```python
schema = MilvusSchema()
schema.add_field(field_name="pk", datatype=DataType.INT64, is_primary=True)
schema.add_field(field_name="dense", datatype=DataType.FLOAT_VECTOR)  # 密集向量
schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)  # 稀疏向量
schema.add_field()  # 动态字段（enable_dynamic_field=True）
```

---

## 核心功能详解

### 1. 混合检索（Hybrid Search）

**原理**: 结合密集向量（Dense）、稀疏向量（Sparse）和 BM25 全文检索

**配置**:
```python
analyzer_params = {
    "tokenizer": "jieba",  # 中文分词
    "filter": [
        "lowercase",  # 小写化
        {
            "type": "stop",
            "stop_words": ["，", "。", "；", "："]  # 停用词
        }
    ]
}
```

**权重配置**:
```python
ranker_params = {
    "weights": [0.6, 0.4]  # dense 60%, sparse 40%
}
```

**优势**:
- **密集向量**: 语义相似度，捕捉上下文含义
- **稀疏向量**: 关键词匹配，精确匹配重要词汇
- **BM25**: 全文检索，基于词频和文档频率

### 2. Rerank 重排序

**实现**: 使用 DashScope Rerank 模型

```python
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

compressor = DashScopeRerank(
    top_n=k,
    model=self.rerank_model,
    dashscope_api_key=self.rerank_api_key
)

compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vector_store.as_retriever(
        search_kwargs={
            "k": k,
            "ranker_type": "weighted",
            "ranker_params": {"weights": [0.6, 0.4]}
        }
    )
)
```

**优势**:
- 提高检索精度
- 优化结果排序
- 减少无关结果

### 3. 中文分词优化

**使用 jieba 分词器**:
```python
analyzer_params = {
    "tokenizer": "jieba",
    "filter": ["lowercase", {"type": "stop", "stop_words": ["，", "。", "；", "："]}]
}
```

**优势**:
- 更准确的中文分词
- 去除无意义标点
- 提高检索准确率

### 4. Embedding 模型支持

**支持的提供商**:

| 提供商 | 提供商标识 | 模型示例 | 维度 |
|--------|------------|----------|------|
| **OpenAI** | `openai` | `text-embedding-ada-002` | 1536 |
| **OpenAI** | `openai` | `text-embedding-v4` | 2048 |
| **DashScope** | `dashscope` | 自定义模型 | 可配置 |

**自动检测维度**:
```python
def _get_embedding_dimension(self, model_name: str) -> int:
    embedding_dims = {
        "text-embedding-ada-002": 1536,
        "text-embedding-v4": 2048,
    }

    # 优先使用环境变量显式配置
    explicit_dim = os.getenv("MILVUS_EMBEDDING_DIM", 0)
    if explicit_dim > 0:
        return explicit_dim

    # 返回模型默认维度
    return embedding_dims.get(model_name, 1536)
```

### 5. 动态字段支持

```python
Milvus.from_documents(
    documents=documents,
    embedding=self.embedding_model_instance,
    builtin_function=BM25BuiltInFunction(analyzer_params=analyzer_params),
    vector_field=["dense", "sparse"],
    connection_args=connect,
    collection_name=self.collection_name,
    enable_dynamic_field=True,  # 启用动态字段
)
```

**优势**:
- 灵活添加元数据
- 无需预定义 schema
- 支持任意字段

---

## 自定义组件

### DashscopeEmbeddings

**文件**: `component.py`

**说明**: DashScope Embedding 模型的 LangChain 封装

**用途**:
- 使用阿里云 DashScope API 生成向量
- 替代 OpenAI Embeddings
- 支持自定义 base_url

**配置**:
```python
DashscopeEmbeddings(
    api_key=self.embedding_api_key,
    model=self.embedding_model,
    base_url=self.embedding_base_url,
    model_kwargs={"encoding_format": "float"},
    dimensions=self.embedding_dim,
)
```

---

## 待深入分析的子模块

### deer_flow/（DeerFlow 检索器）

**文件**:
- `deer_flow/retriever.py`
- `deer_flow/milvus_deerflow.py`

**可能的功能**:
- DeerFlow 框架的自定义检索器
- 与 Milvus 的特殊集成
- 可能的工作流编排

**分析状态**: ⚠️ **未详细分析**

**建议**: 需要读取这两个文件以了解 DeerFlow 的具体实现和用途。

### custom/（LangChain 自定义组件）

**文件**:
- `custom/langchain_component.py`
- `custom/config_lc.py`

**可能的功能**:
- LangChain 组件的自定义实现
- LangChain 配置管理
- 可能的检索器、文档加载器等

**分析状态**: ⚠️ **未详细分析**

**建议**: 需要读取这两个文件以了解自定义组件的具体实现。

---

## 测试与质量

### 测试状态

当前**未发现测试文件**。

### 建议的测试结构

```
tests/
├── test_rag/                       # RAG 模块测试
│   ├── test_knowledge.py           # 知识库管理测试
│   ├── test_milvus.py              # Milvus 管理器测试
│   ├── test_component.py           # 组件测试
│   ├── test_deer_flow/             # DeerFlow 测试
│   └── test_custom/                # 自定义组件测试
└── fixtures/                       # 测试夹具
    ├── sample_documents/
    │   └── pet_nutrition.md
    └── test_embeddings.json
```

### 测试建议

1. **单元测试**
   - 测试 Markdown 文档加载
   - 测试 Embedding 生成
   - 测试向量存储创建

2. **集成测试**
   - 测试 Milvus 连接
   - 测试混合检索
   - 测试 Rerank 功能

3. **Mock 测试**
   - Mock Milvus 客户端（避免实际数据库连接）
   - Mock Embedding API（避免实际 API 调用）
   - 使用预定义的向量

---

## 常见问题 (FAQ)

### Q1: 如何添加新的知识文档？

1. 将 Markdown 文档放到知识库目录
2. 使用 `KnowledgeManager.load_markdown_document()` 加载
3. 使用 `MilvusManager.create_vector_store_from_documents()` 创建向量存储

**示例**:
```python
km = KnowledgeManager()
documents = km.load_markdown_document("knowledge/pet_nutrition.md")

mm = MilvusManager()
await mm.create_vector_store_from_documents(documents, drop=True)
```

### Q2: 如何切换 Embedding 模型？

修改环境变量：
```bash
# 使用 DashScope
MILVUS_EMBEDDING_PROVIDER=dashscope
MILVUS_EMBEDDING_MODEL=text-embedding-v2
MILVUS_EMBEDDING_API_KEY=<your-dashscope-key>
MILVUS_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 使用 OpenAI
MILVUS_EMBEDDING_PROVIDER=openai
MILVUS_EMBEDDING_MODEL=text-embedding-ada-002
MILVUS_EMBEDDING_API_KEY=<your-openai-key>
```

### Q3: 如何调整混合检索的权重？

修改 `ranker_params`:
```python
ranker_params = {
    "weights": [0.7, 0.3]  # dense 70%, sparse 30%
}
```

建议范围：
- 语义重要：`[0.7, 0.3]` 或 `[0.8, 0.2]`
- 关键词重要：`[0.5, 0.5]` 或 `[0.4, 0.6]`

### Q4: 如何优化中文检索效果？

1. **调整分词器**
```python
analyzer_params = {
    "tokenizer": "jieba",
    "filter": [
        "lowercase",
        {
            "type": "stop",
            "stop_words": ["，", "。", "；", "：", "的", "了", "是"]  # 添加更多停用词
        }
    ]
}
```

2. **使用更大的 Embedding 模型**
```bash
MILVUS_EMBEDDING_MODEL=text-embedding-v4  # 2048 维
```

3. **启用 Rerank**
```python
compressor = DashScopeRerank(
    top_n=5,  # 返回更多结果供 rerank
    model="gpt-rerank-v1"
)
```

### Q5: RAG 模块如何在 Agent 中使用？

**方案 1: 添加为子智能体工具**
```python
# src/agent/tools.py
from src.rag.milvus import MilvusManager

@tool
async def search_knowledge(query: str):
    """搜索宠物营养知识库"""
    mm = MilvusManager()
    vector_store = await mm.get_vector_store()
    results = vector_store.similarity_search(query, k=3)
    return results

# src/agent/sub_agent/node.py
model.bind_tools([...search_knowledge])
```

**方案 2: 集成到主智能体**
```python
# src/agent/tools.py
@tool
async def query_knowledge_base(query: str):
    """查询知识库获取宠物营养信息"""
    # 实现检索逻辑
    pass
```

### Q6: 如何处理 Milvus 连接失败？

添加错误处理：
```python
try:
    mm = MilvusManager()
    vector_store = await mm.get_vector_store()
except Exception as e:
    logging.error(f"Milvus 连接失败: {e}")
    # 回退方案：使用本地检索或不使用检索
    return []
```

### Q7: 如何清理向量库？

```python
mm = MilvusManager()
await mm.drop_collection()  # 删除整个 collection
```

**注意**: 此操作**不可逆**，请谨慎使用。

---

## 性能优化建议

### 1. 向量存储优化

- **批量插入**: 一次插入多个文档
```python
await mm.create_vector_store_from_documents(documents, drop=True)
```

- **索引优化**: 根据查询模式选择合适的索引类型
```python
# Milvus 自动创建索引，默认使用 IVF_FLAT 或 HNSW
```

### 2. 检索优化

- **调整 k 值**: 返回适量的结果
```python
results = vector_store.similarity_search(query, k=5)  # 不要太大
```

- **使用 Rerank**: 提高精度，减少返回结果
```python
compression_retriever = ContextualCompressionRetriever(
    base_compressor=DashScopeRerank(top_n=3),
    base_retriever=vector_store.as_retriever(search_kwargs={"k": 10})
)
```

### 3. Embedding 优化

- **缓存 Embedding 结果**: 避免重复计算
```python
from langchain.cache import InMemoryCache
from langchain.globals import set_llm_cache

set_llm_cache(InMemoryCache())
```

- **使用更快的模型**: 平衡速度和效果
```bash
MILVUS_EMBEDDING_MODEL=text-embedding-ada-002  # 较快
MILVUS_EMBEDDING_MODEL=text-embedding-v4  # 更准确但较慢
```

---

## 与其他模块的交互

### 与 Agent 模块

**当前状态**: ❌ **未集成**

**建议集成方式**:
1. 作为子智能体的工具（搜索知识库）
2. 为主智能体提供知识支持
3. 为结构化智能体提供营养数据参考

### 与 Utils 模块

**当前状态**: ❌ **无交互**

**可能集成**:
- Utils 模块提供通用工具函数
- RAG 模块提供特定检索功能

---

## 扩展建议

### 1. 增强知识库管理

- 支持多种文档格式（PDF、Word、TXT）
- 支持增量更新（不重建整个向量库）
- 支持文档版本管理

### 2. 增强检索功能

- 添加更多检索模式（MMR、多样化检索）
- 添加查询扩展（同义词、相关词）
- 添加结果聚类

### 3. 增强监控和日志

- 添加检索性能统计
- 添加检索结果质量评估
- 添加用户反馈收集

### 4. 增强多语言支持

- 添加英文分词器
- 添加多语言 Embedding 模型
- 添加跨语言检索

---

## 相关文件清单

### 核心文件

| 文件 | 行数估计 | 职责 | 分析状态 |
|------|----------|------|----------|
| `knowledge.py` | ~40 | 知识库管理器 | ✅ 已分析 |
| `milvus.py` | ~260 | Milvus 管理器 | ✅ 已分析 |
| `component.py` | ~20 | Embedding 组件 | ✅ 已分析 |

### 待深入分析

| 文件 | 预估行数 | 职责 | 分析状态 |
|------|----------|------|----------|
| `deer_flow/retriever.py` | ~100 | DeerFlow 检索器 | ⚠️ 待分析 |
| `deer_flow/milvus_deerflow.py` | ~100 | DeerFlow Milvus 集成 | ⚠️ 待分析 |
| `custom/langchain_component.py` | ~100 | LangChain 组件 | ⚠️ 待分析 |
| `custom/config_lc.py` | ~50 | LangChain 配置 | ⚠️ 待分析 |

---

## 参考资源

- [Milvus 文档](https://milvus.io/docs)
- [LangChain RAG 教程](https://python.langchain.com/docs/use_cases/question_answering/)
- [DashScope 文档](https://help.aliyun.com/zh/dashscope/)
- [jieba 分词](https://github.com/fxsjy/jieba)
- 项目根文档: [../../CLAUDE.md](../../CLAUDE.md)
- Agent 模块文档: [../agent/CLAUDE.md](../agent/CLAUDE.md)

---

## 下一步行动

基于当前分析，建议优先完成以下任务：

1. **深入分析 deer_flow/ 模块**
   - 读取 `retriever.py` 和 `milvus_deerflow.py`
   - 了解 DeerFlow 框架的用途和实现
   - 评估是否需要在 Agent 中集成

2. **深入分析 custom/ 模块**
   - 读取 `langchain_component.py` 和 `config_lc.py`
   - 了解自定义 LangChain 组件的功能
   - 评估组件的可复用性

3. **集成 RAG 到 Agent**
   - 在子智能体中添加知识库搜索工具
   - 评估检索结果对任务执行的帮助
   - 测试和优化检索效果

4. **添加测试**
   - 为 KnowledgeManager 添加单元测试
   - 为 MilvusManager 添加集成测试
   - 添加端到端检索测试

5. **性能优化**
   - 测试不同 Embedding 模型的效果
   - 调优混合检索权重
   - 优化检索速度和准确率
