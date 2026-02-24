"""
Nutrition Routes (โภชนาการ)
จัดการข้อมูลโภชนาการและความสัมพันธ์กับผัก
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from database import get_collection
from models import Nutrition, NutritionBase, NutritionVeg, NutritionVegBase
from .utils import serialize_doc

router = APIRouter(prefix="/api", tags=["Nutrition"])


# ==================== Nutrition Routes ====================

@router.get("/nutrition", response_model=List[Nutrition])
async def get_nutrition(
):
    """ดึงข้อมูลโภชนาการทั้งหมด"""
    collection = get_collection("nutrition")
    cursor = collection.find()
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.get("/nutrition/{id}", response_model=Nutrition)
async def get_nutrition_by_id(
    id: str,
):
    """ดึงข้อมูลโภชนาการตาม ID"""
    collection = get_collection("nutrition")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Nutrition not found")
    return serialize_doc(doc)


@router.post("/nutrition", response_model=Nutrition)
async def create_nutrition(
    data: NutritionBase,
):
    """เพิ่มข้อมูลโภชนาการ"""
    collection = get_collection("nutrition")
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/nutrition/{id}", response_model=Nutrition)
async def update_nutrition(
    id: str,
    data: NutritionBase,
):
    """อัปเดตข้อมูลโภชนาการ"""
    collection = get_collection("nutrition")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": data.dict(exclude_unset=True)}
    )
    updated = await collection.find_one({"_id": ObjectId(id)})
    if not updated:
        raise HTTPException(status_code=404, detail="Nutrition not found")
    return serialize_doc(updated)


@router.delete("/nutrition/{id}")
async def delete_nutrition(
    id: str,
):
    """ลบข้อมูลโภชนาการ"""
    collection = get_collection("nutrition")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Nutrition not found")
    return {"message": "Nutrition deleted successfully"}


# ==================== Nutrition Veg Routes ====================

@router.get("/nutrition-veg", response_model=List[NutritionVeg])
async def get_nutrition_veg(
    vegetable_id: Optional[int] = None,
    nutrition_id: Optional[int] = None,
):
    """ดึงข้อมูลความสัมพันธ์ผัก-โภชนาการ"""
    collection = get_collection("nutrition_veg")
    
    query = {}
    if vegetable_id:
        query["vegetable_id"] = vegetable_id
    if nutrition_id:
        query["nutrition_id"] = nutrition_id
    
    cursor = collection.find(query)
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.get("/nutrition-veg/{id}", response_model=NutritionVeg)
async def get_nutrition_veg_by_id(
    id: str,
):
    """ดึงข้อมูลความสัมพันธ์ผัก-โภชนาการตาม ID"""
    collection = get_collection("nutrition_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="NutritionVeg not found")
    return serialize_doc(doc)


@router.post("/nutrition-veg", response_model=NutritionVeg)
async def create_nutrition_veg(
    data: NutritionVegBase,
):
    """เพิ่มข้อมูลความสัมพันธ์ผัก-โภชนาการ"""
    collection = get_collection("nutrition_veg")
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/nutrition-veg/{id}", response_model=NutritionVeg)
async def update_nutrition_veg(
    id: str,
    data: NutritionVegBase,
):
    """อัปเดตข้อมูลความสัมพันธ์ผัก-โภชนาการ"""
    collection = get_collection("nutrition_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": data.dict(exclude_unset=True)}
    )
    updated = await collection.find_one({"_id": ObjectId(id)})
    if not updated:
        raise HTTPException(status_code=404, detail="NutritionVeg not found")
    return serialize_doc(updated)


@router.delete("/nutrition-veg/{id}")
async def delete_nutrition_veg(
    id: str,
):
    """ลบข้อมูลความสัมพันธ์ผัก-โภชนาการ"""
    collection = get_collection("nutrition_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="NutritionVeg not found")
    return {"message": "NutritionVeg deleted successfully"}
