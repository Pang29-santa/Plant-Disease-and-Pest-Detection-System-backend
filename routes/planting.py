"""
Planting & Harvest Routes (การปลูกและการเก็บเกี่ยว)
จัดการข้อมูลการปลูกผักและบันทึกการเก็บเกี่ยว
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from database import get_collection
from models import PlantingVeg, PlantingVegBase, HarvestRecord, HarvestRecordBase
from .utils import serialize_doc

router = APIRouter(prefix="/api", tags=["Planting"])


# ==================== Planting Routes ====================

@router.get("/planting-veg", response_model=List[PlantingVeg])
async def get_planting_veg(
    user_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    vegetable_id: Optional[int] = None,
    status: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """ดึงข้อมูลการปลูกผัก"""
    collection = get_collection("planting_veg")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if plot_id:
        query["plot_id"] = plot_id
    if vegetable_id:
        query["vegetable_id"] = vegetable_id
    if status is not None:
        query["status"] = status
    
    cursor = collection.find(query).sort("planting_date", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/planting-veg/{id}", response_model=PlantingVeg)
async def get_planting_veg_by_id(
    id: str,
):
    """ดึงข้อมูลการปลูกตาม MongoDB ID"""
    collection = get_collection("planting_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Planting record not found")
    return serialize_doc(doc)


@router.get("/planting-veg/by-planting-id/{planting_id}", response_model=PlantingVeg)
async def get_planting_veg_by_planting_id(
    planting_id: int,
):
    """ดึงข้อมูลการปลูกตาม planting_id"""
    collection = get_collection("planting_veg")
    doc = await collection.find_one({"planting_id": planting_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Planting record not found")
    return serialize_doc(doc)


@router.post("/planting-veg", response_model=PlantingVeg)
async def create_planting_veg(
    data: PlantingVegBase,
):
    """เพิ่มข้อมูลการปลูก"""
    collection = get_collection("planting_veg")
    
    # Update plot status to planted
    if data.plot_id:
        plots_collection = get_collection("plots")
        await plots_collection.update_one(
            {"plot_id": data.plot_id},
            {"$set": {"status": "1"}}
        )
    
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/planting-veg/{id}", response_model=PlantingVeg)
async def update_planting_veg(
    id: str,
    data: PlantingVegBase,
):
    """อัปเดตข้อมูลการปลูก"""
    collection = get_collection("planting_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = data.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Planting record not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/planting-veg/{id}")
async def delete_planting_veg(
    id: str,
):
    """ลบข้อมูลการปลูก"""
    collection = get_collection("planting_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # Get planting data first to update plot status
    planting = await collection.find_one({"_id": ObjectId(id)})
    if planting:
        plot_id = planting.get("plot_id")
        if plot_id:
            plots_collection = get_collection("plots")
            await plots_collection.update_one(
                {"plot_id": plot_id},
                {"$set": {"status": "0"}}
            )
    
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Planting record not found")
    return {"message": "Planting record deleted successfully"}


@router.post("/planting-veg/{id}/complete")
async def complete_planting(
    id: str,
    harvest_date: str,
    actual_quantity: float,
    income: Optional[int] = None,
    cost: Optional[int] = None,
    notes: Optional[str] = None,
):
    """บันทึกการเก็บเกี่ยวและปิดการปลูก"""
    collection = get_collection("planting_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    planting = await collection.find_one({"_id": ObjectId(id)})
    if not planting:
        raise HTTPException(status_code=404, detail="Planting record not found")
    
    # Update planting status
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "status": 2,  # เก็บเกี่ยวแล้ว
            "harvesting_date": harvest_date
        }}
    )
    
    # Update plot status to empty
    plot_id = planting.get("plot_id")
    if plot_id:
        plots_collection = get_collection("plots")
        await plots_collection.update_one(
            {"plot_id": plot_id},
            {"$set": {"status": "0"}}
        )
    
    # Create harvest record
    harvest_collection = get_collection("harvest_records")
    harvest_data = {
        "harvest_id": await get_next_harvest_id(),
        "user_id": planting.get("user_id"),
        "vegetable_id": planting.get("vegetable_id"),
        "planting_id": planting.get("planting_id"),
        "plot_id": plot_id,
        "planting_date": planting.get("planting_date"),
        "harvesting_date": harvest_date,
        "quantity": actual_quantity,
        "income": income,
        "cost": cost,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat()
    }
    await harvest_collection.insert_one(harvest_data)
    
    return {"message": "Planting completed and harvest recorded"}


async def get_next_harvest_id() -> int:
    """Get next harvest_id"""
    collection = get_collection("harvest_records")
    last_doc = await collection.find_one(sort=[("harvest_id", -1)])
    if last_doc and "harvest_id" in last_doc:
        return last_doc["harvest_id"] + 1
    return 1


@router.get("/planting-veg/{id}/details")
async def get_planting_details(
    id: str,
):
    """ดึงข้อมูลการปลูกพร้อมรายละเอียดที่เกี่ยวข้อง"""
    collection = get_collection("planting_veg")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    planting = await collection.find_one({"_id": ObjectId(id)})
    if not planting:
        raise HTTPException(status_code=404, detail="Planting record not found")
    
    result = {"planting": serialize_doc(planting)}
    
    # Get vegetable info
    if planting.get("vegetable_id"):
        veg_collection = get_collection("vegetable")
        veg = await veg_collection.find_one({"vegetable_id": planting.get("vegetable_id")})
        if veg:
            result["vegetable"] = serialize_doc(veg)
    
    # Get plot info
    if planting.get("plot_id"):
        plots_collection = get_collection("plots")
        plot = await plots_collection.find_one({"plot_id": planting.get("plot_id")})
        if plot:
            result["plot"] = serialize_doc(plot)
    
    # Get harvest records
    harvest_collection = get_collection("harvest_records")
    harvest_cursor = harvest_collection.find({"planting_id": planting.get("planting_id")})
    harvests = await harvest_cursor.to_list(length=10)
    result["harvests"] = [serialize_doc(h) for h in harvests]
    
    return result


# ==================== Harvest Routes ====================

@router.get("/harvest-records", response_model=List[HarvestRecord])
async def get_harvest_records(
    user_id: Optional[int] = None,
    vegetable_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    planting_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """ดึงข้อมูลการเก็บเกี่ยว"""
    collection = get_collection("harvest_records")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if vegetable_id:
        query["vegetable_id"] = vegetable_id
    if plot_id:
        query["plot_id"] = plot_id
    if planting_id:
        query["planting_id"] = planting_id
    
    cursor = collection.find(query).sort("harvesting_date", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [serialize_doc(doc) for doc in docs]


@router.get("/harvest-records/{id}", response_model=HarvestRecord)
async def get_harvest_record_by_id(
    id: str,
):
    """ดึงข้อมูลการเก็บเกี่ยวตาม MongoDB ID"""
    collection = get_collection("harvest_records")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Harvest record not found")
    return serialize_doc(doc)


@router.get("/harvest-records/by-harvest-id/{harvest_id}", response_model=HarvestRecord)
async def get_harvest_record_by_harvest_id(
    harvest_id: int,
):
    """ดึงข้อมูลการเก็บเกี่ยวตาม harvest_id"""
    collection = get_collection("harvest_records")
    doc = await collection.find_one({"harvest_id": harvest_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Harvest record not found")
    return serialize_doc(doc)


@router.post("/harvest-records", response_model=HarvestRecord)
async def create_harvest_record(
    data: HarvestRecordBase,
):
    """เพิ่มข้อมูลการเก็บเกี่ยว"""
    collection = get_collection("harvest_records")
    
    # Set harvest_id and created_at
    if not data.harvest_id:
        data.harvest_id = await get_next_harvest_id()
    if not data.created_at:
        data.created_at = datetime.utcnow().isoformat()
    
    result = await collection.insert_one(data.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/harvest-records/{id}", response_model=HarvestRecord)
async def update_harvest_record(
    id: str,
    data: HarvestRecordBase,
):
    """อัปเดตข้อมูลการเก็บเกี่ยว"""
    collection = get_collection("harvest_records")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = data.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Harvest record not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/harvest-records/{id}")
async def delete_harvest_record(
    id: str,
):
    """ลบข้อมูลการเก็บเกี่ยว"""
    collection = get_collection("harvest_records")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Harvest record not found")
    return {"message": "Harvest record deleted successfully"}


@router.get("/harvest-records/stats/user/{user_id}")
async def get_harvest_stats(
    user_id: int,
):
    """ดึงสถิติการเก็บเกี่ยวของผู้ใช้"""
    collection = get_collection("harvest_records")
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$vegetable_id",
            "total_quantity": {"$sum": "$quantity"},
            "total_income": {"$sum": "$income"},
            "total_cost": {"$sum": "$cost"},
            "count": {"$sum": 1}
        }}
    ]
    
    cursor = collection.aggregate(pipeline)
    stats = await cursor.to_list(length=100)
    
    # Get vegetable names
    veg_collection = get_collection("vegetable")
    result = []
    for stat in stats:
        veg_id = stat.get("_id")
        veg = await veg_collection.find_one({"vegetable_id": veg_id})
        result.append({
            "vegetable_id": veg_id,
            "vegetable_name": veg.get("thai_name", "Unknown") if veg else "Unknown",
            "total_quantity": stat.get("total_quantity", 0),
            "total_income": stat.get("total_income", 0),
            "total_cost": stat.get("total_cost", 0),
            "profit": (stat.get("total_income", 0) or 0) - (stat.get("total_cost", 0) or 0),
            "count": stat.get("count", 0)
        })
    
    return {"user_id": user_id, "stats": result}


@router.get("/harvest-records/summary/user/{user_id}")
async def get_harvest_summary(
    user_id: int,
):
    """ดึงสรุปการเก็บเกี่ยวของผู้ใช้"""
    collection = get_collection("harvest_records")
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_records": {"$sum": 1},
            "total_quantity": {"$sum": "$quantity"},
            "total_income": {"$sum": "$income"},
            "total_cost": {"$sum": "$cost"},
            "avg_quantity": {"$avg": "$quantity"}
        }}
    ]
    
    cursor = collection.aggregate(pipeline)
    summary = await cursor.to_list(length=1)
    
    if summary:
        data = summary[0]
        total_income = data.get("total_income", 0) or 0
        total_cost = data.get("total_cost", 0) or 0
        return {
            "user_id": user_id,
            "total_records": data.get("total_records", 0),
            "total_quantity": data.get("total_quantity", 0),
            "total_income": total_income,
            "total_cost": total_cost,
            "total_profit": total_income - total_cost,
            "average_quantity_per_harvest": round(data.get("avg_quantity", 0) or 0, 2)
        }
    
    return {
        "user_id": user_id,
        "total_records": 0,
        "total_quantity": 0,
        "total_income": 0,
        "total_cost": 0,
        "total_profit": 0,
        "average_quantity_per_harvest": 0
    }
