"""
Detection Routes (การตรวจจับ)
จัดการข้อมูลการตรวจจับจาก AI/CCTV
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from database import get_collection
from models import Detection, DetectionBase
from .utils import serialize_doc
from .telegram import send_telegram_message, send_telegram_photo_with_caption
import html
import socket

def get_local_ip():
    """ดึงเลข IP ของเครื่องที่รันอยู่"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

router = APIRouter(prefix="/api/detection", tags=["Detection"])


@router.get("", response_model=List[Detection])
async def get_detections(
    user_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    vegetable_id: Optional[int] = None,
    disease_pest_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงประวัติการตรวจจับทั้งหมด"""
    collection = get_collection("detection")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if plot_id:
        query["plot_id"] = plot_id
    if vegetable_id:
        query["vegetable_id"] = vegetable_id
    if disease_pest_id:
        query["disease_pest_id"] = disease_pest_id
    
    cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/{id}", response_model=Detection)
async def get_detection(
    id: str
):
    """ดึงข้อมูลการตรวจจับตาม MongoDB ID"""
    collection = get_collection("detection")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Detection not found")
    return serialize_doc(doc)


@router.get("/by-detection-id/{detection_id}", response_model=Detection)
async def get_detection_by_detection_id(
    detection_id: int
):
    """ดึงข้อมูลการตรวจจับตาม detection_id"""
    collection = get_collection("detection")
    doc = await collection.find_one({"detection_id": detection_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Detection not found")
    return serialize_doc(doc)


@router.get("/by-user/{user_id}")
async def get_detections_by_user(
    user_id: str,
    start_date: Optional[str] = Query(None, description="Start date in ISO format (e.g., 2024-01-01T00:00:00)"),
    end_date: Optional[str] = Query(None, description="End date in ISO format (e.g., 2024-12-31T23:59:59)"),
    type: Optional[str] = Query(None, description="Filter by type: 'disease' (1) or 'pest' (2)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500)
):
    """ดึงข้อมูลการตรวจจับตาม User ID พร้อมข้อมูลที่เกี่ยวข้อง และรองรับการ filter ตามช่วงเวลา"""
    collection = get_collection("detection")
    
    # Try querying with both int and string user_id
    query_conditions = []
    try:
        query_conditions.append({"user_id": int(user_id)})
    except (ValueError, TypeError):
        pass
    query_conditions.append({"user_id": user_id})
    
    # Base query with user_id
    base_query = {"$or": query_conditions}
    
    # Add date range filter if provided
    # Note: MongoDB stores datetime in UTC, frontend sends ISO format (UTC)
    date_filter = {}
    if start_date:
        try:
            # Handle ISO format with or without timezone
            start_date_clean = start_date.replace('Z', '+00:00')
            start_dt = datetime.fromisoformat(start_date_clean)
            # Ensure it's UTC (remove timezone info for MongoDB compatibility)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
            date_filter["$gte"] = start_dt
            print(f"[Detection History] Start date filter (UTC): {start_dt}")
        except ValueError as e:
            print(f"[Detection History] Error parsing start_date '{start_date}': {e}")
    if end_date:
        try:
            end_date_clean = end_date.replace('Z', '+00:00')
            end_dt = datetime.fromisoformat(end_date_clean)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
            date_filter["$lte"] = end_dt
            print(f"[Detection History] End date filter (UTC): {end_dt}")
        except ValueError as e:
            print(f"[Detection History] Error parsing end_date '{end_date}': {e}")
    
    if date_filter:
        base_query["timestamp"] = date_filter
        print(f"[Detection History] Date range filter applied: {date_filter}")
    
    print(f"[Detection History] Query: user_id={user_id}, type={type}, skip={skip}, limit={limit}")
    
    # If type filter is provided, we need to get disease_pest_ids first
    if type:
        diseases_collection = get_collection("diseases_pest")
        type_mapping = {"disease": "1", "pest": "2"}
        type_value = type_mapping.get(type.lower())
        
        if type_value:
            # Get all disease_pest_ids with matching type
            matching_diseases = await diseases_collection.find(
                {"type": type_value},
                {"ID": 1}
            ).to_list(length=1000)
            disease_pest_ids = [d["ID"] for d in matching_diseases if "ID" in d]
            
            if disease_pest_ids:
                base_query["disease_pest_id"] = {"$in": disease_pest_ids}
            else:
                # No matching diseases found, return empty result
                return []
    
    # Use $or to match either int or string representation
    cursor = collection.find(base_query).sort("timestamp", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    
    # Enrich with related data
    diseases_collection = get_collection("diseases_pest")
    vegetables_collection = get_collection("vegetable")
    plots_collection = get_collection("plots")
    
    result = []
    for doc in docs:
        det_dict = serialize_doc(doc)
        
        # Get disease info
        if doc.get("disease_pest_id"):
            disease_pest_id = doc.get("disease_pest_id")
            # Try finding by ID (int) or _id (ObjectId/str) logic if needed, 
            # assuming ID is the field used for linking based on models
            disease = await diseases_collection.find_one({"ID": disease_pest_id})
            if disease:
                det_dict["disease"] = {
                    "thai_name": disease.get("thai_name"),
                    "eng_name": disease.get("eng_name"),
                    "type": disease.get("type"),
                    "severity": disease.get("severity")
                }
        
        # Get vegetable info
        if doc.get("vegetable_id"):
            veg_id = doc.get("vegetable_id")
            veg = await vegetables_collection.find_one({"vegetable_id": veg_id})
            if veg:
                det_dict["vegetable"] = {
                    "thai_name": veg.get("thai_name"),
                    "eng_name": veg.get("eng_name"),
                    "image": veg.get("image")
                }
        
        # Get plot info
        if doc.get("plot_id"):
            plot_id = doc.get("plot_id")
            # Handle plot_id as int or string if needed, but usually int based on other code
            plot = await plots_collection.find_one({"plot_id": plot_id})
            if plot:
                det_dict["plot"] = {
                    "plot_name": plot.get("plot_name")
                }
        
        result.append(det_dict)
        
    return result


@router.get("/by-plot/{plot_id}", response_model=List[Detection])
async def get_detections_by_plot(
    plot_id: int,
    limit: int = Query(50, ge=1, le=500)
):
    """ดึงข้อมูลการตรวจจับตาม Plot ID"""
    collection = get_collection("detection")
    cursor = collection.find({"plot_id": plot_id}).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/by-vegetable/{vegetable_id}", response_model=List[Detection])
async def get_detections_by_vegetable(
    vegetable_id: int,
    limit: int = Query(50, ge=1, le=500)
):
    """ดึงข้อมูลการตรวจจับตาม Vegetable ID"""
    collection = get_collection("detection")
    cursor = collection.find({"vegetable_id": vegetable_id}).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/by-disease/{disease_pest_id}", response_model=List[Detection])
async def get_detections_by_disease(
    disease_pest_id: int,
    limit: int = Query(50, ge=1, le=500)
):
    """ดึงข้อมูลการตรวจจับตาม Disease/Pest ID"""
    collection = get_collection("detection")
    cursor = collection.find({"disease_pest_id": disease_pest_id}).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.post("", response_model=Detection)
async def create_detection(
    data: DetectionBase
):
    """บันทึกการตรวจจับใหม่"""
    collection = get_collection("detection")
    
    # Set timestamp if not provided
    if not data.timestamp:
        data.timestamp = datetime.utcnow()
    
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    
    # Send notification if confidence is high
    if data.confidence and data.confidence > 0.8:
        await send_detection_notification(new_doc)
    
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=Detection)
async def update_detection(
    id: str,
    data: DetectionBase
):
    """อัปเดตข้อมูลการตรวจจับ"""
    collection = get_collection("detection")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = data.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_detection(
    id: str
):
    """ลบข้อมูลการตรวจจับ"""
    collection = get_collection("detection")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Detection not found")
    return {"message": "Detection deleted successfully"}


@router.get("/stats/summary")
async def get_detection_stats(
    user_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    days: int = Query(7, ge=1, le=365)
):
    """ดึงสถิติการตรวจจับ"""
    collection = get_collection("detection")
    
    # Calculate date range
    from_date = datetime.utcnow() - timedelta(days=days)
    
    query = {"timestamp": {"$gte": from_date}}
    if user_id:
        query["user_id"] = user_id
    if plot_id:
        query["plot_id"] = plot_id
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$disease_pest_id",
            "count": {"$sum": 1},
            "avg_confidence": {"$avg": "$confidence"}
        }}
    ]
    
    cursor = collection.aggregate(pipeline)
    stats = await cursor.to_list(length=100)
    
    return {
        "days": days,
        "stats": [serialize_doc(s) for s in stats]
    }


@router.get("/stats/by-user/{user_id}")
async def get_user_detection_stats(
    user_id: int,
    days: int = Query(30, ge=1, le=365)
):
    """ดึงสถิติการตรวจจับของผู้ใช้แยกตามโรค/ศัตรูพืช"""
    collection = get_collection("detection")
    
    from_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "user_id": user_id,
            "timestamp": {"$gte": from_date}
        }},
        {"$group": {
            "_id": "$disease_pest_id",
            "count": {"$sum": 1},
            "latest_detection": {"$max": "$timestamp"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    cursor = collection.aggregate(pipeline)
    stats = await cursor.to_list(length=50)
    
    # Get disease names
    diseases_collection = get_collection("diseases_pest")
    result = []
    for stat in stats:
        disease_id = stat.get("_id")
        disease = await diseases_collection.find_one({"ID": disease_id})
        result.append({
            "disease_pest_id": disease_id,
            "disease_name": disease.get("thai_name", "Unknown") if disease else "Unknown",
            "count": stat.get("count"),
            "latest_detection": stat.get("latest_detection")
        })
    
    return {
        "user_id": user_id,
        "days": days,
        "total_detections": sum(s.get("count", 0) for s in stats),
        "stats": result
    }


@router.get("/stats/by-plot/{plot_id}")
async def get_plot_detection_stats(
    plot_id: int,
    days: int = Query(30, ge=1, le=365)
):
    """ดึงสถิติการตรวจจับของแปลงแยกตามโรค/ศัตรูพืช"""
    collection = get_collection("detection")
    
    from_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "plot_id": plot_id,
            "timestamp": {"$gte": from_date}
        }},
        {"$group": {
            "_id": "$disease_pest_id",
            "count": {"$sum": 1},
            "latest_detection": {"$max": "$timestamp"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    cursor = collection.aggregate(pipeline)
    stats = await cursor.to_list(length=50)
    
    # Get disease names
    diseases_collection = get_collection("diseases_pest")
    result = []
    for stat in stats:
        disease_id = stat.get("_id")
        disease = await diseases_collection.find_one({"ID": disease_id})
        result.append({
            "disease_pest_id": disease_id,
            "disease_name": disease.get("thai_name", "Unknown") if disease else "Unknown",
            "count": stat.get("count"),
            "latest_detection": stat.get("latest_detection")
        })
    
    return {
        "plot_id": plot_id,
        "days": days,
        "total_detections": sum(s.get("count", 0) for s in stats),
        "stats": result
    }


@router.post("/batch")
async def create_detections_batch(
    data: List[DetectionBase]
):
    """บันทึกการตรวจจับหลายรายการพร้อมกัน"""
    collection = get_collection("detection")
    
    documents = []
    for item in data:
        if not item.timestamp:
            item.timestamp = datetime.utcnow()
        documents.append(item.dict(exclude_unset=True))
    
    result = await collection.insert_many(documents)
    
    return {
        "message": f"Inserted {len(result.inserted_ids)} detections",
        "count": len(result.inserted_ids)
    }


@router.get("/recent/{user_id}")
async def get_recent_detections(
    user_id: int,
    limit: int = Query(10, ge=1, le=100)
):
    """ดึงการตรวจจับล่าสุดของผู้ใช้ พร้อมข้อมูลที่เกี่ยวข้อง"""
    collection = get_collection("detection")
    
    cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    detections = await cursor.to_list(length=limit)
    
    # Enrich with related data
    diseases_collection = get_collection("diseases_pest")
    vegetables_collection = get_collection("vegetable")
    plots_collection = get_collection("plots")
    
    result = []
    for det in detections:
        det_dict = serialize_doc(det)
        
        # Get disease info
        if det.get("disease_pest_id"):
            disease = await diseases_collection.find_one({"ID": det.get("disease_pest_id")})
            if disease:
                det_dict["disease"] = {
                    "thai_name": disease.get("thai_name"),
                    "eng_name": disease.get("eng_name"),
                    "type": disease.get("type")
                }
        
        # Get vegetable info
        if det.get("vegetable_id"):
            veg = await vegetables_collection.find_one({"vegetable_id": det.get("vegetable_id")})
            if veg:
                det_dict["vegetable"] = {
                    "thai_name": veg.get("thai_name"),
                    "eng_name": veg.get("eng_name")
                }
        
        # Get plot info
        if det.get("plot_id"):
            plot = await plots_collection.find_one({"plot_id": det.get("plot_id")})
            if plot:
                det_dict["plot"] = {
                    "plot_name": plot.get("plot_name")
                }
        
        result.append(det_dict)
    
    return {"count": len(result), "data": result}


async def send_detection_notification(detection: dict):
    """ส่งการแจ้งเตือนเมื่อพบการตรวจจับไปยัง Telegram"""
    user_id = detection.get("user_id")
    
    if not user_id:
        print("[NOTIFICATION] No user_id, skipping notification")
        return
    
    try:
        # Get disease info
        disease_collection = get_collection("diseases_pest")
        disease = await disease_collection.find_one({"ID": detection.get("disease_pest_id")})
        
        disease_name = disease.get("thai_name", "ไม่ระบุ") if disease else "ไม่ระบุ"
        disease_name_en = disease.get("eng_name", "") if disease else ""
        disease_id = disease.get("ID") if disease else None
        confidence = detection.get("confidence", 0)
        
        # Get treatment from database
        treatment_text = disease.get("treatment", "") if disease else ""
        
        # Get user Telegram connection
        telegram_collection = get_collection("telegram_connections")
        connection = await telegram_collection.find_one({
            "user_id": user_id,
            "status": "active"
        })
        
        if not connection:
            print(f"⚠️  [NOTIFICATION] No active Telegram connection for user {user_id}")
            return
        
        chat_id = connection.get("chat_id")
        if not chat_id:
            print(f"⚠️  [NOTIFICATION] No chat_id for user {user_id}")
            return
        
        # Determine category
        disease_type = disease.get("type", "") if disease else ""
        category_text = "โรคพืช" if disease_type == "1" else "ศัตรูพืช" if disease_type == "2" else "พบการตรวจจับ"
        

        
        # Build message in HTML format
        disease_name = html.escape(disease_name)
        disease_name_en = html.escape(disease_name_en)
        
        telegram_message = f"<b>🚨 แจ้งเตือนการตรวจพบ {category_text}</b>\n\n"
        telegram_message += f"<b>ชื่อ:</b> {disease_name}\n"
        telegram_message += f"<b>ชื่อภาษาอังกฤษ:</b> {disease_name_en}\n"
        telegram_message += f"<b>ความมั่นใจ:</b> {confidence}%\n\n"
        telegram_message += "<b>การรักษา:</b>\n"
        
        # Add treatment steps
        if treatment_text:
            import re
            clean_treatment = re.sub(r'<[^>]+>', '', treatment_text)
            clean_treatment = html.escape(clean_treatment) # Escape content
            steps = re.split(r'(?:\d+[.)]\s*|\n+)', clean_treatment)
            steps = [s.strip() for s in steps if s.strip()]
            for i, step in enumerate(steps[:5], 1):
                telegram_message += f"{i}. {step}\n"
        else:
            telegram_message += "ไม่มีข้อมูล\n"
        
        # เตรียมเวลาและลิงก์
        import os
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        timestamp = detection.get("timestamp", datetime.utcnow())
        telegram_message += f"\n<i>บันทึกเมื่อ: {timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'N/A'}</i>"
        
        reply_markup = None
        if disease_id:
            detail_url = f"{frontend_url}/diseases-pest/details/{disease_id}"
            
            # แปลง localhost เป็น IP จริงเพื่อให้ Telegram ยอมให้ใช้ในปุ่มกด (Inline Keyboard)
            if "localhost" in detail_url or "127.0.0.1" in detail_url:
                local_ip = get_local_ip()
                detail_url = detail_url.replace("localhost", local_ip).replace("127.0.0.1", local_ip)
            
            # ใช้ปุ่มกดแทนการวางลิงก์ดิบ เพื่อ "ซ่อน" ลิงก์ที่ยาวและดูไม่สวย
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔗 ดูรายละเอียดและวิธีการจัดการ", "url": detail_url}]
                ]
            }
        
        # Get image URL if available
        image_path = detection.get("image_path")
        image_url = None
        if image_path:
            from utils.file_handler import get_image_url
            image_url = get_image_url(image_path)

        # Send notification
        print(f"🔍  [NOTIFICATION] Image URL: {image_url}")

        if image_url:
            success = send_telegram_photo_with_caption(chat_id, image_url, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
        else:
            success = send_telegram_message(chat_id, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
        
        if success:
            print(f"✅  [NOTIFICATION] Telegram notification sent to user {user_id}")
        else:
            print(f"❌  [NOTIFICATION] Failed to send Telegram notification to user {user_id}")
            
    except Exception as e:
        print(f"❌  [NOTIFICATION] Error sending notification: {e}")
