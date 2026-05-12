"""
view_type 到前端 Widget 的契约。

后端 emit_progress 的 detail.view_type 字段告诉前端用哪个 Widget 渲染。
新增 view_type 时同步更新前端 widgetRegistry.js。

设计原则：后端不猜前端 UI；前端不猜后端语义。所有渲染意图由后端在 detail.view_type
中显式给出，前端只做表查找。
"""
from enum import Enum


class ViewType(str, Enum):
    """前端 Widget 的路由键。值即字符串常量，可直接序列化到 JSON。"""

    # ── 通用对话流元素 ──
    AI_MESSAGE = "ai_message"            # AI 文本输出（含可选 reasoning，下沉折叠）
    REASONING = "reasoning"              # 单独的思考流（与 ai_message 分离时用）

    # ── 工具调用 Widget（按工具名定制） ──
    TOOL_CALL_GENERIC = "tool_call_generic"  # 通用兜底：args + result 折叠展示
    TOOL_SEARCH = "tool_search"              # tavily_search 专属（关键词 + 来源链接）
    TOOL_NOTE_READ = "tool_note_read"        # query_note / ls
    TOOL_NOTE_WRITE = "tool_note_write"      # write_note / update_note / week_write_note
    TOOL_FOOD_CALC = "tool_food_calc"        # 食材营养计算（未来扩展占位）

    # ── DeepAgent 结构化 Widget ──
    PLAN_BOARD = "plan_board"                # todo 列表（write_plan / finish_sub_plan 触发）
    SUBAGENT_DISPATCH = "subagent_dispatch"  # transfor_task_to_subagent
    WEEK_DISPATCH = "week_dispatch"          # dispatch_weeks 一对四扇出

    # ── 阶段元事件 ──
    PHASE_MARKER = "phase_marker"            # 阶段开始 / 完成的分隔标记
    PROGRESS_TICK = "progress_tick"          # 仅推进进度，不入流（前端可忽略渲染）
