# Utils 模块文档

[根目录](../../CLAUDE.md) > [src](../) > **utils**

---

## 变更记录 (Changelog)

### 2025-01-29
- 初始化 Utils 模块文档
- 完成现有文件分析

---

## 模块职责

Utils 模块提供项目的**通用工具函数和数据结构**，负责：

- 🛠️ **通用工具**: 提供可复用的工具函数
- 📦 **数据结构**: 定义通用的数据模型

**注意**: 当前 Utils 模块**仅包含一个文件**，功能有限。大部分通用工具实际位于 `src/agent/utils/` 中。

---

## 目录结构

```
src/utils/
├── __init__.py
└── strtuct.py              # 通用数据结构（注意拼写：strtuct）
```

**注意**: 文件名存在拼写错误，正确拼写应为 `struct.py`，但当前为 `strtuct.py`。

---

## 入口与启动

### 当前文件

| 文件 | 说明 | 状态 |
|------|------|------|
| `strtuct.py` | 通用数据结构定义 | ⚠️ 内容待确认 |

**建议**:
- 读取 `strtuct.py` 文件以了解具体内容
- 考虑重命名文件为 `struct.py`（如果拼写确实有误）
- 评估是否需要添加更多通用工具

---

## 与其他模块的交互

### 与 Agent 模块

**当前状态**: ❌ **无直接交互**

Agent 模块内部有自己的 `utils/` 目录：
- `src/agent/utils/struct.py`: Agent 专用的数据结构
- `src/agent/utils/context.py`: 运行时上下文

**建议**:
- 明确区分通用工具（`src/utils/`）和模块专用工具（`src/agent/utils/`）
- 避免功能重复
- 考虑将通用数据结构移到 `src/utils/`

### 与 RAG 模块

**当前状态**: ❌ **无交互**

RAG 模块相对独立，不依赖 Utils 模块。

---

## 扩展建议

### 1. 添加通用工具函数

建议添加以下工具：

**日志工具** (`logger.py`):
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_file: str, level=logging.INFO):
    """设置日志记录器"""
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger
```

**配置工具** (`config.py`):
```python
from pathlib import Path
from typing import Any
import yaml
import json

def load_config(config_path: Path) -> dict[str, Any]:
    """加载配置文件"""
    if config_path.suffix in ['.yml', '.yaml']:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    elif config_path.suffix == '.json':
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported config format: {config_path.suffix}")
```

**时间工具** (`datetime_utils.py`):
```python
from datetime import datetime, timezone
from typing import Optional

def now_iso() -> str:
    """获取当前时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat()

def parse_iso(date_string: str) -> Optional[datetime]:
    """解析 ISO 格式时间字符串"""
    try:
        return datetime.fromisoformat(date_string)
    except:
        return None
```

### 2. 添加通用数据结构

建议添加以下数据结构：

**响应结果** (`response.py`):
```python
from pydantic import BaseModel, Generic, TypeVar
from typing import Optional, TypeVar

T = TypeVar('T')

class Response(BaseModel, Generic[T]):
    """通用响应结果"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None
```

**分页结果** (`pagination.py`):
```python
from pydantic import BaseModel, Generic, TypeVar
from typing import List, Optional

T = TypeVar('T')

