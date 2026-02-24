"""
Admin Stats Routes
==================
API สำหรับสถิติต่างๆ สำหรับหน้า Admin

APIs:
- GET /api/admin/top-daily-detections - สถิติ 3 อันดับแรกประจำวัน
- GET /api/admin/detection-stats - สถิติการตรวจพบสำหรับ admin
- GET /api/admin/available-months - เดือนที่มีข้อมูลสำหรับปีที่เลือก
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException

from database import get_collection

router = APIRouter(tags=["Admin Stats"])


THAI_MONTHS = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
}


@router.get("/api/admin/top-daily-detections")
async def get_top_daily_detections(
    date: Optional[str] = None
):
    """
    API สำหรับดึงข้อมูล 3 อันดับแรกที่ตรวจพบมากที่สุดประจำวัน แยกตามโรคและแมลง
    
    Args:
        date: วันที่ในรูปแบบ YYYY-MM-DD (default: วันนี้)
        
    Returns:
        top_diseases: 3 อันดับโรคพืชที่พบมากที่สุด
        top_pests: 3 อันดับศัตรูพืชที่พบมากที่สุด
    """
    try:
        # หากไม่ระบุวันที่ ให้ใช้วันปัจจุบัน
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        detection_collection = get_collection("detection")
        
        # Pipeline สำหรับโรคพืช (type = '1')
        pipeline_diseases = [
            {
                "$match": {
                    "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
                }
            },
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": "$disease_info"},
            {"$match": {"disease_info.type": "1"}},
            {
                "$group": {
                    "_id": "$disease_pest_id",
                    "count": {"$sum": 1},
                    "thai_name": {"$first": "$disease_info.thai_name"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        # Pipeline สำหรับศัตรูพืช (type = '2')
        pipeline_pests = [
            {
                "$match": {
                    "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
                }
            },
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": "$disease_info"},
            {"$match": {"disease_info.type": "2"}},
            {
                "$group": {
                    "_id": "$disease_pest_id",
                    "count": {"$sum": 1},
                    "thai_name": {"$first": "$disease_info.thai_name"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor_diseases = detection_collection.aggregate(pipeline_diseases)
        cursor_pests = detection_collection.aggregate(pipeline_pests)
        
        top_diseases = await cursor_diseases.to_list(length=3)
        top_pests = await cursor_pests.to_list(length=3)
        
        return {
            "date": date,
            "top_diseases": [
                {"id": d["_id"], "name": d["thai_name"], "count": d["count"]}
                for d in top_diseases
            ],
            "top_pests": [
                {"id": p["_id"], "name": p["thai_name"], "count": p["count"]}
                for p in top_pests
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")


@router.get("/api/admin/detection-stats")
async def get_admin_detection_stats(
    year: int,
    month: Optional[int] = None,
    disease_type: Optional[str] = None
):
    """
    API สำหรับดึงข้อมูลสถิติทั้งหมดสำหรับหน้า Admin
    
    Args:
        year: ปีที่ต้องการดู (รองรับทั้ง พ.ศ. และ ค.ศ.)
        month: เดือนที่ต้องการ (1-12, optional)
        disease_type: '1' สำหรับโรค, '2' สำหรับศัตรูพืช, 'all' สำหรับทั้งหมด
        
    Returns:
        total_detections: จำนวนการตรวจพบทั้งหมด
        top_items: 5 อันดับที่พบมากที่สุด
        chart_data: ข้อมูลสำหรับแสดงกราฟ
    """
    try:
        # แปลงปี พ.ศ. เป็น ค.ศ. ถ้าจำเป็น
        if year > 2500:
            year = year - 543
        
        detection_collection = get_collection("detection")
        
        # สร้าง query พื้นฐาน
        if month:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(microseconds=1)
            chart_title = f'สถิติรายวัน เดือน{THAI_MONTHS.get(month, "")} {year + 543}'
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            chart_title = f'สถิติรายเดือน ปี {year + 543}'
        
        base_match = {
            "timestamp": {"$gte": start_date, "$lte": end_date}
        }
        
        # นับจำนวนการตรวจพบทั้งหมด
        total_detections = await detection_collection.count_documents(base_match)
        
        # ดึงข้อมูลสำหรับ Top 5
        pipeline_top = [
            {"$match": base_match},
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": "$disease_info"},
            {
                "$group": {
                    "_id": "$disease_pest_id",
                    "thai_name": {"$first": "$disease_info.thai_name"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        
        cursor_top = detection_collection.aggregate(pipeline_top)
        top_items_raw = await cursor_top.to_list(length=5)
        top_items = [{"name": item["thai_name"], "count": item["count"]} for item in top_items_raw]
        
        # เตรียมข้อมูลสำหรับกราฟ
        if month:
            # กราฟรายวัน
            num_days = (end_date - start_date).days + 1
            labels = [str(d) for d in range(1, num_days + 1)]
            group_by = {"$dayOfMonth": "$timestamp"}
        else:
            # กราฟรายเดือน
            labels = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
            group_by = {"$month": "$timestamp"}
        
        # ข้อมูลโรค (type=1)
        pipeline_disease_chart = [
            {"$match": base_match},
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": "$disease_info"},
            {"$match": {"disease_info.type": "1"}},
            {
                "$group": {
                    "_id": group_by,
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        # ข้อมูลศัตรูพืช (type=2)
        pipeline_pest_chart = [
            {"$match": base_match},
            {
                "$lookup": {
                    "from": "diseases_pest",
                    "localField": "disease_pest_id",
                    "foreignField": "ID",
                    "as": "disease_info"
                }
            },
            {"$unwind": "$disease_info"},
            {"$match": {"disease_info.type": "2"}},
            {
                "$group": {
                    "_id": group_by,
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        cursor_disease_chart = detection_collection.aggregate(pipeline_disease_chart)
        cursor_pest_chart = detection_collection.aggregate(pipeline_pest_chart)
        
        disease_data_raw = await cursor_disease_chart.to_list(length=None)
        pest_data_raw = await cursor_pest_chart.to_list(length=None)
        
        # สร้าง array สำหรับกราฟ
        data_len = len(labels)
        disease_data = [0] * data_len
        pest_data = [0] * data_len
        
        for item in disease_data_raw:
            idx = int(item["_id"]) - 1
            if 0 <= idx < data_len:
                disease_data[idx] = item["count"]
        
        for item in pest_data_raw:
            idx = int(item["_id"]) - 1
            if 0 <= idx < data_len:
                pest_data[idx] = item["count"]
        
        chart_data = {
            "title": chart_title,
            "labels": labels,
            "datasets": [
                {"label": "โรคพืช", "data": disease_data},
                {"label": "แมลงศัตรูพืช", "data": pest_data}
            ]
        }
        
        return {
            "total_detections": total_detections,
            "top_items": top_items,
            "chart_data": chart_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")


@router.get("/api/admin/available-months")
async def get_available_months(
    year: int
):
    """
    API สำหรับดึงข้อมูลเดือนที่มีการตรวจพบข้อมูล สำหรับปีที่ระบุ
    
    Args:
        year: ปีที่ต้องการดู (รองรับทั้ง พ.ศ. และ ค.ศ.)
        
    Returns:
        List of months with data
    """
    try:
        # แปลงปี พ.ศ. เป็น ค.ศ. ถ้าจำเป็น
        if year > 2500:
            year = year - 543
        
        detection_collection = get_collection("detection")
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": datetime(year, 1, 1),
                        "$lte": datetime(year, 12, 31, 23, 59, 59)
                    }
                }
            },
            {
                "$group": {
                    "_id": {"$month": "$timestamp"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        cursor = detection_collection.aggregate(pipeline)
        months_data = await cursor.to_list(length=None)
        
        available_months = [
            {"value": m["_id"], "name": THAI_MONTHS.get(m["_id"], "ไม่ระบุ")}
            for m in months_data
        ]
        
        return available_months
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")
