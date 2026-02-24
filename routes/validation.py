"""
Validation Routes
=================
API สำหรับตรวจสอบความถูกต้องของข้อมูล (Validation)

APIs:
- GET /api/check-vegetable-name - ตรวจสอบชื่อผักซ้ำ
- GET /api/check-diseasepest-name - ตรวจสอบชื่อโรค/ศัตรูพืชซ้ำ
"""

from typing import Optional
from fastapi import APIRouter, HTTPException

from database import get_collection

router = APIRouter(tags=["Validation"])


@router.get("/api/check-vegetable-name")
async def check_vegetable_name(
    thai_name: str
):
    """
    ตรวจสอบว่าชื่อผัก (ภาษาไทย) มีอยู่ในระบบแล้วหรือไม่
    
    Args:
        thai_name: ชื่อผักภาษาไทยที่ต้องการตรวจสอบ
        
    Returns:
        exists: true ถ้ามีชื่อนี้อยู่แล้ว, false ถ้ายังไม่มี
    """
    collection = get_collection("vegetable")
    
    # ตรวจสอบแบบ case-insensitive
    existing = await collection.find_one({
        "thai_name": {"$regex": f"^{thai_name}$", "$options": "i"}
    })
    
    return {
        "exists": existing is not None,
        "thai_name": thai_name,
        "message": "ชื่อผักนี้มีอยู่ในระบบแล้ว" if existing else "ชื่อผักนี้สามารถใช้ได้"
    }


@router.get("/api/check-diseasepest-name")
async def check_diseasepest_name(
    thai_name: str,
    type: Optional[str] = None
):
    """
    ตรวจสอบว่าชื่อโรคหรือศัตรูพืช (ภาษาไทย) มีอยู่ในระบบแล้วหรือไม่
    
    Args:
        thai_name: ชื่อโรค/ศัตรูพืชภาษาไทยที่ต้องการตรวจสอบ
        type: '1' สำหรับโรค, '2' สำหรับศัตรูพืช (optional)
        
    Returns:
        exists: true ถ้ามีชื่อนี้อยู่แล้ว, false ถ้ายังไม่มี
    """
    collection = get_collection("diseases_pest")
    
    # สร้าง query แบบ case-insensitive
    query = {
        "thai_name": {"$regex": f"^{thai_name}$", "$options": "i"}
    }
    
    # ถ้าระบุ type ให้เพิ่มเงื่อนไข
    if type:
        query["type"] = type
    
    existing = await collection.find_one(query)
    
    type_name = "โรคพืช" if type == "1" else "ศัตรูพืช" if type == "2" else "โรค/ศัตรูพืช"
    
    return {
        "exists": existing is not None,
        "thai_name": thai_name,
        "type": type,
        "type_name": type_name,
        "message": f"ชื่อ{type_name}นี้มีอยู่ในระบบแล้ว" if existing else f"ชื่อ{type_name}นี้สามารถใช้ได้"
    }
