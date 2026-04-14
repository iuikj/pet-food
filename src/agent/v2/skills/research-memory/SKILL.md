---
name: research-memory
description: "调研记忆管理技能。plan_agent 在开始调研前，先检查 files/notes/ 目录下是否已有可复用的调研结果。找到匹配记忆文件则直接读取复用，跳过重复调研；未找到则执行正常调研流程，完成后保存到文件系统。适用场景：(1) plan_agent 开始新调研任务前检查已有知识 (2) 保存调研成果到文件系统供后续复用 (3) 判断已有调研是否过期需要更新"
---

# Research Memory

调研记忆的检查、复用和保存流程。

## 核心流程

```
收到调研任务
  ↓
Step 1: glob 搜索  files/notes/{pet_type}/{breed}/
  ├─ 找到匹配文件 → Step 2
  └─ 未找到       → Step 3
  ↓
Step 2: read_file → 检查 updated 时间戳
  ├─ 未过期 (< 30天) → 直接使用，跳过调研
  └─ 已过期           → Step 3（标记为"需更新"）
  ↓
Step 3: 正常调研流程 (web_search / rag_search)
  ↓
Step 4: write_file 保存到 files/notes/{pet_type}/{breed}/
```

## 目录规范

详见 [file_structure.md](references/file_structure.md)

```
files/notes/
├── {pet_type}/                 # dog / cat
│   ├── {breed}/                # golden_retriever / ragdoll / ...
│   │   ├── 营养需求标准.md
│   │   ├── 常见健康问题饮食.md
│   │   └── 烹饪搭配指南.md
│   └── _common/                # 该宠物类型通用知识
│       └── 基础营养标准.md
└── _shared/                    # 跨宠物类型通用
    └── 食材安全清单.md
```

## 文件头格式

每个记忆文件必须包含 YAML frontmatter：

```markdown
---
updated: 2026-04-12
pet_type: dog
breed: golden_retriever
tags: [营养需求, AAFCO标准]
ttl_days: 30
---

# 文件标题

正文内容...
```

## 匹配规则

1. 按 `{pet_type}/{breed}/` 匹配目录
2. 按任务关键词模糊匹配文件名（`glob` 搜索）
3. 找不到品种目录时，回退检查 `{pet_type}/_common/`
4. `updated` 距今超过 `ttl_days` 视为过期

## 搜索示例

```
任务: "调查金毛犬的营养需求"
  → glob "files/notes/dog/golden_retriever/*营养*"
  → 命中 "营养需求标准.md" → 读取并检查 ttl

任务: "调查猫的牛磺酸需求"
  → glob "files/notes/cat/*牛磺酸*" (品种未知)
  → 未命中 → glob "files/notes/cat/_common/*营养*"
  → 命中 → 读取
```
