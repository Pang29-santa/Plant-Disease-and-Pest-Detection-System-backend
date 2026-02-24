"""
Vegetable Routes (ผัก)
จัดการข้อมูลผักทั้งหมด
"""

from typing import List, Optional, Dict, Any
import shutil
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
from bson import ObjectId

from database import get_collection
from models import Vegetable, VegetableBase, NutritionVegBase
from .utils import serialize_doc

router = APIRouter(prefix="/api/vegetable", tags=["Vegetable"])


@router.get("")
async def get_vegetables(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """ดึงข้อมูลผักทั้งหมด"""
    collection = get_collection("vegetable")
    
    # Get total count
    total = await collection.count_documents({})
    
    cursor = collection.find({}).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {
        "success": True,
        "total": total,
        "count": len(docs),
        "data": [serialize_doc(doc) for doc in docs]
    }


@router.get("/search")
async def search_vegetables(
    q: str
):
    """ค้นหาผัก"""
    collection = get_collection("vegetable")
    query = {
        "$or": [
            {"thai_name": {"$regex": q, "$options": "i"}},
            {"eng_name": {"$regex": q, "$options": "i"}},
            {"sci_name": {"$regex": q, "$options": "i"}}
        ]
    }
    cursor = collection.find(query)
    docs = await cursor.to_list(length=100)
    return {"count": len(docs), "data": [serialize_doc(doc) for doc in docs]}


@router.get("/{id}", response_model=Vegetable)
async def get_vegetable(
    id: str
):
    """ดึงข้อมูลผักตาม ID"""
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    return serialize_doc(doc)


@router.get("/by-vegetable-id/{vegetable_id}", response_model=Vegetable)
async def get_vegetable_by_vegetable_id(
    vegetable_id: int
):
    """ดึงข้อมูลผักตาม vegetable_id"""
    collection = get_collection("vegetable")
    doc = await collection.find_one({"vegetable_id": vegetable_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    return serialize_doc(doc)


# ============== Original Endpoints (Backward Compatibility) ==============

@router.post("", response_model=Vegetable)
async def create_vegetable(
    vegetable: VegetableBase
):
    """เพิ่มข้อมูลผักใหม่ (แบบไม่มีรูปภาพ หรือใช้ image_paths ที่อัปโหลดแยกไว้แล้ว)"""
    collection = get_collection("vegetable")
    result = await collection.insert_one(vegetable.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=Vegetable)
async def update_vegetable(
    id: str,
    vegetable: VegetableBase
):
    """อัปเดตข้อมูลผัก (แบบไม่มีรูปภาพ)"""
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    update_data = vegetable.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


# ============== New Endpoints with Multiple Images Support ==============

@router.post("/with-images", response_model=Vegetable)
async def create_vegetable_with_images(
    thai_name: str = Form(...),
    eng_name: Optional[str] = Form(None),
    sci_name: Optional[str] = Form(None),
    growth: Optional[int] = Form(None),
    planting_method: Optional[str] = Form(None),
    care: Optional[str] = Form(None),
    details: Optional[str] = Form(None),
    planting_method_en: Optional[str] = Form(None),
    care_en: Optional[str] = Form(None),
    details_en: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    gallery_images: List[UploadFile] = File(default=[])
):
    """
    เพิ่มข้อมูลผักพร้อมรูปภาพ
    
    - cover_image: รูปภาพปก (1 รูป)
    - gallery_images: รูปภาพเพิ่มเติม (สูงสุด 4 รูป)
    """
    from utils.file_handler import save_multiple_images, validate_multiple_images
    
    # ตรวจสอบจำนวนรูปภาพ
    total_images = (1 if cover_image else 0) + len(gallery_images)
    if total_images > 5:
        raise HTTPException(status_code=400, detail="สามารถอัปโหลดรูปภาพได้สูงสุด 5 รูป (รวมรูปปก)")
    
    # สร้างข้อมูลผักก่อน (ยังไม่มีรูป)
    collection = get_collection("vegetable")
    
    # หา vegetable_id ถัดไป
    last_doc = await collection.find_one(sort=[("vegetable_id", -1)])
    next_id = (last_doc.get("vegetable_id", 0) + 1) if last_doc else 1
    
    vegetable_data = {
        "vegetable_id": next_id,
        "thai_name": thai_name,
        "eng_name": eng_name,
        "sci_name": sci_name,
        "growth": growth,
        "planting_method": planting_method,
        "care": care,
        "details": details,
        "planting_method_en": planting_method_en,
        "care_en": care_en,
        "details_en": details_en,
        "image_paths": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    # ลบค่า None ออก
    vegetable_data = {k: v for k, v in vegetable_data.items() if v is not None}
    
    # บันทึกข้อมูลผัก
    result = await collection.insert_one(vegetable_data)
    inserted_id = result.inserted_id
    
    try:
        image_paths = []
        
        # 1. Save Cover Image
        if cover_image:
            cover_paths = await save_multiple_images(
                files=[cover_image],
                image_type="vegetables",
                entity_id=str(next_id),
                start_index=1
            )
            if cover_paths:
                image_paths.extend(cover_paths)
                
        # 2. Save Gallery Images
        if gallery_images and len(gallery_images) > 0:
            gallery_paths = await save_multiple_images(
                files=gallery_images,
                image_type="vegetable_gallery", # แยกเก็บใน static/img/vegetables
                entity_id=str(next_id),
                start_index=2
            )
            image_paths.extend(gallery_paths)
            
        # อัปเดตข้อมูลด้วยรูปภาพ
        if image_paths:
            await collection.update_one(
                {"_id": inserted_id},
                {
                    "$set": {
                        "image_paths": image_paths,
                        "image_path": image_paths[0] if image_paths else None,  # เก็บรูปแรกเป็น primary
                        "updated_at": datetime.now()
                    }
                }
            )
            
    except HTTPException:
        # ถ้าอัปโหลดรูปไม่สำเร็จ ลบข้อมูลผักที่เพิ่งสร้าง
        await collection.delete_one({"_id": inserted_id})
        raise
    
    new_doc = await collection.find_one({"_id": inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}/with-images", response_model=Vegetable)
async def update_vegetable_with_images(
    id: str,
    thai_name: Optional[str] = Form(None),
    eng_name: Optional[str] = Form(None),
    sci_name: Optional[str] = Form(None),
    growth: Optional[int] = Form(None),
    planting_method: Optional[str] = Form(None),
    care: Optional[str] = Form(None),
    details: Optional[str] = Form(None),
    planting_method_en: Optional[str] = Form(None),
    care_en: Optional[str] = Form(None),
    details_en: Optional[str] = Form(None),
    
    # Images logic split
    cover_image: Optional[UploadFile] = File(None),         # New Cover File
    existing_cover_path: Optional[str] = Form(None),        # Existing Cover Path
    
    gallery_images: List[UploadFile] = File(default=[]),    # New Gallery Files
    existing_gallery_paths: Optional[str] = Form(None)      # Existing Gallery Paths (JSON)
):
    """
    อัปเดตข้อมูลผักพร้อมจัดการรูปภาพแยกส่วน (Cover & Gallery)
    """
    from utils.file_handler import save_multiple_images, delete_multiple_images
    import json
    
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    collection = get_collection("vegetable")
    existing = await collection.find_one({"_id": ObjectId(id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    
    veg_id = existing.get("vegetable_id", id)
    
    # 1. Parse Existing Gallery Paths
    valid_gallery_paths = []
    if existing_gallery_paths:
        try:
            valid_gallery_paths = json.loads(existing_gallery_paths)
            if not isinstance(valid_gallery_paths, list):
                valid_gallery_paths = []
        except json.JSONDecodeError:
            valid_gallery_paths = []
            
    # 2. Check total limit
    # Count: (New Cover OR Existing Cover) + (New Gallery Count + Existing Gallery Count)
    has_cover = 1 if (cover_image or existing_cover_path) else 0
    total_images = has_cover + len(gallery_images) + len(valid_gallery_paths)
    
    if total_images > 5:
        raise HTTPException(
            status_code=400, 
            detail=f"จำนวนรูปภาพรวมต้องไม่เกิน 5 รูป"
        )
    
    # 3. Handle Deletions
    # Gather all paths we WANT to keep
    paths_to_keep = []
    if existing_cover_path:
        paths_to_keep.append(existing_cover_path)
    paths_to_keep.extend(valid_gallery_paths)
    
    # Gather all paths currently in DB
    current_db_paths = existing.get("image_paths", []) or []
    if existing.get("image_path") and not current_db_paths:
        current_db_paths = [existing.get("image_path")]
        
    # Find what to delete
    images_to_delete = [p for p in current_db_paths if p not in paths_to_keep]
    
    if images_to_delete:
        delete_multiple_images(images_to_delete)
        
        # 4. Upload & Assemble
    final_image_paths = []
    
    # 4.1 Handle Cover
    if cover_image:
        # Save new cover (Index 1)
        new_cover_paths = await save_multiple_images(
            files=[cover_image],
            image_type="vegetables",
            entity_id=str(veg_id),
            start_index=1
        )
        if new_cover_paths:
            final_image_paths.append(new_cover_paths[0])
    elif existing_cover_path:
        # Keep old cover
        final_image_paths.append(existing_cover_path)
        
    # 4.2 Handle Gallery
    # Add existing gallery first (preserve order if needed, or user order)
    final_image_paths.extend(valid_gallery_paths)
    
    # Add new gallery
    if gallery_images and len(gallery_images) > 0:
        # Start index for new gallery images should be after cover (1) + existing gallery count
        # Or simple counting: currently we have len(final_image_paths) images.
        # Next index is len(final_image_paths) + 1.
        next_index = len(final_image_paths) + 1
        
        new_gallery_paths = await save_multiple_images(
            files=gallery_images,
            image_type="vegetable_gallery", # แยกเก็บใน static/img/vegetables
            entity_id=str(veg_id),
            start_index=next_index
        )
        final_image_paths.extend(new_gallery_paths)
    
    # 5. Update DB
    update_data = {
        "updated_at": datetime.now()
    }
    
    if thai_name is not None: update_data["thai_name"] = thai_name
    if eng_name is not None: update_data["eng_name"] = eng_name
    if sci_name is not None: update_data["sci_name"] = sci_name
    if growth is not None: update_data["growth"] = growth
    if planting_method is not None: update_data["planting_method"] = planting_method
    if care is not None: update_data["care"] = care
    if details is not None: update_data["details"] = details
    if planting_method_en is not None: update_data["planting_method_en"] = planting_method_en
    if care_en is not None: update_data["care_en"] = care_en
    if details_en is not None: update_data["details_en"] = details_en
    
    update_data["image_paths"] = final_image_paths
    update_data["image_path"] = final_image_paths[0] if final_image_paths else None
    
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_vegetable(
    id: str
):
    """ลบข้อมูลผัก พร้อมลบรูปภาพทั้งหมด"""
    from utils.file_handler import delete_multiple_images
    
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Find vegetable to get vegetable_id และรูปภาพ
    vegetable = await collection.find_one({"_id": ObjectId(id)})
    if not vegetable:
        raise HTTPException(status_code=404, detail="Vegetable not found")
        
    veg_id = vegetable.get("vegetable_id")
    
    # ลบรูปภาพทั้งหมด
    image_paths = vegetable.get("image_paths", []) or []
    if vegetable.get("image_path") and not image_paths:
        image_paths = [vegetable.get("image_path")]
    
    if image_paths:
        delete_multiple_images(image_paths)
    
    # Check if vegetable is currently being planted
    planting_collection = get_collection("planting_veg")
    active_planting = await planting_collection.find_one({
        "vegetable_id": veg_id,
        "status": {"$in": [0, 1]} # 0=Planned, 1=Planting
    })
    
    if active_planting:
         raise HTTPException(
             status_code=400, 
             detail=f"ไม่สามารถลบข้อมูลได้เนื่องจากมีผู้ใช้งานปลูกผักชนิดนี้อยู่ (Planting ID: {active_planting.get('planting_id')})"
         )
    
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    return {"message": "Vegetable deleted successfully"}


@router.delete("/{id}/images/{image_index}")
async def delete_vegetable_image(
    id: str,
    image_index: int
):
    """ลบรูปภาพเฉพาะรูปของผัก"""
    from utils.file_handler import delete_image
    
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    collection = get_collection("vegetable")
    vegetable = await collection.find_one({"_id": ObjectId(id)})
    if not vegetable:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    
    image_paths = vegetable.get("image_paths", []) or []
    if vegetable.get("image_path") and not image_paths:
        image_paths = [vegetable.get("image_path")]
    
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


@router.get("/{id}/nutrition")
async def get_vegetable_nutrition(
    id: str
):
    """ดึงข้อมูลโภชนาการของผัก"""
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    vegetable = await collection.find_one({"_id": ObjectId(id)})
    if not vegetable:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    
    veg_id = vegetable.get("vegetable_id")
    
    # Get nutrition data with names
    nutrition_veg_collection = get_collection("nutrition_veg")
    nutrition_collection = get_collection("nutrition")
    
    cursor = nutrition_veg_collection.find({"vegetable_id": veg_id})
    nutrition_data = await cursor.to_list(length=100)
    
    # Manually join with nutrition collection to get names
    # Manually join with nutrition collection to get names
    result_nutrition = []
    for n in nutrition_data:
        n_doc = serialize_doc(n)
        
        # If nutrition_id exists, try to fetch name from nutrition table
        if n_doc.get("nutrition_id"):
            raw_nut_id = n_doc.get("nutrition_id")
            nut_info = None
            
            # Try finding by int
            try:
                nut_id_int = int(raw_nut_id)
                nut_info = await nutrition_collection.find_one({"nutrition_id": nut_id_int})
            except:
                pass
                
            # If not found, try finding by string
            if not nut_info:
                nut_info = await nutrition_collection.find_one({"nutrition_id": str(raw_nut_id)})
            
            if nut_info:
                # Get the best available name
                name_th = nut_info.get("nutrition_name_th")
                name_en = nut_info.get("nutrition_name_en")
                name_std = nut_info.get("nutrition_name")
                
                final_name = name_th or name_std or name_en
                
                # Assign name if not already present or to override
                if final_name:
                    n_doc["nutrition_name"] = final_name
                    n_doc["nutrient_name"] = final_name
        
        result_nutrition.append(n_doc)
    
    return {
        "vegetable": serialize_doc(vegetable),
        "nutrition": result_nutrition
    }


@router.get("/{id}/diseases")
async def get_vegetable_diseases(
    id: str
):
    """ดึงข้อมูลโรคและศัตรูพืชที่เกี่ยวข้องกับผัก"""
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    vegetable = await collection.find_one({"_id": ObjectId(id)})
    if not vegetable:
        raise HTTPException(status_code=404, detail="Vegetable not found")
    
    # Get diseases related to this vegetable
    diseases_collection = get_collection("diseases_pest")
    cursor = diseases_collection.find({})
    diseases = await cursor.to_list(length=100)
    
    return {
        "vegetable": serialize_doc(vegetable),
        "diseases": [serialize_doc(d) for d in diseases]
    }


# ============== Validation Endpoints ==============

@router.get("/check-vegetable-name")
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


# ============== File Upload Endpoints (Original - for backward compatibility) ==============

@router.post("/upload")
async def upload_vegetable_image(
    file: UploadFile = File(...)
):
    """อัปโหลดรูปภาพผัก (ใช้สำหรับอัปโหลดแยก)"""
    try:
        # Create directory if not exists
        upload_dir = Path("static/images/vegetables")
        # Ensure it's absolute or relative to project root
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
            "image_path": f"static/images/vegetables/{filename}"
        }
    except Exception as e:
        print(f"Error uploading: {e}")
        # In case of error, just fallback or raise HTTP exception
        raise HTTPException(status_code=500, detail="Image upload failed")


@router.post("/{id}/nutrition")
async def update_vegetable_nutrition(
    id: str,
    items: List[NutritionVegBase]
):
    """อัปเดตข้อมูลโภชนาการของผัก"""
    collection = get_collection("vegetable")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    vegetable = await collection.find_one({"_id": ObjectId(id)})
    if not vegetable:
        raise HTTPException(status_code=404, detail="Vegetable not found")
        
    veg_id = vegetable.get("vegetable_id")
    
    nutrition_collection = get_collection("nutrition_veg")
    
    # ลบข้อมูลเก่า
    await nutrition_collection.delete_many({"vegetable_id": veg_id})
    
    if items:
        new_items = []
        for item in items:
            # Debug log
            print(f"Received nutrition item: {item}")
            data = item.dict(exclude_unset=True)
            data["vegetable_id"] = veg_id
            new_items.append(data)
            
        if new_items:
            print(f"Saving nutrition items: {new_items}")
            await nutrition_collection.insert_many(new_items)
            
    return {"message": "Nutrition updated", "count": len(items)}
