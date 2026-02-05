from typing import Dict

from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, field_validator
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
    pet_breed: Optional[str] = Field(None, max_length=50, description="宠物品种")
    pet_age: int = Field(..., gt=0, le=300, description="宠物年龄（月）")
    pet_weight: float = Field(..., gt=0, le=1000, description="宠物体重（千克）")
    health_status: Optional[str] = Field(None, max_length=500, description="健康状况描述")