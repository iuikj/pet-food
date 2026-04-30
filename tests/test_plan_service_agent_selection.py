from types import SimpleNamespace

import pytest

from src.agent.common.stream_events import ProgressEventType
from src.api.config import settings
from src.api.services.plan_service import PlanService


@pytest.mark.asyncio
async def test_plan_service_build_graph_uses_v1_when_configured(monkeypatch):
    import src.agent.v1.graph as v1_graph_module

    sentinel_graph = object()

    async def fake_build_v1_graph():
        return sentinel_graph

    monkeypatch.setattr(settings, "diet_plan_agent_version", "v1")
    monkeypatch.setattr(v1_graph_module, "build_v1_graph", fake_build_v1_graph)

    service = PlanService(None)
    graph = await service._build_graph()

    assert graph is sentinel_graph


@pytest.mark.asyncio
async def test_plan_service_build_graph_prefers_precompiled_v2_graph(monkeypatch):
    sentinel_graph = object()

    monkeypatch.setattr(settings, "diet_plan_agent_version", "v2")

    service = PlanService(
        None,
        app_state=SimpleNamespace(v2_graph=sentinel_graph),
    )
    graph = await service._build_graph()

    assert graph is sentinel_graph


def test_plan_service_prepare_inputs_builds_v2_context(monkeypatch):
    monkeypatch.setattr(settings, "diet_plan_agent_version", "v2")

    service = PlanService(None)
    inputs, context = service._prepare_inputs(
        {
            "pet_type": "cat",
            "pet_breed": "英短",
            "pet_age": 18,
            "pet_weight": 4.2,
            "health_status": "软便恢复期",
            "special_requirements": "低敏",
        },
        user_id="user-123",
    )

    assert inputs["pet_information"].pet_type == "cat"
    assert context.user_id == "user-123"
    assert context.pet_information.pet_breed == "英短"


@pytest.mark.asyncio
async def test_v2_gather_and_structure_emits_completed_payload(monkeypatch):
    import src.agent.v2.node as v2_node

    events = []

    class FakeWeeklyPlan:
        def __init__(self, week_number: int):
            self.week_number = week_number

        def model_dump(self):
            return {
                "oder": self.week_number,
                "diet_adjustment_principle": f"week-{self.week_number}",
                "weekly_diet_plan": {"daily_diet_plans": []},
            }

    async def fake_fetch_ingredients_by_names(_names):
        return {"鸡胸肉": {"name": "鸡胸肉"}}

    async def fake_generate_ai_suggestions(_weekly_plans, _model_name):
        return "保持饮水，逐步过渡。"

    monkeypatch.setattr(
        v2_node,
        "get_runtime",
        lambda: SimpleNamespace(
            context=SimpleNamespace(
                pet_information={"pet_type": "cat"},
                summary_model="dummy-model",
            )
        ),
    )
    monkeypatch.setattr(v2_node, "collect_ingredient_names", lambda _plans: ["鸡胸肉"])
    monkeypatch.setattr(v2_node, "fetch_ingredients_by_names", fake_fetch_ingredients_by_names)
    monkeypatch.setattr(
        v2_node,
        "assemble_weekly_plan",
        lambda light, rows_by_name: FakeWeeklyPlan(light.week_number),
    )
    monkeypatch.setattr(v2_node, "_generate_ai_suggestions", fake_generate_ai_suggestions)
    monkeypatch.setattr(v2_node, "MonthlyDietPlan", lambda **kwargs: kwargs)
    monkeypatch.setattr(v2_node, "PetDietPlan", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        v2_node,
        "emit_progress",
        lambda event_type, message, **kwargs: events.append(
            {"type": event_type, "message": message, **kwargs}
        ),
    )

    result = await v2_node.gather_and_structure(
        {
            "week_light_plans": [
                SimpleNamespace(week_number=2),
                SimpleNamespace(week_number=1),
            ]
        }
    )

    completed_event = next(event for event in events if event["type"] == ProgressEventType.COMPLETED)
    assert completed_event["detail"]["ai_suggestions"] == "保持饮水，逐步过渡。"
    assert [plan["oder"] for plan in completed_event["detail"]["plans"]] == [1, 2]
    assert result["report"]["ai_suggestions"] == "保持饮水，逐步过渡。"

