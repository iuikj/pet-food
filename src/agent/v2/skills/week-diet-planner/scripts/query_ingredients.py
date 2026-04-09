#!/usr/bin/env python3
"""
食材查询模块

从本地 ingredients 数据库查询食材营养数据。
支持按类别、营养素筛选，支持组合查询。
"""
from dataclasses import dataclass
from typing import Optional, List, Literal, Any
from decimal import Decimal


@dataclass
class IngredientInfo:
    """食材信息"""
    id: str
    name: str
    category: str
    sub_category: str
    has_nutrition_data: bool
    calories: Optional[float]
    protein: Optional[float]
    fat: Optional[float]
    carbohydrates: Optional[float]
    dietary_fiber: Optional[float]
    # 矿物质
    calcium: Optional[float]
    phosphorus: Optional[float]
    iron: Optional[float]
    zinc: Optional[float]
    # 维生素
    vitamin_a: Optional[float]
    vitamin_d: Optional[float]
    vitamin_e: Optional[float]
    # 其他
    taurine: Optional[float]
    epa: Optional[float]
    dha: Optional[float]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "category": self.category,
            "sub_category": self.sub_category,
            "calories": self.calories,
            "protein": self.protein,
            "fat": self.fat,
            "carbohydrates": self.carbohydrates,
            "dietary_fiber": self.dietary_fiber,
            "calcium": self.calcium,
            "phosphorus": self.phosphorus,
            "iron": self.iron,
            "zinc": self.zinc,
            "vitamin_a": self.vitamin_a,
            "vitamin_d": self.vitamin_d,
            "vitamin_e": self.vitamin_e,
            "taurine": self.taurine,
            "epa": self.epa,
            "dha": self.dha,
        }


