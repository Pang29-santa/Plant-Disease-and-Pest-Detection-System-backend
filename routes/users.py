"""
User Routes (ผู้ใช้)
จัดการข้อมูลผู้ใช้งานระบบ
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, File, UploadFile
from bson import ObjectId

from database import get_collection
from models import User, UserBase, ChangePasswordRequest
from auth_utils import get_password_hash
from .utils import serialize_doc
from sequence_utils import get_next_sequence_value

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("")
async def get_users(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """ดึงข้อมูลผู้ใช้ทั้งหมด พร้อมค้นหา"""
    collection = get_collection("users")
    
    query = {}
    if search:
        query["$or"] = [
            {"fullname": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
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


@router.get("/{id}", response_model=User)
async def get_user(
    id: str,
):
    """ดึงข้อมูลผู้ใช้ตาม ID"""
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@router.get("/by-user-id/{user_id}", response_model=User)
async def get_user_by_user_id(
    user_id: int,
):
    """ดึงข้อมูลผู้ใช้ตาม user_id"""
    collection = get_collection("users")
    doc = await collection.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@router.get("/by-email/{email}", response_model=User)
async def get_user_by_email(
    email: str,
):
    """ดึงข้อมูลผู้ใช้ตาม email"""
    collection = get_collection("users")
    doc = await collection.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@router.post("", response_model=User)
async def create_user(
    user: UserBase,
):
    """สร้างผู้ใช้ใหม่"""
    collection = get_collection("users")
    
    # Check if email already exists
    if user.email:
        existing = await collection.find_one({"email": user.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Check if phone already exists
    if user.phone:
        existing = await collection.find_one({"phone": user.phone})
        if existing:
            raise HTTPException(status_code=400, detail="Phone already exists")
    
    userData = user.dict(exclude_unset=True)
    if "password" in userData and userData["password"]:
        userData["password"] = get_password_hash(userData["password"])
        
    # Auto-increment user_id
    if not userData.get("user_id"):
        userData["user_id"] = await get_next_sequence_value("userid")
        
    result = await collection.insert_one(userData)
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=User)
async def update_user(
    id: str,
    user: UserBase,
):
    """อัปเดตข้อมูลผู้ใช้"""
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # Check email uniqueness if changing
    if user.email:
        existing = await collection.find_one({
            "email": user.email,
            "_id": {"$ne": ObjectId(id)}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": user.dict(exclude_unset=True)}
    )
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_user(
    id: str,
):
    """ลบผู้ใช้ - พร้อมลบรูปโปรไฟล์"""
    import os
    from pathlib import Path
    
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # หาข้อมูลผู้ใช้ก่อนลบ (เพื่อเอา path รูป)
    user = await collection.find_one({"_id": ObjectId(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # ลบไฟล์รูปถ้ามี
    image_path = user.get("image_path")
    if image_path:
        try:
            # แปลง path เป็น absolute path
            file_path = Path(image_path)
            if not file_path.is_absolute():
                file_path = Path(".") / image_path
            
            if file_path.exists():
                os.remove(file_path)
                print(f"[INFO] Deleted image: {file_path}")
        except Exception as e:
            print(f"[WARN] Failed to delete image: {e}")
    
    # ลบข้อมูลผู้ใช้
    result = await collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}


@router.get("/{id}/plots")
async def get_user_plots(
    id: str,
):
    """ดึงข้อมูลแปลงของผู้ใช้"""
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    user = await collection.find_one({"_id": ObjectId(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user.get("user_id")
    
    plots_collection = get_collection("plots")
    cursor = plots_collection.find({
        "user_id": user_id,
        "is_deleted": {"$ne": "1"}
    })
    plots = await cursor.to_list(length=100)
    
    return {
        "user": serialize_doc(user),
        "plots": [serialize_doc(p) for p in plots]
    }


@router.get("/{id}/cctv")
async def get_user_cctv(
    id: str,
):
    """ดึงข้อมูลกล้อง CCTV ของผู้ใช้"""
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    user = await collection.find_one({"_id": ObjectId(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user.get("user_id")
    
    cctv_collection = get_collection("cctv")
    cursor = cctv_collection.find({"user_id": user_id})
    cctvs = await cursor.to_list(length=100)
    
    return {
        "user": serialize_doc(user),
        "cctv": [serialize_doc(c) for c in cctvs]
    }


@router.put("/{id}/password")
async def change_password(
    id: str,
    request: ChangePasswordRequest,
):
    """เปลี่ยนรหัสผ่าน"""
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    user = await collection.find_one({"_id": ObjectId(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify old password
    stored_password = user.get("password", "")
    
    # Check if hashed or plain text
    if len(stored_password) == 60 and stored_password.startswith("$2"):
        from auth_utils import verify_password
        if not verify_password(request.old_password, stored_password):
            raise HTTPException(status_code=401, detail="Incorrect old password")
    else:
        if stored_password != request.old_password:
            raise HTTPException(status_code=401, detail="Incorrect old password")
    
    # Update with hashed password
    hashed_password = get_password_hash(request.new_password)
    await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"password": hashed_password}}
    )
    
    return {"message": "Password changed successfully"}


@router.patch("/{id}/status")
async def update_user_status(
    id: str,
    status: str  # "active", "inactive", "suspended"
):
    """อัปเดตสถานะผู้ใช้"""
    if status not in ["active", "inactive", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    collection = get_collection("users")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"status": status}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return {
        "success": True,
        "message": f"User status updated to {status}",
        "data": serialize_doc(updated)
    }


@router.post("/upload")
async def upload_user_image(
    file: UploadFile = File(...)
):
    """อัปโหลดรูปโปรไฟล์ผู้ใช้"""
    import os
    import uuid
    from pathlib import Path
    
    # Create directory if not exists
    upload_dir = Path("uploads/users")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = upload_dir / file_name
    
    # Save file
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "success": True,
        "image_path": str(file_path).replace("\\", "/")
    }
