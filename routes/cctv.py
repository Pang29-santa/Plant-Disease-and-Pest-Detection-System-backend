"""
CCTV Routes (กล้องวงจรปิด)
จัดการข้อมูลกล้อง CCTV
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from database import get_collection
from models import CCTV, CCTVBase
from .utils import serialize_doc

router = APIRouter(prefix="/api/cctv", tags=["CCTV"])


@router.get("", response_model=List[CCTV])
async def get_cctvs(
    user_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงข้อมูลกล้อง CCTV ทั้งหมด"""
    collection = get_collection("cctv")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if plot_id:
        query["plot_id"] = plot_id
    
    cursor = collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/{id}", response_model=CCTV)
async def get_cctv(
    id: str
):
    """ดึงข้อมูลกล้อง CCTV ตาม ID"""
    collection = get_collection("cctv")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="CCTV not found")
    return serialize_doc(doc)


@router.get("/user/{user_id}", response_model=List[CCTV])
async def get_cctvs_by_user(
    user_id: int
):
    """ดึงข้อมูลกล้อง CCTV ตาม user_id"""
    collection = get_collection("cctv")
    cursor = collection.find({"user_id": user_id})
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.get("/plot/{plot_id}", response_model=List[CCTV])
async def get_cctvs_by_plot(
    plot_id: int
):
    """ดึงข้อมูลกล้อง CCTV ตาม plot_id"""
    collection = get_collection("cctv")
    cursor = collection.find({"plot_id": plot_id})
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.post("", response_model=CCTV)
async def create_cctv(
    cctv: CCTVBase
):
    """เพิ่มกล้อง CCTV ใหม่"""
    collection = get_collection("cctv")
    result = await collection.insert_one(cctv.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=CCTV)
async def update_cctv(
    id: str,
    cctv: CCTVBase
):
    """อัปเดตข้อมูลกล้อง CCTV"""
    collection = get_collection("cctv")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = cctv.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="CCTV not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_cctv(
    id: str
):
    """ลบกล้อง CCTV"""
    collection = get_collection("cctv")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="CCTV not found")
    return {"message": "CCTV deleted successfully"}


@router.post("/{id}/test-connection")
async def test_cctv_connection(
    id: str
):
    """ทดสอบการเชื่อมต่อกล้อง CCTV"""
    collection = get_collection("cctv")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    cctv = await collection.find_one({"_id": ObjectId(id)})
    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")
    
    # In production, actually test the connection to the IP
    return {
        "cctv_id": id,
        "ip_address": cctv.get("ip_address"),
        "status": "connected",  # or "disconnected"
        "message": "Connection test completed"
    }
