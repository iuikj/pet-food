# 调研记忆文件目录规范

## 完整目录树

```
files/
├── notes/                              # 调研笔记（持久化记忆）
│   ├── dog/                            # 犬类
│   │   ├── golden_retriever/           # 金毛
│   │   │   ├── 营养需求标准.md
│   │   │   ├── 常见健康问题饮食.md
│   │   │   └── 烹饪搭配指南.md
│   │   ├── labrador/                   # 拉布拉多
│   │   │   └── ...
│   │   └── _common/                    # 犬类通用
│   │       ├── 基础营养标准.md
│   │       └── 犬类禁食清单.md
│   ├── cat/                            # 猫类
│   │   ├── ragdoll/                    # 布偶猫
│   │   ├── british_shorthair/          # 英短
│   │   └── _common/
│   │       ├── 基础营养标准.md
│   │       └── 牛磺酸需求说明.md
│   └── _shared/                        # 跨物种通用
│       ├── 食材安全清单.md
│       └── 烹饪方法指南.md
│
├── plans/                              # 历史计划存档（可选复用）
│   └── {pet_type}/{breed}/
│       └── {date}_{theme}.json
│
└── notebooks/                          # 运行时临时工作区
    └── {session_id}/
```

## 命名规范

| 项目 | 规则 | 示例 |
|------|------|------|
| pet_type 目录 | 小写英文 | `dog`, `cat` |
| breed 目录 | 小写英文，下划线分隔 | `golden_retriever`, `british_shorthair` |
| 笔记文件名 | 中文描述性名称，.md 扩展名 | `营养需求标准.md` |
| 通用目录 | `_common` 前缀下划线 | `dog/_common/` |
| 跨物种目录 | `_shared` 前缀下划线 | `notes/_shared/` |

## YAML Frontmatter 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `updated` | date | 是 | 最后更新日期 (YYYY-MM-DD) |
| `pet_type` | string | 是 | "dog" 或 "cat" |
| `breed` | string | 否 | 品种英文名 |
| `tags` | list[str] | 是 | 内容标签，用于搜索匹配 |
| `ttl_days` | int | 是 | 有效期天数，默认 30 |
| `source` | string | 否 | 数据来源 (tavily_search / rag / manual) |

## 检索优先级

```
1. files/notes/{pet_type}/{breed}/  (精确品种)
2. files/notes/{pet_type}/_common/  (该物种通用)
3. files/notes/_shared/              (跨物种通用)
```
