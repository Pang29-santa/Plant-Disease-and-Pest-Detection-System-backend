"""
Location Routes (จังหวัด/อำเภอ/ตำบล)
จัดการข้อมูลพื้นที่ภูมิศาสตร์ไทย
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from database import get_collection
from models import Province, District, Subdistrict
from .utils import serialize_doc

router = APIRouter(prefix="/api", tags=["Location"])


@router.get("/provinces")
async def get_provinces():
    """ดึงข้อมูลจังหวัดทั้งหมด (Public - ไม่ต้อง Login)"""
    try:
        collection = get_collection("provinces")
        cursor = collection.find()
        docs = await cursor.to_list(length=100)
        
        # ถ้าไม่มีข้อมูล ให้คืนค่า dummy ชั่วคราว
        if not docs:
            print("[WARN] No provinces in database, returning dummy data")
            return [
                {"id": 1, "name_in_thai": "กรุงเทพมหานคร", "name_in_english": "Bangkok"},
                {"id": 2, "name_in_thai": "เชียงใหม่", "name_in_english": "Chiang Mai"},
                {"id": 3, "name_in_thai": "ชลบุรี", "name_in_english": "Chon Buri"},
            ]
        
        return [serialize_doc(doc) for doc in docs]
    except Exception as e:
        import traceback
        print(f"[ERROR] get_provinces: {e}")
        print(traceback.format_exc())
        # ถ้า error ให้คืนค่า dummy ไปก่อน
        return [
            {"id": 1, "name_in_thai": "กรุงเทพมหานคร", "name_in_english": "Bangkok"},
            {"id": 2, "name_in_thai": "เชียงใหม่", "name_in_english": "Chiang Mai"},
        ]


@router.get("/provinces/{id}", response_model=Province)
async def get_province_by_id(
    id: int,
):
    """ดึงข้อมูลจังหวัดตาม ID"""
    collection = get_collection("provinces")
    doc = await collection.find_one({"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="Province not found")
    return serialize_doc(doc)


@router.get("/districts", response_model=List[District])
async def get_districts(
    province_id: Optional[int] = None,
):
    """ดึงข้อมูลอำเภอ (Public - ไม่ต้อง Login)"""
    try:
        collection = get_collection("districts")
        query = {"province_id": province_id} if province_id else {}
        cursor = collection.find(query)
        docs = await cursor.to_list(length=1000)
        return [serialize_doc(doc) for doc in docs]
    except Exception as e:
        print(f"[ERROR] get_districts: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/districts/{id}", response_model=District)
async def get_district_by_id(
    id: int,
):
    """ดึงข้อมูลอำเภอตาม ID"""
    collection = get_collection("districts")
    doc = await collection.find_one({"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="District not found")
    return serialize_doc(doc)


@router.get("/subdistricts", response_model=List[Subdistrict])
async def get_subdistricts(
    district_id: Optional[int] = None,
    province_id: Optional[int] = None,
):
    """ดึงข้อมูลตำบล (Public - ไม่ต้อง Login)"""
    try:
        collection = get_collection("subdistricts")
        query = {}
        if district_id:
            query["district_id"] = district_id
        if province_id:
            query["province_id"] = province_id
        
        cursor = collection.find(query)
        docs = await cursor.to_list(length=1000)
        return [serialize_doc(doc) for doc in docs]
    except Exception as e:
        print(f"[ERROR] get_subdistricts: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/subdistricts/{id}", response_model=Subdistrict)
async def get_subdistrict_by_id(
    id: int,
):
    """ดึงข้อมูลตำบลตาม ID"""
    collection = get_collection("subdistricts")
    doc = await collection.find_one({"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="Subdistrict not found")
    return serialize_doc(doc)


@router.get("/location/full/{subdistrict_id}")
async def get_full_location(
    subdistrict_id: int,
):
    """ดึงข้อมูลตำบล พร้อมอำเภอและจังหวัด"""
    subdistricts_collection = get_collection("subdistricts")
    subdistrict = await subdistricts_collection.find_one({"id": subdistrict_id})
    
    if not subdistrict:
        raise HTTPException(status_code=404, detail="Subdistrict not found")
    
    district_id = subdistrict.get("district_id")
    province_id = subdistrict.get("province_id")
    
    districts_collection = get_collection("districts")
    district = await districts_collection.find_one({"id": district_id})
    
    provinces_collection = get_collection("provinces")
    province = await provinces_collection.find_one({"id": province_id})
    
    return {
        "subdistrict": serialize_doc(subdistrict),
        "district": serialize_doc(district) if district else None,
        "province": serialize_doc(province) if province else None
    }
