"""
Diseases & Pest Routes (โรคและศัตรูพืช)
จัดการข้อมูลโรคพืชและศัตรูพืช
"""

from typing import List, Optional, Dict, Any
import shutil
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
from bson import ObjectId

from database import get_collection
from models import DiseasesPest, DiseasesPestBase
from .utils import serialize_doc

router = APIRouter(prefix="/api/diseases-pest", tags=["DiseasesPest"])


@router.get("")
async def get_diseases_pest(
    type: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงข้อมูลโรคและศัตรูพืช"""
    collection = get_collection("diseases_pest")
    
    query = {}
    if type:
        query["type"] = type
    if search:
        query["$or"] = [
            {"thai_name": {"$regex": search, "$options": "i"}},
            {"eng_name": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await collection.count_documents(query)
    
    cursor = collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {
        "success": True,
        "total": total,
        "count": len(docs),
        "data": [serialize_doc(doc) for doc in docs]
    }


@router.get("/diseases")
async def get_diseases_only(
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงข้อมูลโรคพืชเท่านั้น"""
    collection = get_collection("diseases_pest")
    
    query = {"type": "1"}  # 1 = โรค
    if search:
        query["$or"] = [
            {"thai_name": {"$regex": search, "$options": "i"}},
            {"eng_name": {"$regex": search, "$options": "i"}}
        ]
    
    cursor = collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    # Return array directly for frontend compatibility
    return [serialize_doc(doc) for doc in docs]


@router.get("/pests")
async def get_pests_only(
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงข้อมูลศัตรูพืชเท่านั้น"""
    collection = get_collection("diseases_pest")
    
    query = {"type": "2"}  # 2 = ศัตรูพืช
    if search:
        query["$or"] = [
            {"thai_name": {"$regex": search, "$options": "i"}},
            {"eng_name": {"$regex": search, "$options": "i"}}
        ]
    
    cursor = collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    # Return array directly for frontend compatibility
    return [serialize_doc(doc) for doc in docs]


@router.get("/{id}", response_model=DiseasesPest)
async def get_disease_pest(
    id: str
):
    """ดึงข้อมูลโรค/ศัตรูพืชตาม MongoDB ID หรือ numeric ID"""
    collection = get_collection("diseases_pest")
    
    # ลองหาด้วย MongoDB ID ก่อน
    if ObjectId.is_valid(id):
        doc = await collection.find_one({"_id": ObjectId(id)})
        if doc:
            return serialize_doc(doc)
    
    # ถ้าไม่ใช่ MongoDB ID หรือไม่เจอ ให้ลองหาด้วย numeric ID (ID field)
    try:
        numeric_id = int(id)
        doc = await collection.find_one({"ID": numeric_id})
        if doc:
            return serialize_doc(doc)
    except ValueError:
        pass
        
    raise HTTPException(status_code=404, detail="Disease/Pest not found")


@router.get("/by-disease-id/{disease_id}", response_model=DiseasesPest)
async def get_disease_by_disease_id(
    disease_id: int
):
    """ดึงข้อมูลโรค/ศัตรูพืชตาม Disease ID"""
    collection = get_collection("diseases_pest")
    doc = await collection.find_one({"ID": disease_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


# ============== Original Endpoints (Backward Compatibility) ==============

@router.post("", response_model=DiseasesPest)
async def create_disease_pest(
    data: DiseasesPestBase
):
    """เพิ่มข้อมูลโรค/ศัตรูพืช (แบบไม่มีรูปภาพ หรือใช้ image_paths ที่อัปโหลดแยกไว้แล้ว)"""
    collection = get_collection("diseases_pest")
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=DiseasesPest)
async def update_disease_pest(
    id: str,
    data: DiseasesPestBase
):
    """อัปเดตข้อมูลโรค/ศัตรูพืช (แบบไม่มีรูปภาพ)"""
    collection = get_collection("diseases_pest")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = data.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


# ============== New Endpoints with Multiple Images Support ==============

@router.post("/with-images", response_model=DiseasesPest)
async def create_disease_pest_with_images(
    type: str = Form(..., description="1=โรค, 2=ศัตรูพืช"),
    thai_name: str = Form(...),
    eng_name: Optional[str] = Form(None),
    cause: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    prevention: Optional[str] = Form(None),
    treatment: Optional[str] = Form(None),
    cause_en: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    prevention_en: Optional[str] = Form(None),
    treatment_en: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    gallery_images: List[UploadFile] = File(default=[])
):
    """
    เพิ่มข้อมูลโรค/ศัตรูพืชพร้อมรูปภาพ
    
    - cover_image: รูปภาพปก (1 รูป)
    - gallery_images: รูปภาพเพิ่มเติม (สูงสุด 4 รูป)
    """
    from utils.file_handler import save_multiple_images
    
    # ตรวจสอบจำนวนรูปภาพ
    total_images = (1 if cover_image else 0) + len(gallery_images)
    if total_images > 5:
        raise HTTPException(status_code=400, detail="สามารถอัปโหลดรูปภาพได้สูงสุด 5 รูป (รวมรูปปก)")
    
    # ตรวจสอบ type
    if type not in ["1", "2"]:
        raise HTTPException(status_code=400, detail="type ต้องเป็น '1' (โรค) หรือ '2' (ศัตรูพืช)")
    
    # สร้างข้อมูลก่อน (ยังไม่มีรูป)
    collection = get_collection("diseases_pest")
    
    # หา ID ถัดไป
    last_doc = await collection.find_one(sort=[("ID", -1)])
    next_id = (last_doc.get("ID", 0) + 1) if last_doc else 1
    
    data_dict = {
        "ID": next_id,
        "type": type,
        "thai_name": thai_name,
        "eng_name": eng_name,
        "cause": cause,
        "description": description,
        "prevention": prevention,
        "treatment": treatment,
        "cause_en": cause_en,
        "description_en": description_en,
        "prevention_en": prevention_en,
        "treatment_en": treatment_en,
        "image_paths": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    # ลบค่า None ออก
    data_dict = {k: v for k, v in data_dict.items() if v is not None}
    
    # บันทึกข้อมูล
    result = await collection.insert_one(data_dict)
    inserted_id = result.inserted_id
    
    try:
        image_paths = []
        image_folder = "diseases" if type == "1" else "pests"
        
        # 1. Save Cover
        if cover_image:
            cover_paths = await save_multiple_images(
                files=[cover_image],
                image_type=image_folder,
                entity_id=str(next_id)
            )
            if cover_paths:
                image_paths.extend(cover_paths)
                
        # 2. Save Gallery
        if gallery_images and len(gallery_images) > 0:
            gallery_paths = await save_multiple_images(
                files=gallery_images,
                image_type=image_folder,
                entity_id=str(next_id)
            )
            image_paths.extend(gallery_paths)
            
        # อัปเดตข้อมูลด้วยรูปภาพ
        if image_paths:
            await collection.update_one(
                {"_id": inserted_id},
                {
                    "$set": {
                        "image_paths": image_paths,
                        "image_path": image_paths[0] if image_paths else None,
                        "updated_at": datetime.now()
                    }
                }
            )
    except HTTPException:
        # ถ้าอัปโหลดรูปไม่สำเร็จ ลบข้อมูลที่เพิ่งสร้าง
        await collection.delete_one({"_id": inserted_id})
        raise
    
    new_doc = await collection.find_one({"_id": inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}/with-images", response_model=DiseasesPest)
async def update_disease_pest_with_images(
    id: str,
    type: Optional[str] = Form(None, description="1=โรค, 2=ศัตรูพืช"),
    thai_name: Optional[str] = Form(None),
    eng_name: Optional[str] = Form(None),
    cause: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    prevention: Optional[str] = Form(None),
    treatment: Optional[str] = Form(None),
    cause_en: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    prevention_en: Optional[str] = Form(None),
    treatment_en: Optional[str] = Form(None),
    
    # Images logic split
    cover_image: Optional[UploadFile] = File(None),
    existing_cover_path: Optional[str] = Form(None),
    
    gallery_images: List[UploadFile] = File(default=[]),
    existing_gallery_paths: Optional[str] = Form(None)
):
    """
    อัปเดตข้อมูลโรค/ศัตรูพืชพร้อมจัดการรูปภาพแยกส่วน (Cover & Gallery)
    """
    from utils.file_handler import save_multiple_images, delete_multiple_images
    import json
    
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # ตรวจสอบ type
    if type and type not in ["1", "2"]:
        raise HTTPException(status_code=400, detail="type ต้องเป็น '1' (โรค) หรือ '2' (ศัตรูพืช)")
    
    collection = get_collection("diseases_pest")
    existing = await collection.find_one({"_id": ObjectId(id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    
    disease_id = existing.get("ID", id)
    disease_type = type or existing.get("type", "1")
    
    # 1. Parse Existing Gallery Paths
    valid_gallery_paths = []
    if existing_gallery_paths:
        try:
            valid_gallery_paths = json.loads(existing_gallery_paths)
            if not isinstance(valid_gallery_paths, list):
                valid_gallery_paths = []
        except json.JSONDecodeError:
            valid_gallery_paths = []
            
    # 2. Check limits
    has_cover = 1 if (cover_image or existing_cover_path) else 0
    total_images = has_cover + len(gallery_images) + len(valid_gallery_paths)
    
    if total_images > 5:
        raise HTTPException(
            status_code=400,
            detail=f"จำนวนรูปภาพรวมต้องไม่เกิน 5 รูป"
        )
    
    # 3. Handle Deletions
    paths_to_keep = []
    if existing_cover_path:
        paths_to_keep.append(existing_cover_path)
    paths_to_keep.extend(valid_gallery_paths)
    
    current_db_paths = existing.get("image_paths", []) or []
    if existing.get("image_path") and not current_db_paths:
        current_db_paths = [existing.get("image_path")]
    
    images_to_delete = [p for p in current_db_paths if p not in paths_to_keep]
    
    if images_to_delete:
        delete_multiple_images(images_to_delete)
    
    # 4. Upload & Assemble
    final_image_paths = []
    image_folder = "diseases" if disease_type == "1" else "pests"
    
    # 4.1 Cover
    if cover_image:
        new_cover_paths = await save_multiple_images(
            files=[cover_image],
            image_type=image_folder,
            entity_id=str(disease_id)
        )
        if new_cover_paths:
            final_image_paths.append(new_cover_paths[0])
    elif existing_cover_path:
        final_image_paths.append(existing_cover_path)
        
    # 4.2 Gallery
    final_image_paths.extend(valid_gallery_paths)
    
    if gallery_images and len(gallery_images) > 0:
        new_gallery_paths = await save_multiple_images(
            files=gallery_images,
            image_type=image_folder,
            entity_id=str(disease_id)
        )
        final_image_paths.extend(new_gallery_paths)
    
    # 5. Update DB
    update_data = {
        "updated_at": datetime.now()
    }
    
    if type is not None: update_data["type"] = type
    if thai_name is not None: update_data["thai_name"] = thai_name
    if eng_name is not None: update_data["eng_name"] = eng_name
    if cause is not None: update_data["cause"] = cause
    if description is not None: update_data["description"] = description
    if prevention is not None: update_data["prevention"] = prevention
    if treatment is not None: update_data["treatment"] = treatment
    if cause_en is not None: update_data["cause_en"] = cause_en
    if description_en is not None: update_data["description_en"] = description_en
    if prevention_en is not None: update_data["prevention_en"] = prevention_en
    if treatment_en is not None: update_data["treatment_en"] = treatment_en
    
    update_data["image_paths"] = final_image_paths
    update_data["image_path"] = final_image_paths[0] if final_image_paths else None
    
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_disease_pest(
    id: str
):
    """ลบข้อมูลโรค/ศัตรูพืช พร้อมลบรูปภาพทั้งหมด"""
    from utils.file_handler import delete_multiple_images
    
    collection = get_collection("diseases_pest")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # หาข้อมูลเพื่อเอารูปภาพ
    existing = await collection.find_one({"_id": ObjectId(id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    
    # ลบรูปภาพทั้งหมด
    image_paths = existing.get("image_paths", []) or []
    if existing.get("image_path") and not image_paths:
        image_paths = [existing.get("image_path")]
    
    if image_paths:
        delete_multiple_images(image_paths)
    
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted successfully"}


@router.delete("/{id}/images/{image_index}")
async def delete_disease_image(
    id: str,
    image_index: int
):
    """ลบรูปภาพเฉพาะรูปของโรค/ศัตรูพืช"""
    from utils.file_handler import delete_image
    
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    collection = get_collection("diseases_pest")
    existing = await collection.find_one({"_id": ObjectId(id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    
    image_paths = existing.get("image_paths", []) or []
    if existing.get("image_path") and not image_paths:
        image_paths = [existing.get("image_path")]
    
    if image_index < 0 or image_index >= len(image_paths):
        raise HTTPException(status_code=400, detail="Invalid image index")
    
    # ลบรูปภาพ
    image_to_delete = image_paths[image_index]
    delete_image(image_to_delete)
    
    # อัปเดตข้อมูล
    new_paths = [p for i, p in enumerate(image_paths) if i != image_index]
    await collection.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "image_paths": new_paths,
                "image_path": new_paths[0] if new_paths else None,
                "updated_at": datetime.now()
            }
        }
    )
    
    return {"message": "Image deleted successfully", "remaining_images": len(new_paths)}


# ============== File Upload Endpoints (Original - for backward compatibility) ==============

@router.post("/upload")
async def upload_disease_image(
    file: UploadFile = File(...)
):
    """อัปโหลดรูปภาพโรค/ศัตรูพืช (ใช้สำหรับอัปโหลดแยก)"""
    try:
        # Create directory if not exists
        upload_dir = Path("static/images/diseases")
        if not upload_dir.exists():
            upload_dir.mkdir(parents=True, exist_ok=True)
            
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_filename = "".join([c for c in file.filename if c.isalnum() or c in "._-"])
        filename = f"{timestamp}_{safe_filename}"
        file_location = upload_dir / filename
        
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "success": True, 
            "image_path": f"static/images/diseases/{filename}"
        }
    except Exception as e:
        print(f"Error uploading: {e}")
        raise HTTPException(status_code=500, detail="Image upload failed")


# ============== Statistics Endpoints ==============

@router.get("/stats/by-type")
async def get_diseases_stats_by_type():
    """ดึงสถิติโรคและศัตรูพืชแยกตามประเภท"""
    collection = get_collection("diseases_pest")
    
    pipeline = [
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1}
        }}
    ]
    
    cursor = collection.aggregate(pipeline)
    stats = await cursor.to_list(length=10)
    
    # Map type codes to names
    type_names = {"1": "โรค", "2": "ศัตรูพืช"}
    result = []
    for s in stats:
        type_code = s.get("_id")
        result.append({
            "type": type_code,
            "type_name": type_names.get(type_code, "Unknown"),
            "count": s.get("count")
        })
    
    return {"stats": result}


@router.get("/stats/top-detected")
async def get_top_detected_diseases(
    limit: int = Query(10, ge=1, le=50)
):
    """ดึงโรค/ศัตรูพืชที่ถูกตรวจจับบ่อยที่สุด"""
    detection_collection = get_collection("detection")
    
    pipeline = [
        {"$group": {
            "_id": "$disease_pest_id",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    
    cursor = detection_collection.aggregate(pipeline)
    stats = await cursor.to_list(length=limit)
    
    # Get disease details
    diseases_collection = get_collection("diseases_pest")
    result = []
    for stat in stats:
        disease_id = stat.get("_id")
        disease = await diseases_collection.find_one({"ID": disease_id})
        if disease:
            result.append({
                "disease_id": disease_id,
                "thai_name": disease.get("thai_name"),
                "eng_name": disease.get("eng_name"),
                "type": disease.get("type"),
                "type_name": "โรค" if disease.get("type") == "1" else "ศัตรูพืช",
                "detection_count": stat.get("count")
            })
    
    return {"top_detected": result}


@router.get("/reports/monthly")
async def get_monthly_report(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    type: Optional[str] = None  # "1" = โรค, "2" = ศัตรูพืช, None = ทั้งหมด
):
    """ดึงรายงานสรุปรายเดือน"""
    from datetime import datetime
    
    detection_collection = get_collection("detection")
    diseases_collection = get_collection("diseases_pest")
    
    # สร้าง date range สำหรับเดือนที่เลือก
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # Query detections ในช่วงเวลาที่กำหนด
    detection_query = {
        "timestamp": {
            "$gte": start_date,
            "$lt": end_date
        }
    }
    
    # นับจำนวน detection ทั้งหมดในเดือน
    total_detections = await detection_collection.count_documents(detection_query)
    
    # Group by disease_pest_id
    pipeline = [
        {"$match": detection_query},
        {"$group": {
            "_id": "$disease_pest_id",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    
    cursor = detection_collection.aggregate(pipeline)
    detection_stats = await cursor.to_list(length=None)
    
    # Get disease details and filter by type if specified
    result = []
    disease_count = 0
    pest_count = 0
    
    for stat in detection_stats:
        disease_id = stat.get("_id")
        disease = await diseases_collection.find_one({"ID": disease_id})
        if disease:
            disease_type = disease.get("type")
            
            # Filter by type if specified
            if type and disease_type != type:
                continue
            
            # Count by type
            if disease_type == "1":
                disease_count += stat.get("count", 0)
            elif disease_type == "2":
                pest_count += stat.get("count", 0)
            
            result.append({
                "disease_id": disease_id,
                "thai_name": disease.get("thai_name"),
                "eng_name": disease.get("eng_name"),
                "type": disease_type,
                "type_name": "โรคพืช" if disease_type == "1" else "ศัตรูพืช",
                "detection_count": stat.get("count"),
                "image_path": disease.get("image_path")
            })
    
    return {
        "success": True,
        "year": year,
        "month": month,
        "type_filter": type,
        "total_detections": total_detections,
        "disease_detections": disease_count,
        "pest_detections": pest_count,
        "data": result
    }


# ============== Validation Endpoints ==============

@router.get("/check-diseasepest-name")
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
