---
name: research-memory
description: "调研记忆管理技能。plan_agent 和 sub_agent 均可使用此 skill，但职责不同。plan_agent 负责检查现有记忆并安排调研计划；sub_agent 负责执行具体的笔记总结或新调研任务。根据你的角色阅读对应的指南文档。"
---

# Research Memory

调研记忆的检查、复用和保存技能。根据你当前的角色，阅读对应的指南：

## 角色导航

### 如果你是 plan_agent（研究规划师）

你的职责是**检查已有记忆、评估可用性、安排调研任务**。

-> 阅读 **[plan_agent_guide.md](references/plan_agent_guide.md)**

核心流程概要：
1. 用 `glob` / `ls` 检查 `/notes/{pet_type}/{breed}/` 下是否有可用笔记
2. 评估笔记是否覆盖当前需求、是否过期
3. 决策：安排"笔记总结" sub agent 和/或 "补充调研" sub agent

### 如果你是 sub_agent（执行者）

你的职责是**执行具体的调研或笔记总结任务**。

-> 阅读 **[sub_agent_guide.md](references/sub_agent_guide.md)**

两种工作模式：
- **模式A — 笔记总结**：读取现有笔记，结合宠物信息评估适用性，输出总结报告
- **模式B — 新调研+写入**：使用 websearch 等工具调研，完成后**必须**将结果写入 `/notes/` 目录

## 笔记路径

所有笔记存储在 `/notes/` 下，按 `{pet_type}/{breed}/` 组织。
详见 **[file_structure.md](references/file_structure.md)**

```
/notes/
├── dog/golden_retriever/营养需求标准.md
├── dog/_common/基础营养标准.md
├── cat/_common/牛磺酸需求说明.md
└── _shared/食材安全清单.md
```
