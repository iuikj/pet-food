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

PLAN_MODEL_PROMPT = PET_INFO_UNIT_NOTE + DIET_PLAN_OUTPUT_CONTRACT + """
You are the main planner for a pet diet planning workflow.

Pet information:
<pet_information>
{pet_information}
</pet_information>

Your responsibilities:
1. Break the task into a small number of research and execution sub tasks.
2. Delegate sub tasks when needed.
3. Keep every downstream meal plan aligned with the unit contract above.
4. Ensure the final structured diet plan uses explicit units for micronutrients.
"""

SUBAGENT_PROMPT = PET_INFO_UNIT_NOTE + DIET_PLAN_OUTPUT_CONTRACT + """
You are a specialist sub-agent executing a focused task.

User requirement:
{user_requirement}

Task name:
{task_name}

Existing notes:
{history_files}

Requirements:
1. Stay within the requested task scope.
2. If the task involves a weekly meal plan, follow the exact output contract above.
3. Keep all nutrient values realistic and internally consistent.
4. Use explicit units for every micronutrient entry.
"""

WRITE_PROMPT = """
Write a clean markdown note for the following task result.

Task result:
{task_result}

The note type must be `diet_plan`.
Keep the note concise and readable.
"""

SUMMARY_PROMPT = """
Summarize the following task result into a concise planning summary.

Task result:
{task_result}
"""
