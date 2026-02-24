"""
Plot Routes (แปลงผัก)
จัดการข้อมูลแปลงปลูกผัก
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel

from database import get_collection
from models import Plot, PlotBase
from .utils import serialize_doc

router = APIRouter(prefix="/api/plots", tags=["Plots"])


@router.get("")
async def get_plots(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """ดึงข้อมูลแปลงทั้งหมด"""
    collection = get_collection("plots")
    
    query = {"is_deleted": {"$ne": 1}}  # Exclude deleted plots
    if user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status
    
    cursor = collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    
    # ดึงข้อมูลการปลูกปัจจุบันสำหรับแต่ละแปลง
    result = []
    planting_col = get_collection("planting_veg")
    for doc in docs:
        d = serialize_doc(doc)
        if str(d.get("status")) == "1":
            active_planting = await planting_col.find_one({
                "plot_object_id": str(doc["_id"]),
                "status": 1
            })
            if active_planting:
                d["current_planting"] = serialize_doc(active_planting)
        result.append(d)
        
    return result


@router.get("/{id}")
async def get_plot(
    id: str,
):
    """ดึงข้อมูลแปลงตาม MongoDB ID"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    doc = await collection.find_one({
        "_id": ObjectId(id),
        "is_deleted": {"$ne": 1}
    })
    
    if not doc:
        raise HTTPException(status_code=404, detail="Plot not found")
    return serialize_doc(doc)



@router.get("/by-plot-id/{plot_id}", response_model=Plot)
async def get_plot_by_plot_id(
    plot_id: int,
):
    """ดึงข้อมูลแปลงตาม plot_id"""
    collection = get_collection("plots")
    doc = await collection.find_one({
        "plot_id": plot_id,
        "is_deleted": {"$ne": 1}
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Plot not found")
    return serialize_doc(doc)


@router.get("/user/{user_id}", response_model=List[Plot])
async def get_plots_by_user(
    user_id: int,
):
    """ดึงข้อมูลแปลงตาม user_id"""
    collection = get_collection("plots")
    cursor = collection.find({
        "user_id": user_id,
        "is_deleted": {"$ne": 1}
    })
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.post("", response_model=Plot)
async def create_plot(
    plot: PlotBase,
):
    """สร้างแปลงใหม่"""
    collection = get_collection("plots")
    
    # Generate auto-increment plot_id
    if plot.plot_id is None:
        # Find the max plot_id in the collection
        cursor = collection.find({}, {"plot_id": 1}).sort("plot_id", -1).limit(1)
        docs = await cursor.to_list(length=1)
        if docs and "plot_id" in docs[0] and isinstance(docs[0]["plot_id"], int):
            plot.plot_id = docs[0]["plot_id"] + 1
        else:
            plot.plot_id = 1

    # Set default status
    if not plot.status:
        plot.status = "0"  # ว่าง
    if not isinstance(plot.is_deleted, int):
        plot.is_deleted = 0  # ไม่ลบ
    
    result = await collection.insert_one(plot.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=Plot)
async def update_plot(
    id: str,
    plot: PlotBase,
):
    """อัปเดตข้อมูลแปลง"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = plot.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Plot not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_plot(
    id: str,
    hard_delete: bool = False
):
    """ลบแปลง (soft delete หรือ hard delete)"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    if hard_delete:
        # Hard delete
        result = await collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Plot not found")
        return {"message": "Plot permanently deleted"}
    else:
        # Soft delete
        result = await collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_deleted": 1}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Plot not found")
        return {"message": "Plot soft deleted"}


@router.get("/{id}/details")
async def get_plot_details(
    id: str,
):
    """ดึงข้อมูลแปลงพร้อมรายละเอียดที่เกี่ยวข้อง"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    plot = await collection.find_one({
        "_id": ObjectId(id),
        "is_deleted": {"$ne": 1}
    })
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    
    result = {"plot": serialize_doc(plot)}
    plot_id = plot.get("plot_id")
    
    # Get CCTV info
    cctv_collection = get_collection("cctv")
    cctv_cursor = cctv_collection.find({"plot_id": plot_id})
    cctvs = await cctv_cursor.to_list(length=10)
    result["cctv"] = [serialize_doc(c) for c in cctvs]
    
    # Get current planting
    planting_collection = get_collection("planting_veg")
    planting_cursor = planting_collection.find({
        "plot_id": plot_id,
        "status": {"$in": [0, 1]}  # วางแผน หรือ กำลังปลูก
    })
    plantings = await planting_cursor.to_list(length=10)
    result["active_plantings"] = [serialize_doc(p) for p in plantings]
    
    # Get recent detections
    detection_collection = get_collection("detection")
    detection_cursor = detection_collection.find({"plot_id": plot_id}).sort("timestamp", -1).limit(5)
    detections = await detection_cursor.to_list(length=5)
    result["recent_detections"] = [serialize_doc(d) for d in detections]
    
    # Get harvest records
    harvest_collection = get_collection("harvest_records")
    harvest_cursor = harvest_collection.find({"plot_id": plot_id}).sort("harvesting_date", -1).limit(5)
    harvests = await harvest_cursor.to_list(length=5)
    result["recent_harvests"] = [serialize_doc(h) for h in harvests]
    
    return result


@router.get("/stats/user/{user_id}")
async def get_plot_stats(
    user_id: int,
):
    """ดึงสถิติแปลงของผู้ใช้"""
    collection = get_collection("plots")
    
    total = await collection.count_documents({
        "user_id": user_id,
        "is_deleted": {"$ne": 1}
    })
    
    empty = await collection.count_documents({
        "user_id": user_id,
        "status": "0",
        "is_deleted": {"$ne": 1}
    })
    
    planted = await collection.count_documents({
        "user_id": user_id,
        "status": "1",
        "is_deleted": {"$ne": 1}
    })
    
    return {
        "user_id": user_id,
        "total_plots": total,
        "empty_plots": empty,
        "planted_plots": planted
    }


@router.post("/{id}/restore")
async def restore_plot(
    id: str,
):
    """กู้คืนแปลงที่ถูก soft delete"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"is_deleted": 0}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Plot not found or not deleted")
    
    return {"message": "Plot restored successfully"}

