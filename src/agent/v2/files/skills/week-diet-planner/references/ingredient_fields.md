# Ingredient 表字段说明

本地食材数据库 (`ingredients` 表) 的完整字段列表。

## 基础字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | String(36) | 主键 |
| name | String(100) | 食材名称（唯一） |
| category | String(50) | 大类别（如 "白肉", "红肉", "谷薯果蔬"） |
| sub_category | String(50) | 小类别（如 "鸡", "鸭", "牛"） |
| has_nutrition_data | Boolean | 是否有营养数据 |
| note | String(100) | 计量备注 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## 宏量营养素

| 字段名 | 单位 | 说明 |
|--------|------|------|
| calories | kcal | 热量 |
| carbohydrates | g | 碳水化合物 |
| protein | g | 蛋白质 |
| fat | g | 脂肪 |
| dietary_fiber | g | 膳食纤维 |

## 矿物质

| 字段名 | 单位 | 说明 |
|--------|------|------|
| calcium | mg | 钙 |
| phosphorus | mg | 磷 |
| iron | mg | 铁 |
| zinc | mg | 锌 |
| copper | mg | 铜 |
| manganese | mg | 锰 |
| magnesium | mg | 镁 |
| sodium | mg | 钠 |
| potassium | mg | 钾 |
| iodine | μg | 碘 |
| selenium | μg | 硒 |

## 维生素

| 字段名 | 单位 | 说明 |
|--------|------|------|
| vitamin_a | IU | 维生素A |
| vitamin_d | IU | 维生素D |
| vitamin_e | mg | 维生素E |
| vitamin_b1 | mg | 维生素B1 |

## 脂肪酸

| 字段名 | 单位 | 说明 |
|--------|------|------|
| epa | mg | EPA (二十碳五烯酸) |
| dha | mg | DHA (二十二碳六烯酸) |
| epa_dha | mg | EPA&DHA 总量 |

## 其他

| 字段名 | 单位 | 说明 |
|--------|------|------|
| bone_content | % | 骨骼含量 |
| water | g | 水分 |
| choline | mg | 胆碱 |
| taurine | mg | 牛磺酸 |
| cholesterol | mg | 胆固醇 |

## 常用类别

### 大类别 (category)

- `内脏` - 肝脏
- `常用` - 常见食材
- `白肉` - 鸡、鸭、兔、火鸡等
- `红肉` - 牛、羊、猪等
- `自定义` - 其他、奶制品
- `谷薯果蔬` - 水果、籽、菌菇、蔬菜、薯类、谷物、豆类
- `鱼类` - 鱼类及其他水产

### 小类别 (sub_category)

内脏类:
- `肝脏`

常用类:
- `食材`

白肉类:
- `鸡` - 鸡肉各部位
- `鸭` - 鸭肉各部位
- `兔` - 兔肉
- `火鸡` - 火鸡肉
- `鸵鸟` - 鸵鸟肉
- `鹅` - 鹅肉
- `蛋`
- `其他`

红肉类:
- `牛` - 牛肉各部位
- `羊` - 羊肉各部位
- `猪` - 猪肉各部位
- `鹿`
- `其他`

自定义类:
- `其他`
- `奶制品`

谷薯果蔬类:
- `水果`
- `籽`
- `菌菇`
- `蔬菜`
- `薯类`
- `谷物`
- `豆类`

鱼类:
- `其他`
- `马鲛`
- `鲑鱼`
- `鲭鱼`
- `鲱鱼`

## 数据来源

食材数据位于 `docs/嗷呜食材数据/` 目录，通过 `scripts/import_ingredients.py` 导入。