class PagedResponse(BaseModel, Generic[T]):
    """分页响应结果"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
```

### 3. 添加验证和装饰器

**验证工具** (`validators.py`):
```python
from typing import Any, Callable
from functools import wraps

def validate_required_fields(data: dict[str, Any], required_fields: list[str]) -> bool:
    """验证必需字段"""
    for field in required_fields:
        if field not in data or data[field] is None:
            return False
    return True

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """失败重试装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
```

---

## 建议的目录结构

```
src/utils/
├── __init__.py
├── strtuct.py              # 通用数据结构（或重命名为 struct.py）
├── logger.py               # 日志工具（建议添加）
├── config.py               # 配置工具（建议添加）
├── datetime_utils.py       # 时间工具（建议添加）
├── validators.py           # 验证工具（建议添加）
├── response.py             # 响应结果（建议添加）
└── pagination.py           # 分页结果（建议添加）
```

---

## 测试建议

### 建议的测试结构

```
tests/
├── test_utils/             # Utils 模块测试
│   ├── test_struct.py      # 数据结构测试
│   ├── test_logger.py      # 日志工具测试
│   ├── test_config.py      # 配置工具测试
│   └── test_validators.py  # 验证工具测试
```

---

## 相关文件清单

### 现有文件

| 文件 | 行数估计 | 职责 | 分析状态 |
|------|----------|------|----------|
| `strtuct.py` | 未知 | 通用数据结构 | ⚠️ 内容待确认 |

### 建议添加的文件

| 文件 | 预估行数 | 职责 | 优先级 |
|------|----------|------|--------|
| `logger.py` | ~50 | 日志工具 | 高 |
| `config.py` | ~40 | 配置工具 | 高 |
| `validators.py` | ~60 | 验证工具 | 中 |
| `datetime_utils.py` | ~30 | 时间工具 | 低 |

---

## 常见问题 (FAQ)

### Q1: 为什么 Utils 模块内容这么少？

可能原因：
1. 项目处于早期开发阶段
2. 通用工具分散在其他模块中（如 `src/agent/utils/`）
3. 尚未充分提取和复用代码

**建议**: 随着项目发展，逐步将通用功能提取到 `src/utils/`。

### Q2: `strtuct.py` 的内容是什么？

**当前状态**: ⚠️ **未读取**

**建议**: 读取该文件以了解：
- 定义了哪些数据结构
- 是否与 `src/agent/utils/struct.py` 有重复
- 是否需要重构或重命名

### Q3: 如何区分通用工具和模块专用工具？

**建议原则**:
- **通用工具** (`src/utils/`): 跨模块使用，不依赖特定业务逻辑
  - 日志、配置、时间、验证等

- **模块专用工具** (`src/{module}/utils/`): 仅在该模块内使用，依赖特定业务逻辑
  - `src/agent/utils/`: Agent 相关的数据结构、上下文
  - `src/rag/utils/`: RAG 相关的工具函数（如有）

### Q4: 是否应该重命名 `strtuct.py`？

**建议**:
1. 如果确认文件内容与结构相关，重命名为 `struct.py`
2. 更新所有引用该文件的导入语句
3. 提交 Git commit 记录重命名

**命令**:
```bash
git mv src/utils/strtuct.py src/utils/struct.py
# 更新导入语句
# git commit -m "refactor: rename strtuct.py to struct.py"
```

---

## 参考资源

- [Python Utils 库最佳实践](https://docs.python-guide.org/writing/structure/)
- 项目根文档: [../../CLAUDE.md](../../CLAUDE.md)
- Agent 模块文档: [../agent/CLAUDE.md](../agent/CLAUDE.md)
- RAG 模块文档: [../rag/CLAUDE.md](../rag/CLAUDE.md)

---

## 下一步行动

基于当前分析，建议优先完成以下任务：

1. **读取 `strtuct.py` 文件**
   - 了解文件内容和用途
   - 评估是否需要重构
   - 考虑重命名为 `struct.py`

2. **添加通用工具**
   - 实现日志工具（`logger.py`）
   - 实现配置工具（`config.py`）
   - 实现验证工具（`validators.py`）

3. **整理工具函数分布**
   - 审查 `src/agent/utils/` 中的工具
   - 将通用功能提取到 `src/utils/`
   - 保持模块专用工具在各自模块内

4. **添加测试**
   - 为 `strtuct.py` 添加单元测试
   - 为新增工具添加测试
   - 确保工具的可靠性

5. **文档完善**
   - 为每个工具函数添加 docstring
   - 提供使用示例
   - 说明工具的设计意图