class IngredientQuerier:
    """食材查询器（内存版本，适用于已加载的数据）"""

    def __init__(self, ingredients_data: Optional[List[dict]] = None):
        """
        初始化查询器

        Args:
            ingredients_data: 食材数据列表（从数据库或文件加载）
                            每个元素包含 Ingredient 表的字段
        """
        self.ingredients = ingredients_data or []

    def load_from_db_row(self, row: Any) -> IngredientInfo:
        """从数据库行加载食材信息"""
        return IngredientInfo(
            id=getattr(row, 'id', ''),
            name=getattr(row, 'name', ''),
            category=getattr(row, 'category', ''),
            sub_category=getattr(row, 'sub_category', ''),
            has_nutrition_data=getattr(row, 'has_nutrition_data', True),
            calories=float(row.calories) if row.calories else None,
            protein=float(row.protein) if row.protein else None,
            fat=float(row.fat) if row.fat else None,
            carbohydrates=float(row.carbohydrates) if row.carbohydrates else None,
            dietary_fiber=float(row.dietary_fiber) if row.dietary_fiber else None,
            calcium=float(row.calcium) if row.calcium else None,
            phosphorus=float(row.phosphorus) if row.phosphorus else None,
            iron=float(row.iron) if row.iron else None,
            zinc=float(row.zinc) if row.zinc else None,
            vitamin_a=float(row.vitamin_a) if row.vitamin_a else None,
            vitamin_d=float(row.vitamin_d) if row.vitamin_d else None,
            vitamin_e=float(row.vitamin_e) if row.vitamin_e else None,
            taurine=float(row.taurine) if row.taurine else None,
            epa=float(row.epa) if row.epa else None,
            dha=float(row.dha) if row.dha else None,
        )

    def by_category(self, category: str, sub_category: Optional[str] = None) -> List[IngredientInfo]:
        """
        按类别查询

        Args:
            category: 大类别（如 "白肉", "红肉", "蔬菜"）
            sub_category: 小类别（如 "鸡", "鸭", "牛"），可选

        Returns:
            食材列表
        """
        results = []
        for ing in self.ingredients:
            cat = ing.get('category') if isinstance(ing, dict) else ing.category
            sub = ing.get('sub_category') if isinstance(ing, dict) else ing.sub_category

            if cat == category:
                if sub_category is None or sub == sub_category:
                    if isinstance(ing, dict):
                        results.append(IngredientInfo(
                            id=ing.get('id', ''),
                            name=ing['name'],
                            category=ing['category'],
                            sub_category=ing.get('sub_category', ''),
                            has_nutrition_data=ing.get('has_nutrition_data', True),
                            calories=ing.get('calories'),
                            protein=ing.get('protein'),
                            fat=ing.get('fat'),
                            carbohydrates=ing.get('carbohydrates'),
                            dietary_fiber=ing.get('dietary_fiber'),
                            calcium=ing.get('calcium'),
                            phosphorus=ing.get('phosphorus'),
                            iron=ing.get('iron'),
                            zinc=ing.get('zinc'),
                            vitamin_a=ing.get('vitamin_a'),
                            vitamin_d=ing.get('vitamin_d'),
                            vitamin_e=ing.get('vitamin_e'),
                            taurine=ing.get('taurine'),
                            epa=ing.get('epa'),
                            dha=ing.get('dha'),
                        ))
                    else:
                        results.append(ing)
        return results

    def by_nutrient_min(self, nutrient: str, min_value: float) -> List[IngredientInfo]:
        """
        按营养素最小值筛选

        Args:
            nutrient: 营养素名称（如 "protein", "calcium"）
            min_value: 最小值

        Returns:
            食材列表
        """
        results = []
        for ing in self.ingredients:
            value = ing.get(nutrient) if isinstance(ing, dict) else getattr(ing, nutrient, None)
            if value is not None and value >= min_value:
                if isinstance(ing, dict):
                    results.append(IngredientInfo(
                        id=ing.get('id', ''),
                        name=ing['name'],
                        category=ing['category'],
                        sub_category=ing.get('sub_category', ''),
                        has_nutrition_data=ing.get('has_nutrition_data', True),
                        calories=ing.get('calories'),
                        protein=ing.get('protein'),
                        fat=ing.get('fat'),
                        carbohydrates=ing.get('carbohydrates'),
                        dietary_fiber=ing.get('dietary_fiber'),
                        calcium=ing.get('calcium'),
                        phosphorus=ing.get('phosphorus'),
                        iron=ing.get('iron'),
                        zinc=ing.get('zinc'),
                        vitamin_a=ing.get('vitamin_a'),
                        vitamin_d=ing.get('vitamin_d'),
                        vitamin_e=ing.get('vitamin_e'),
                        taurine=ing.get('taurine'),
                        epa=ing.get('epa'),
                        dha=ing.get('dha'),
                    ))
                else:
                    results.append(ing)
        return results

    def by_nutrient_max(self, nutrient: str, max_value: float) -> List[IngredientInfo]:
        """
        按营养素最大值筛选

        Args:
            nutrient: 营养素名称（如 "fat", "sodium"）
            max_value: 最大值

        Returns:
            食材列表
        """
        results = []
        for ing in self.ingredients:
            value = ing.get(nutrient) if isinstance(ing, dict) else getattr(ing, nutrient, None)
            if value is not None and value <= max_value:
                if isinstance(ing, dict):
                    results.append(IngredientInfo(
                        id=ing.get('id', ''),
                        name=ing['name'],
                        category=ing['category'],
                        sub_category=ing.get('sub_category', ''),
                        has_nutrition_data=ing.get('has_nutrition_data', True),
                        calories=ing.get('calories'),
                        protein=ing.get('protein'),
                        fat=ing.get('fat'),
                        carbohydrates=ing.get('carbohydrates'),
                        dietary_fiber=ing.get('dietary_fiber'),
                        calcium=ing.get('calcium'),
                        phosphorus=ing.get('phosphorus'),
                        iron=ing.get('iron'),
                        zinc=ing.get('zinc'),
                        vitamin_a=ing.get('vitamin_a'),
                        vitamin_d=ing.get('vitamin_d'),
                        vitamin_e=ing.get('vitamin_e'),
                        taurine=ing.get('taurine'),
                        epa=ing.get('epa'),
                        dha=ing.get('dha'),
                    ))
                else:
                    results.append(ing)
        return results

    def search(
        self,
        categories: Optional[List[str]] = None,
        sub_categories: Optional[List[str]] = None,
        protein_min: Optional[float] = None,
        protein_max: Optional[float] = None,
        fat_min: Optional[float] = None,
        fat_max: Optional[float] = None,
        carb_max: Optional[float] = None,
        calcium_min: Optional[float] = None,
        phosphorus_min: Optional[float] = None,
        taurine_min: Optional[float] = None,
        exclude_names: Optional[List[str]] = None
    ) -> List[IngredientInfo]:
        """
        组合搜索

        Args:
            categories: 大类别列表
            sub_categories: 小类别列表
            protein_min: 蛋白质最小值
            protein_max: 蛋白质最大值
            fat_min: 脂肪最小值
            fat_max: 脂肪最大值
            carb_max: 碳水最大值
            calcium_min: 钙最小值
            phosphorus_min: 磷最小值
            taurine_min: 牛磺酸最小值
            exclude_names: 排除的食材名称列表

        Returns:
            食材列表
        """
        results = self.ingredients.copy()

        # 按类别筛选
        if categories:
            results = [ing for ing in results
                      if (ing.get('category') if isinstance(ing, dict) else ing.category) in categories]

        # 按小类别筛选
        if sub_categories:
            results = [ing for ing in results
                      if (ing.get('sub_category') if isinstance(ing, dict) else ing.sub_category) in sub_categories]

        # 按营养素筛选
        if protein_min is not None:
            results = [ing for ing in results
                      if (ing.get('protein') if isinstance(ing, dict) else ing.protein) is not None
                      and (ing.get('protein') if isinstance(ing, dict) else ing.protein) >= protein_min]

        if protein_max is not None:
            results = [ing for ing in results
                      if (ing.get('protein') if isinstance(ing, dict) else ing.protein) is not None
                      and (ing.get('protein') if isinstance(ing, dict) else ing.protein) <= protein_max]

        if fat_min is not None:
            results = [ing for ing in results
                      if (ing.get('fat') if isinstance(ing, dict) else ing.fat) is not None
                      and (ing.get('fat') if isinstance(ing, dict) else ing.fat) >= fat_min]

        if fat_max is not None:
            results = [ing for ing in results
                      if (ing.get('fat') if isinstance(ing, dict) else ing.fat) is not None
                      and (ing.get('fat') if isinstance(ing, dict) else ing.fat) <= fat_max]

        if carb_max is not None:
            results = [ing for ing in results
                      if (ing.get('carbohydrates') if isinstance(ing, dict) else ing.carbohydrates) is not None
                      and (ing.get('carbohydrates') if isinstance(ing, dict) else ing.carbohydrates) <= carb_max]

        if calcium_min is not None:
            results = [ing for ing in results
                      if (ing.get('calcium') if isinstance(ing, dict) else ing.calcium) is not None
                      and (ing.get('calcium') if isinstance(ing, dict) else ing.calcium) >= calcium_min]

        if taurine_min is not None:
            results = [ing for ing in results
                      if (ing.get('taurine') if isinstance(ing, dict) else ing.taurine) is not None
                      and (ing.get('taurine') if isinstance(ing, dict) else ing.taurine) >= taurine_min]

        # 排除特定名称
        if exclude_names:
            results = [ing for ing in results
                      if (ing.get('name') if isinstance(ing, dict) else ing.name) not in exclude_names]

        # 转换为 IngredientInfo
        return [
            IngredientInfo(
                id=ing.get('id', ''),
                name=ing['name'],
                category=ing['category'],
                sub_category=ing.get('sub_category', ''),
                has_nutrition_data=ing.get('has_nutrition_data', True),
                calories=ing.get('calories'),
                protein=ing.get('protein'),
                fat=ing.get('fat'),
                carbohydrates=ing.get('carbohydrates'),
                dietary_fiber=ing.get('dietary_fiber'),
                calcium=ing.get('calcium'),
                phosphorus=ing.get('phosphorus'),
                iron=ing.get('iron'),
                zinc=ing.get('zinc'),
                vitamin_a=ing.get('vitamin_a'),
                vitamin_d=ing.get('vitamin_d'),
                vitamin_e=ing.get('vitamin_e'),
                taurine=ing.get('taurine'),
                epa=ing.get('epa'),
                dha=ing.get('dha'),
            ) if isinstance(ing, dict) else ing
            for ing in results
        ]

    def get_ingredient_by_name(self, name: str) -> Optional[IngredientInfo]:
        """
        按名称精确查询

        Args:
            name: 食材名称

        Returns:
            食材信息，不存在返回 None
        """
        for ing in self.ingredients:
            ing_name = ing.get('name') if isinstance(ing, dict) else ing.name
            if ing_name == name:
                if isinstance(ing, dict):
                    return IngredientInfo(
                        id=ing.get('id', ''),
                        name=ing['name'],
                        category=ing['category'],
                        sub_category=ing.get('sub_category', ''),
                        has_nutrition_data=ing.get('has_nutrition_data', True),
                        calories=ing.get('calories'),
                        protein=ing.get('protein'),
                        fat=ing.get('fat'),
                        carbohydrates=ing.get('carbohydrates'),
                        dietary_fiber=ing.get('dietary_fiber'),
                        calcium=ing.get('calcium'),
                        phosphorus=ing.get('phosphorus'),
                        iron=ing.get('iron'),
                        zinc=ing.get('zinc'),
                        vitamin_a=ing.get('vitamin_a'),
                        vitamin_d=ing.get('vitamin_d'),
                        vitamin_e=ing.get('vitamin_e'),
                        taurine=ing.get('taurine'),
                        epa=ing.get('epa'),
                        dha=ing.get('dha'),
                    )
                return ing
        return None


