# 调研笔记文件目录规范

## 路径映射

agent 中使用的路径 `/notes/` 映射到磁盘上的笔记存储区。
在 skill 和 sub agent 中，所有文件操作直接使用 `/notes/` 开头的路径。

## 完整目录树

```
/notes/                                 # 调研笔记根目录
├── dog/                                # 犬类
│   ├── golden_retriever/               # 金毛
│   │   ├── 营养需求标准.md
│   │   ├── 常见健康问题饮食.md
│   │   └── 烹饪搭配指南.md
│   ├── labrador/                       # 拉布拉多
│   │   └── ...
│   └── _common/                        # 犬类通用
│       ├── 基础营养标准.md
│       └── 犬类禁食清单.md
├── cat/                                # 猫类
│   ├── ragdoll/                        # 布偶猫
│   ├── british_shorthair/              # 英短
│   └── _common/
│       ├── 基础营养标准.md
│       └── 牛磺酸需求说明.md
└── _shared/                            # 跨物种通用
    ├── 食材安全清单.md
    └── 烹饪方法指南.md
```

## 命名规范

| 项目 | 规则 | 示例 |
|------|------|------|
| pet_type 目录 | 小写英文 | `dog`, `cat` |
| breed 目录 | 小写英文，下划线分隔 | `golden_retriever`, `british_shorthair` |
| 笔记文件名 | 中文描述性名称，.md 扩展名 | `营养需求标准.md` |
| 通用目录 | `_common` 前缀下划线 | `dog/_common/` |
| 跨物种目录 | `_shared` 前缀下划线 | `_shared/` |

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
1. /notes/{pet_type}/{breed}/   (精确品种)
2. /notes/{pet_type}/_common/   (该物种通用)
3. /notes/_shared/               (跨物种通用)
```

## 品种英文名参考

### 犬类 (dog)
| 中文名 | 英文目录名 |
|--------|-----------|
| 金毛 | golden_retriever |
| 拉布拉多 | labrador |
| 德牧 | german_shepherd |
| 柯基 | corgi |
| 泰迪/贵宾 | poodle |
| 哈士奇 | husky |
| 边牧 | border_collie |
| 柴犬 | shiba_inu |
| 法斗 | french_bulldog |
| 比熊 | bichon_frise |

### 猫类 (cat)
| 中文名 | 英文目录名 |
|--------|-----------|
| 布偶猫 | ragdoll |
| 英短 | british_shorthair |
| 美短 | american_shorthair |
| 暹罗猫 | siamese |
| 缅因猫 | maine_coon |
| 橘猫/田园猫 | domestic_shorthair |
| 波斯猫 | persian |
| 苏格兰折耳 | scottish_fold |
