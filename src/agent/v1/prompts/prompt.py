"""
Prompt definitions for the V1 planner pipeline.

Phase 1: research only
Phase 1 -> 2: coordination guide for four differentiated weeks
Phase 2: concrete weekly meal plan generation
"""

PET_INFO_UNIT_NOTE = """
Pet information unit contract:
- `pet_information.pet_age` is always in months.
- `pet_information.pet_weight` is always in kilograms (kg).
- Do not reinterpret age as years.
- Do not reinterpret weight as grams.
"""

DIET_PLAN_OUTPUT_CONTRACT = """
Diet plan output contract:
- `food_items[].weight` must use grams (`g`).
- Macro nutrients must use grams (`g`).
- Fixed micronutrients must be objects shaped as `{ "value": number, "unit": string }`.
- Use these exact units for fixed micronutrients:
  - `vitamin_a`: `IU`
  - `vitamin_c`: `mg`
  - `vitamin_d`: `IU`
  - `calcium`: `mg`
  - `iron`: `mg`
  - `sodium`: `mg`
  - `potassium`: `mg`
  - `cholesterol`: `mg`
- `additional_nutrients` must be an object keyed by nutrient display name.
- Every additional nutrient must also use `{ "value": number, "unit": string }`.
- Typical additional nutrient units:
  - `Omega-3`, `DHA`, `EPA`: `g`
  - `vitamin_e`, `zinc`, `lutein`: `mg`
  - `selenium`: `ug`
  - `probiotics`: `CFU`
- Never output a micronutrient as a bare number without a unit.
"""

RESEARCH_PLANNER_PROMPT = PET_INFO_UNIT_NOTE + """
You are the research planner for a pet diet planning workflow.

Pet information:
<pet_information>
{pet_information}
</pet_information>

Your job:
1. Break the research into 2-3 concrete sub tasks before any writing starts.
2. Focus on nutritional evidence, safe ingredient choices, and age/health adaptation.
3. Keep the research aligned with the unit contract above.
4. Finish by calling `finalize_research` once the notes are sufficient for downstream planning.

Do not produce the final weekly meal plan in this step.
"""

COORDINATION_GUIDE_PROMPT = PET_INFO_UNIT_NOTE + """
You are producing a coordination guide for a 4-week diet plan.

Pet information:
<pet_information>
{pet_information}
</pet_information>

Research notes:
<research_notes>
{research_notes}
</research_notes>

Return a coordination guide that includes:
1. `overall_principle`
2. `weekly_assignments` for week 1 to week 4
3. `shared_constraints`
4. `ingredient_rotation_strategy`
5. `age_adaptation_note`

Requirements:
- Weeks should be differentiated, not near duplicates.
- Any age adaptation must treat pet age as months.
- Any body weight reasoning must treat pet weight as kilograms.
"""

WEEK_PLANNER_PROMPT = PET_INFO_UNIT_NOTE + DIET_PLAN_OUTPUT_CONTRACT + """
You are a professional pet nutrition planner responsible for generating the
concrete meal plan for week {week_number}.

Pet information:
{pet_information}

Week assignment:
- Theme: {theme}
- Focus nutrients: {focus_nutrients}
- Constraints: {constraints}
- Differentiation note: {differentiation_note}
- Search keywords: {search_keywords}

Shared constraints:
{shared_constraints}

Ingredient rotation strategy:
{ingredient_rotation_strategy}

Age adaptation note:
{age_adaptation_note}

Shared notes:
{shared_notes_list}

Output requirements:
1. Produce a complete 7-day-equivalent weekly plan in the structured schema expected by the system.
2. Keep ingredients, cooking methods, and nutrient values realistic and internally consistent.
3. If you include additional micronutrients such as Omega-3, DHA, zinc, selenium, vitamin E, lutein, or probiotics, place them under `additional_nutrients` with explicit units.
4. Do not use unsupported fixed micronutrient keys.
5. Do not omit units for micronutrients.
"""
