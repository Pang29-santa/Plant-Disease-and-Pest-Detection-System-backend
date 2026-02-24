"""
Authentication & OTP Routes
จัดการการเข้าสู่ระบบ และ OTP
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv

from database import get_collection

# โหลดค่าจาก .env
load_dotenv()

# OTP Configuration
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
from models import (
    LoginRequest, LoginResponse, TokenRefreshRequest, TokenResponse,
    UserRegister, OTPBase, User
)
from auth_utils import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from auth_utils import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from sequence_utils import get_next_sequence_value
from .utils import serialize_doc

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    เข้าสู่ระบบด้วย fullname และ password
    คืนค่า access_token และ refresh_token
    
    BYPASS MODE: ถ้า BYPASS_AUTH=true และใส่ credentials ตรงกับ .env
    จะ login สำเร็จทันทีโดยไม่ต้องเช็ค database
    """
    # ========== BYPASS MODE ==========
    bypass_auth = os.getenv("BYPASS_AUTH", "false").lower() == "true"
    bypass_username = os.getenv("BYPASS_ADMIN_USERNAME", "")
    bypass_password = os.getenv("BYPASS_ADMIN_PASSWORD", "")
    bypass_role = os.getenv("BYPASS_ADMIN_ROLE", "admin")
    
    if bypass_auth:
        if (credentials.fullname == bypass_username and 
            credentials.password == bypass_password):
            
            print(f"[BYPASS] Admin login: {bypass_username}")
            
            # สร้าง token สำหรับ bypass user
            token_data = {
                "sub": "bypass_admin_id",
                "email": f"{bypass_username}@bypass.local",
                "fullname": bypass_username,
                "role": bypass_role,
            }
            
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)
            
            return LoginResponse(
                success=True,
                message="Login successful (Bypass Mode)",
                access_token=access_token,
                refresh_token=refresh_token,
                user={
                    "user_id": "bypass_admin_id",
                    "fullname": bypass_username,
                    "email": f"{bypass_username}@bypass.local",
                    "role": bypass_role,
                    "status": "active"
                }
            )
    # ========== END BYPASS ==========
    
    collection = get_collection("users")
    
    # หา user จาก fullname
    user = await collection.find_one({"fullname": credentials.fullname})
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ตรวจสอบรหัสผ่าน
    stored_password = user.get("password", "")
    
    # ตรวจสอบว่าเป็น bcrypt hash หรือ plain text
    if len(stored_password) == 60 and stored_password.startswith("$2"):
        # เป็น bcrypt hash
        if not verify_password(credentials.password, stored_password):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # เป็น plain text (ข้อมูลเก่า)
        if stored_password != credentials.password:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # อัปเดตเป็น hash
        await collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"password": get_password_hash(stored_password)}}
        )
    
    # สร้าง token
    user_id = str(user.get("user_id") or user.get("_id"))
    token_data = {
        "sub": user_id,
        "email": user.get("email"),
        "fullname": user.get("fullname"),
        "role": user.get("role", "user"),
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # ลบ password ออกจาก response
    user_data = serialize_doc(user)
    user_data.pop("password", None)
    
    return LoginResponse(
        success=True,
        message="Login successful",
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_data
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: TokenRefreshRequest):
    """รีเฟรช access token ด้วย refresh token"""
    payload = decode_token(request.refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # สร้าง token ใหม่
    token_data = {
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "fullname": payload.get("fullname"),
        "role": payload.get("role", "user"),
    }
    
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


import shutil
from pathlib import Path
from fastapi import Form, File, UploadFile

@router.post("/register", response_model=LoginResponse)
async def register(
    fullname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: Optional[str] = Form(None),
    subdistricts_id: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """สมัครสมาชิกใหม่"""
    collection = get_collection("users")
    
    # ตรวจสอบ email ซ้ำ
    if email:
        existing = await collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # ตรวจสอบ phone ซ้ำ
    if phone:
        existing = await collection.find_one({"phone": phone})
        if existing:
            raise HTTPException(status_code=400, detail="Phone already registered")
            
    # Handle Image Upload
    image_path = None
    if image:
        try:
            # Create directory if not exists
            upload_dir = Path("static/images/users")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename: timestamp_filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # Sanitize filename if needed, but for now simple
            import re
            safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", image.filename)
            filename = f"{timestamp}_{safe_filename}"
            file_location = upload_dir / filename
            
            with file_location.open("wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
                
            image_path = f"static/images/users/{filename}"
        except Exception as e:
            # Just log and continue without image
            print(f"Image upload failed: {e}")
    
    # Hash password
    hashed_password = get_password_hash(password)
    
    user_data = {
        "fullname": fullname,
        "email": email,
        "password": hashed_password,
        "phone": phone,
        "subdistricts_id": subdistricts_id,
        "image_path": image_path,
        "status": "active",
        "role": "user",
        "user_id": await get_next_sequence_value("userid")
    }
    
    result = await collection.insert_one(user_data)
    new_user = await collection.find_one({"_id": result.inserted_id})
    
    # สร้าง token
    user_id = str(new_user.get("user_id") or new_user.get("_id"))
    token_data = {
        "sub": user_id,
        "email": new_user.get("email"),
        "fullname": new_user.get("fullname"),
        "role": new_user.get("role", "user"),
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # ลบ password ออกจาก response
    user_response = serialize_doc(new_user)
    user_response.pop("password", None)
    
    return LoginResponse(
        success=True,
        message="Registration successful",
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response
    )


@router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """ดึงข้อมูลผู้ใช้ปัจจุบัน"""
    collection = get_collection("users")
    
    # หา user จาก user_id - รองรับทั้ง int, string, และ ObjectId
    user_id = current_user["user_id"]
    query_conditions = []
    
    # ลองแปลงเป็น int ถ้าเป็นเลข
    try:
        query_conditions.append({"user_id": int(user_id)})
    except (ValueError, TypeError):
        pass
    
    # ลองแปลงเป็น ObjectId ถ้าเป็น ObjectId string ที่ถูกต้อง
    try:
        query_conditions.append({"_id": ObjectId(user_id)})
    except (InvalidId, ValueError, TypeError):
        pass
    
    # ถ้าไม่สามารถแปลงได้เลย ให้ลองหาด้วย fullname หรือ email (bypass mode)
    if not query_conditions:
        if current_user.get("fullname"):
            query_conditions.append({"fullname": current_user["fullname"]})
        if current_user.get("email"):
            query_conditions.append({"email": current_user["email"]})
    
    # ถ้ามี query conditions ให้ลองค้นหาในฐานข้อมูล
    if query_conditions:
        query = {"$or": query_conditions}
        user = await collection.find_one(query)
        if user:
            user_data = serialize_doc(user)
            user_data.pop("password", None)
            return user_data
    
    # Bypass mode: ถ้าไม่พบในฐานข้อมูล ให้คืนค่า current_user โดยตรง
    # (กรณี login สำเร็จแต่ user ไม่มีในฐานข้อมูลจริง)
    return {
        "user_id": current_user.get("user_id"),
        "fullname": current_user.get("fullname", "Unknown"),
        "email": current_user.get("email"),
        "role": current_user.get("role", "user"),
        "status": "active",
        "image_path": None
    }


@router.post("/otp/send")
async def send_otp(email: str):
    """ส่ง OTP ไปยัง email"""
    collection = get_collection("otp")
    
    # ตรวจสอบว่า email มีในระบบ
    users_collection = get_collection("users")
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # สร้าง OTP 6 หลัก
    import random
    otp_code = str(random.randint(100000, 999999))
    
    # ตั้ง expiration จาก .env
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(minutes=OTP_EXPIRE_MINUTES)
    
    otp_data = {
        "email": email,
        "otp_code": otp_code,
        "created_at": created_at,
        "expires_at": expires_at
    }
    
    # ลบ OTP เก่าของ email นี้
    await collection.delete_many({"email": email})
    
    # บันทึก OTP ใหม่
    result = await collection.insert_one(otp_data)
    
    # In production: ส่ง email จริง
    
    return {
        "message": "OTP sent successfully",
        "email": email,
        "otp_code": otp_code,  # เอาออกใน production
        "expires_at": expires_at
    }


@router.post("/otp/verify")
async def verify_otp(email: str, otp_code: str):
    """ตรวจสอบ OTP"""
    collection = get_collection("otp")
    
    otp_record = await collection.find_one({
        "email": email,
        "otp_code": otp_code
    })
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # ตรวจสอบ expiration
    if datetime.utcnow() > otp_record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # ลบ OTP ที่ใช้แล้ว
    await collection.delete_one({"_id": otp_record["_id"]})
    
    return {"message": "OTP verified successfully", "email": email}


@router.post("/password/reset")
async def reset_password(email: str, otp_code: str, new_password: str):
    """รีเซ็ตรหัสผ่านด้วย OTP"""
    # ตรวจสอบ OTP
    otp_collection = get_collection("otp")
    otp_record = await otp_collection.find_one({
        "email": email,
        "otp_code": otp_code
    })
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if datetime.utcnow() > otp_record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # อัปเดตรหัสผ่าน
    users_collection = get_collection("users")
    hashed_password = get_password_hash(new_password)
    result = await users_collection.update_one(
        {"email": email},
        {"$set": {"password": hashed_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # ลบ OTP ที่ใช้แล้ว
    await otp_collection.delete_one({"_id": otp_record["_id"]})
    
@router.get("/users")
async def get_all_users(
    skip: int = 0, 
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """ดึงรายชื่อผู้ใช้งานทั้งหมด (สำหรับ Admin)"""
    # ตรวจสอบสิทธิ์ (ถ้ามี check role logic)
    # logger.info(f"User {current_user['fullname']} requesting all users")
    
    collection = get_collection("users")
    cursor = collection.find({}).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    
    results = []
    for user in users:
        u_data = serialize_doc(user)
        u_data.pop("password", None)
        results.append(u_data)
        
    return {
        "success": True,
        "count": len(results),
        "data": results
    }