class PlantRequest(BaseModel):
    vegetable_name: str
    plant_date: str
    harvest_date: str
    quantity: str

class HarvestRequest(BaseModel):
    actual_harvest_date: str
    amount_kg: str
    income: str
    expense: str
    note: str

@router.post("/{id}/plant")
async def plant_vegetable(id: str, payload: PlantRequest):
    """ปลูกผักในแปลง"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    plot = await collection.find_one({"_id": ObjectId(id)})
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
        
    planting = {
        "plot_id": plot.get("plot_id", id),
        "plot_object_id": id,
        "vegetable_name": payload.vegetable_name,
        "plant_date": payload.plant_date,
        "harvest_date": payload.harvest_date,
        "quantity": payload.quantity,
        "status": 1, 
        "created_at": datetime.utcnow()
    }
    
    await get_collection("planting_veg").insert_one(planting)
    
    # Update plot status to planted (1)
    await collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": "1"}})
    
    return {"message": "Planted successfully"}

@router.post("/{id}/harvest")
async def harvest_vegetable(id: str, payload: HarvestRequest):
    """เก็บเกี่ยวผัก"""
    collection = get_collection("plots")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
        
    plot = await collection.find_one({"_id": ObjectId(id)})
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
        
    # Find active planting
    planting = await get_collection("planting_veg").find_one({
        "plot_object_id": id,
        "status": 1
    })
    
    harvest = {
        "plot_id": plot.get("plot_id", id),
        "plot_object_id": id,
        "actual_harvest_date": payload.actual_harvest_date,
        "amount_kg": payload.amount_kg,
        "income": payload.income,
        "expense": payload.expense,
        "note": payload.note,
        "vegetable_name": planting.get("vegetable_name") if planting else None,
        "plant_date": planting.get("plant_date") if planting else None,
        "quantity": planting.get("quantity") if planting else None,
        "created_at": datetime.utcnow()
    }
    
    await get_collection("harvest_records").insert_one(harvest)
    
    if planting:
        # Mark planting as harvested
        await get_collection("planting_veg").update_one(
            {"_id": planting["_id"]},
            {"$set": {"status": 2}}
        )
        
    # Check if there are other active plantings, if not set plot status to empty (0)
    active_plantings = await get_collection("planting_veg").count_documents({
        "plot_object_id": id,
        "status": 1
    })
    if active_plantings == 0:
        await collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": "0"}})
        
    return {"message": "Harvested successfully"}

@router.get("/{id}/history")
async def get_plot_history(id: str):
    """ประวัติการปลูก"""
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
        
    cursor = get_collection("harvest_records").find({"plot_object_id": id}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    
    # Data backfill for older records that might be missing quantity or dates
    planting_collection = get_collection("planting_veg")
    for doc in docs:
        if "quantity" not in doc or not doc.get("quantity"):
            # Try to guess the corresponding planting record
            plant_q = {"plot_object_id": id}
            if doc.get("vegetable_name"):
                plant_q["vegetable_name"] = doc.get("vegetable_name")
            # We assume it's one of the recently harvested for this plot
            planting_record = await planting_collection.find_one(plant_q, sort=[("created_at", -1)])
            if planting_record:
                if "quantity" not in doc or not doc.get("quantity"):
                    doc["quantity"] = planting_record.get("quantity")
                if "plant_date" not in doc or not doc.get("plant_date"):
                    doc["plant_date"] = planting_record.get("plant_date")

    return [serialize_doc(doc) for doc in docs]
