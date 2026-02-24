"""
API Endpoint สำหรับตรวจสอบและสร้าง Database
เพิ่มใน routes/ เพื่อให้เรียกผ่าน API ได้
"""

from fastapi import APIRouter, HTTPException
from database import db
from typing import Dict, List

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/database/check")
async def check_database() -> Dict:
    """ตรวจสอบ database และ collections ที่มีอยู่"""
    try:
        # ตรวจสอบ databases
        databases = await db.client.list_database_names()
        
        # ตรวจสอบ collections ใน database ปัจจุบัน
        collections = await db.database.list_collection_names()
        
        # นับจำนวน documents ในแต่ละ collection
        collection_stats = {}
        for col_name in collections:
            count = await db.database[col_name].count_documents({})
            collection_stats[col_name] = count
        
        return {
            "status": "success",
            "databases": databases,
            "current_database": db.database.name,
            "collections": collections,
            "collection_stats": collection_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/create")
async def create_database_collections() -> Dict:
    """สร้าง collections ทั้งหมดใน database"""
    try:
        collections_to_create = [
            "users",
            "vegetables",
            "diseases_pests",
            "planting",
            "harvesting",
            "locations",
            "user_vegetables",
            "otp_codes"
        ]
        
        existing_collections = await db.database.list_collection_names()
        created = []
        already_exists = []
        
        for col_name in collections_to_create:
            if col_name in existing_collections:
                already_exists.append(col_name)
            else:
                # สร้าง collection โดยการ insert และ delete document
                result = await db.database[col_name].insert_one({"_temp": "init"})
                await db.database[col_name].delete_one({"_id": result.inserted_id})
                created.append(col_name)
        
        # ตรวจสอบผลลัพธ์
        final_collections = await db.database.list_collection_names()
        
        return {
            "status": "success",
            "database": db.database.name,
            "created": created,
            "already_exists": already_exists,
            "total_collections": len(final_collections),
            "all_collections": final_collections
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/stats")
async def database_stats() -> Dict:
    """แสดงสถิติของ database"""
    try:
        collections = await db.database.list_collection_names()
        
        stats = {
            "database": db.database.name,
            "total_collections": len(collections),
            "collections": {}
        }
        
        for col_name in collections:
            count = await db.database[col_name].count_documents({})
            # ดึง document ตัวอย่าง 1 ตัว
            sample = await db.database[col_name].find_one({})
            
            stats["collections"][col_name] = {
                "count": count,
                "has_data": count > 0,
                "sample_fields": list(sample.keys()) if sample else []
            }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
