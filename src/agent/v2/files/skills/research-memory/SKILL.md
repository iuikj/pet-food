---
name: research-memory
description: "调研记忆管理技能。plan_agent 和 sub_agent 均可使用此 skill，但职责不同。plan_agent 负责检查现有记忆并安排调研计划；sub_agent 负责执行笔记总结或新调研，结果必须写入 /temp_notes/。根据你的角色阅读对应的指南文档。"
---

# Research Memory

调研记忆的检查、复用和保存技能。根据你当前的角色，阅读对应的指南：

## 角色导航

### 如果你是 plan_agent（研究规划师）

你的职责是**检查已有记忆、评估可用性、安排调研任务**。

-> 阅读 **[plan_agent_guide.md](references/plan_agent_guide.md)**

核心流程概要：
1. 用 `glob` / `ls` 检查 `/memory_notes/{pet_type}/{breed}/` 下是否有持久化笔记
2. 评估笔记是否覆盖当前需求、是否过期
3. 决策：安排"笔记总结" sub agent 和/或 "补充调研" sub agent

### 如果你是 sub_agent（执行者）

你的职责是**执行具体的调研或笔记总结任务**。

-> 阅读 **[sub_agent_guide.md](references/sub_agent_guide.md)**

两种工作模式：
- **模式A — 笔记总结**：读取 `/memory_notes/` 中的现有笔记，结合宠物信息评估适用性，输出总结报告
- **模式B — 新调研**：使用 websearch 等工具调研

**强制约束：无论哪种模式，任务完成后的结果都必须写入 `/temp_notes/` 目录。**

## 双路径说明

| 路径 | 性质 | 用途 | 写入规则 |
|------|------|------|----------|
| `/memory_notes/` | 持久化存储 | 已有的长期调研笔记 | **仅更新已有文件**，无对应文件则不写 |
| `/temp_notes/` | 临时内存态 | 本次任务的调研结果 | **所有 sub agent 结果必须写入** |

## 笔记目录结构

```
/memory_notes/                      # 持久化长期记忆
├── {pet_type}/{breed}/             # 品种专属
├── {pet_type}/_common/             # 物种通用
└── _shared/                         # 跨物种通用

/temp_notes/                        # 本次任务临时笔记
├── 笔记总结_金毛营养需求.md        # sub agent 写入的总结
├── 补充调研_软便饮食方案.md        # sub agent 写入的新调研
└── ...
```
