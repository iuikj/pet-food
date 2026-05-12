# pet-food 文档归档区

本目录收纳 `pet_food_backend/pet-food/` 仓库内过去产生的过程性文档与重复版本文档。

## 文件清单

| 文件 | 原位置 | 归档原因 |
|------|--------|---------|
| `AGUI_INTEGRATION.md` | `pet_food_backend/pet-food/AGUI_INTEGRATION.md` | 2026-04-30 至 2026-05-02 AG-UI 接入实战记录（含 Pit 1-17） |
| `AGUI_GENUI_REFACTOR_PLAN.md` | `pet_food_backend/pet-food/AGUI_GENUI_REFACTOR_PLAN.md` | AG-UI GenUI 重构计划阶段性方案，已落地 |

## 权威规则去向

当前 AG-UI 适配权威文档：

- `.trellis/spec/pet-food/backend/agui-pitfalls.md` — `ag_ui_langgraph` + LangGraph 1.x 接入的稳定规则与已知坑点
- `.trellis/spec/pet-food/backend/agui-langgraph.md` — Agent → AG-UI 协议事件映射与流式实践

`agui-langgraph-learn/` 目录保留为接入实战学习档案（演进式记录），CLAUDE.md 已索引。

## 为什么不删除

这两份文档对应了 2026-04-30 至 2026-05-02 期间的实际接入过程：
1. `AGUI_INTEGRATION.md` 详细记录了从 230 行 wrapper 缩减到 ~110 行的每一步决策与坑点定位过程，是 spec 中"稳定结论"的来源；
2. `AGUI_GENUI_REFACTOR_PLAN.md` 是一份与最终落地有差异的中间方案，保留以便回溯"为何最终未采用 X 方案"。
