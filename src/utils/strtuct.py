from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class PetType(str, Enum):
    """宠物类型"""
    CAT = "cat"
    DOG = "dog"


class PetInformation(BaseModel):
    """
    宠物信息
    """
    pet_type: PetType = Field(..., description="宠物类型")
    pet_breed: Optional[str] = Field(None, max_length=100, description="宠物品种")
    pet_age: int = Field(..., gt=0, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, le=1000, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")
    special_requirements: Optional[str] = Field(
        None,
        max_length=500,
        description="本次计划的特殊需求或定制偏好",
    )
    allergens: Optional[List[str]] = Field(
        None,
        description="过敏原列表（结构化），Agent 应在食材筛选时严格规避",
    )
    health_issues: Optional[List[str]] = Field(
        None,
        description="健康问题列表（结构化），Agent 应基于此调整营养配比",
    )