# 示例数据（用于测试）
SAMPLE_INGREDIENTS = [
    {
        "id": "1",
        "name": "鸡胸肉",
        "category": "白肉",
        "sub_category": "鸡",
        "has_nutrition_data": True,
        "calories": 118.0,
        "protein": 24.6,
        "fat": 1.9,
        "carbohydrates": 0.6,
        "calcium": 11.0,
        "phosphorus": 174.0,
        "iron": 1.0,
        "zinc": 0.26,
    },
    {
        "id": "2",
        "name": "鸡肝",
        "category": "内脏",
        "sub_category": "鸡",
        "has_nutrition_data": True,
        "calories": 121.0,
        "protein": 16.6,
        "fat": 4.8,
        "carbohydrates": 2.8,
        "calcium": 7.0,
        "phosphorus": 263.0,
        "iron": 12.0,
        "zinc": 2.4,
        "vitamin_a": 34713.0,
        "taurine": 110.0,
    },
    {
        "id": "3",
        "name": "牛肉(瘦)",
        "category": "红肉",
        "sub_category": "牛",
        "has_nutrition_data": True,
        "calories": 150.0,
        "protein": 26.0,
        "fat": 5.0,
        "carbohydrates": 0.0,
        "calcium": 20.0,
        "phosphorus": 200.0,
        "iron": 2.5,
        "zinc": 5.0,
    },
]


if __name__ == "__main__":
    # 测试用例
    querier = IngredientQuerier(SAMPLE_INGREDIENTS)

    print("=== 食材查询测试 ===\n")

    # 按类别查询
    print("1. 查询白肉类食材:")
    results = querier.by_category("白肉", "鸡")
    for ing in results:
        print(f"   - {ing.name}: {ing.calories} kcal, 蛋白质 {ing.protein}g")
    print()

    # 按营养素筛选
    print("2. 查询高蛋白食材 (>20g):")
    results = querier.by_nutrient_min("protein", 20.0)
    for ing in results:
        print(f"   - {ing.name}: 蛋白质 {ing.protein}g")
    print()

    # 组合搜索
    print("3. 组合搜索 (白肉, 蛋白>15g, 脂肪<5g):")
    results = querier.search(
        categories=["白肉"],
        protein_min=15.0,
        fat_max=5.0
    )
    for ing in results:
        print(f"   - {ing.name}: 蛋白质 {ing.protein}g, 脂肪 {ing.fat}g")
    print()

    # 排除特定食材
    print("4. 查询所有食材，排除鸡肉:")
    results = querier.search(exclude_names=["鸡胸肉", "鸡肝"])
    for ing in results:
        print(f"   - {ing.name}")
