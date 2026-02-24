"""
Dashboard Routes
จัดการข้อมูลสถิติสำหรับ Dashboard
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query

from database import get_collection

from .utils import serialize_doc

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats():
    """ดึงข้อมูลสถิติสำหรับ Dashboard"""
    try:
        # นับจำนวนผัก
        vegetables_collection = get_collection("vegetable")
        vegetables_count = await vegetables_collection.count_documents({})
        
        # นับจำนวนโรคพืช (type=1)
        diseases_pests_collection = get_collection("diseases_pest")
        diseases_count = await diseases_pests_collection.count_documents({"type": "1"})
        
        # นับจำนวนแมลงศัตรูพืช (type=2)
        pests_count = await diseases_pests_collection.count_documents({"type": "2"})
        
        # นับจำนวนผู้ใช้งาน
        users_collection = get_collection("users")
        users_count = await users_collection.count_documents({})
        
        # นับจำนวนการตรวจจับทั้งหมด
        detections_collection = get_collection("detection")
        detections_count = await detections_collection.count_documents({})
        
        # นับจำนวน CCTV
        cctv_collection = get_collection("cctv")
        cctv_count = await cctv_collection.count_documents({})

        return {
            "success": True,
            "data": {
                "vegetables": vegetables_count,
                "diseases": diseases_count,
                "pests": pests_count,
                "users": users_count,
                "detections": detections_count,
                "cctv": cctv_count
            }
        }
    except Exception as e:
        print(f"[ERROR] get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart-data")
async def get_chart_data():
    """ดึงข้อมูลสำหรับกราฟ"""
    try:
        # TODO: Implement real aggregation from detection collection
        # For now, return empty data to avoid mock data usage
        return {
            "success": True,
            "data": []
        }
    except Exception as e:
        print(f"[ERROR] get_chart_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-activities")
async def get_recent_activities():
    """ดึงข้อมูลการดำเนินการล่าสุด"""
    try:
        # TODO: Implement activity log
        # Return empty list to avoid mock data
        return {
            "success": True,
            "data": []
        }
    except Exception as e:
        print(f"[ERROR] get_recent_activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-stats")
async def get_daily_stats(
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """ดึงสถิติการตรวจพบประจำวัน แยกตามโรคและแมลง (Top 3)"""
    try:
        from datetime import datetime, timedelta
        
        # Parse date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        collection = get_collection("detection")
        
        # Pipeline to get counts for the day
        pipeline = [
            {"$match": {
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
            }},
            {"$group": {
                "_id": "$disease_pest_id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        cursor = collection.aggregate(pipeline)
        raw_stats = await cursor.to_list(length=100)
        
        diseases_params = []
        pests_params = []
        
        diseases_collection = get_collection("diseases_pest")
        
        for item in raw_stats:
            d_id = item["_id"]
            if not d_id:
                continue
                
            # Fetch disease info
            d_info = await diseases_collection.find_one({"ID": d_id})
            if d_info:
                name = d_info.get("thai_name") or d_info.get("eng_name") or "Unknown"
                entry = {
                    "name": name,
                    "count": item["count"]
                }
                
                # Check type: "1" = Disease, "2" = Pest
                d_type = str(d_info.get("type"))
                if d_type == "1":
                    diseases_params.append(entry)
                elif d_type == "2":
                    pests_params.append(entry)
        
        # Take top 3
        top_diseases = diseases_params[:3]
        top_pests = pests_params[:3]
        
        return {
            "success": True,
            "data": {
                "date": date,
                "top_diseases": top_diseases,
                "top_pests": top_pests
            }
        }
            
    except Exception as e:
        print(f"[ERROR] get_daily_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-detections")
async def get_recent_detections():
    """ดึงข้อมูลการตรวจพบล่าสุด"""
    try:
        detections_collection = get_collection("detection")
        
        # Aggregation pipeline to join with diseases_pest and vegetable
        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$limit": 5},
            # Join with diseases_pest
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": {"path": "$disease_info", "preserveNullAndEmptyArrays": True}},
            # Join with vegetable
            {
                "$lookup": {
                    "from": "vegetable",
                    "localField": "vegetable_id",
                    "foreignField": "vegetable_id",
                    "as": "veg_info"
                }
            },
            {"$unwind": {"path": "$veg_info", "preserveNullAndEmptyArrays": True}},
            # Project fields
            {
                "$project": {
                    "_id": 1,
                    "timestamp": 1,
                    "confidence": 1,
                    "image_path": 1,
                    "disease_name_th": "$disease_info.thai_name",
                    "disease_name_en": "$disease_info.eng_name",
                    "vegetable": "$veg_info.thai_name",
                    "type": "$disease_info.type"
                }
            }
        ]
        
        cursor = detections_collection.aggregate(pipeline)
        detections = await cursor.to_list(length=5)
        
        return {
            "success": True,
            "data": [serialize_doc(d) for d in detections]
        }
    except Exception as e:
        print(f"[ERROR] get_recent_detections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
