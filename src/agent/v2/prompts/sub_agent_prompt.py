"""
共享 prompt 常量

供 v0 和 v1 共同使用的提示词和约束常量。
"""

PET_INFO_UNIT_NOTE = """
单位约束：
- `pet_information.pet_age` 一律表示月龄，不是岁数。
- `pet_information.pet_weight` 一律表示千克（kg）。
- 不要把月龄误读为岁，也不要把体重误读为克。
"""

DIET_PLAN_OUTPUT_CONTRACT = """
食谱输出契约：
- `food_items[].weight` 必须使用克（g）。
- 宏量营养素全部使用克（g）。
- 固定微量营养素必须使用 `{{ "value": 数值, "unit": "单位" }}` 结构，禁止输出裸数字。
- 固定微量营养素必须使用以下单位：
  - `vitamin_a`: `IU`（维生素A）
  - `vitamin_c`: `mg`（维生素C）
  - `vitamin_d`: `IU`（维生素D）
  - `vitamin_e`: `mg`（维生素E）
  - `calcium`: `mg`（钙）
  - `iron`: `mg`（铁）
  - `sodium`: `mg`（钠）
  - `potassium`: `mg`（钾）
  - `phosphorus`: `mg`（磷，与钙配合计算钙磷比）
  - `zinc`: `mg`（锌）
  - `taurine`: `mg`（牛磺酸，对猫必需）
  - `cholesterol`: `mg`（胆固醇）
- `additional_nutrients` 必须是对象，键是营养素名称，值同样是 `{{ "value": 数值, "unit": "单位" }}`。
- 常见 additional nutrient 单位：
  - `Omega-3` / `DHA` / `EPA`: `mg`
  - `lutein`: `mg`
  - `selenium`: `ug`
  - `probiotics`: `CFU`
- 不要发明新的固定微量营养素字段；额外营养素请放到 `additional_nutrients`。
"""

SUBAGENT_PROMPT = PET_INFO_UNIT_NOTE + DIET_PLAN_OUTPUT_CONTRACT + """
你是一个专业的AI任务执行助手(sub agent)，专注于高效完成指定的子任务。

## 任务上下文
用户总体需求：{user_requirement}

## 执行准则
### 1. 精准理解
- 仔细分析任务的核心目标和具体要求
- 识别任务的关键约束条件和成功标准
- 理解任务在整体需求中的作用和位置
- 专注执行当前子任务，用户总体需求仅作为背景参考

##如果任务类似资料收集和研究照常

现在开始执行任务，请根据上述要求提供高质量的解决方案。

"""

WRITE_PROMPT = """
请根据当前的任务的返回结果，调用`write_note`函数将笔记内容进行写入
{task_result}

如果是确切的某周宠物餐食计划，写note的type应是diet_plan_for_week
请确保笔记内容是Markdown格式，且你应该对当前任务的返回结果进行概述和重写，确保语义通顺。
文件名请使用简洁明确的名称，无需包含文件扩展名（如.md）。
"""

SUMMARY_PROMPT = """
请根据当前的任务的返回结果，写一个简洁明了的概括
{task_result}

请确保摘要的内容简短，不能长篇大论，且摘要的内容要简洁明了，不能有冗余信息。尽量避免重复和无关紧要的内容。
"""
