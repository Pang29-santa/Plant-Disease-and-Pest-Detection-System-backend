"""
Telegram Routes
จัดการการเชื่อมต่อ Telegram และส่งข้อความแจ้งเตือน
"""

import os
import random
import string
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
import requests

from database import get_collection
from models import TelegramConnection, TelegramConnectionBase
from .utils import serialize_doc

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])

# โหลดค่าจาก environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def generate_connection_code(length=6):
    """สร้างรหัสยืนยันแบบสุ่ม"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def send_telegram_message(chat_id: str, message: str, parse_mode: str = "Markdown", 
                          reply_markup: dict = None) -> bool:
    """ส่งข้อความไปยัง Telegram จริง
    
    Args:
        chat_id: Telegram chat ID
        message: ข้อความที่จะส่ง
        parse_mode: "Markdown" หรือ "HTML" (default: Markdown สำหรับลิงก์ที่กดได้)
        reply_markup: Inline keyboard หรือ other reply markup (optional)
    """
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  Warning: TELEGRAM_BOT_TOKEN not set")
        return False
    
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        
        # 🔍 DEBUG: แสดงข้อความที่จะส่ง
        print(f"\n{'='*60}")
        print(f"📤 [TELEGRAM SEND MESSAGE]")
        print(f"   Chat ID: {chat_id}")
        print(f"   Parse Mode: {parse_mode}")
        print(f"   Message length: {len(message)} chars")
        print(f"\n📝 Message content:\n{message}")
        print(f"{'='*60}\n")
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        
        # เพิ่ม reply_markup ถ้ามี (เช่น inline keyboard)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Telegram message sent successfully")
            return True
        else:
            error_desc = result.get('description', 'Unknown error')
            print(f"❌ Telegram API Error: {error_desc}")
            
            # ถ้า Markdown ไม่สำเร็จ ลองส่งแบบไม่มี parse_mode
            if parse_mode != "":
                print(f"⚠️ Retrying with empty parse_mode...")
                payload["parse_mode"] = ""
                response = requests.post(url, json=payload, timeout=10)
                result = response.json()
                if result.get("ok"):
                    print(f"✅ Message sent without parse_mode")
                    return True
                else:
                    print(f"❌ Still failed: {result.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Exception sending Telegram message: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_telegram_photo_with_caption(chat_id: str, photo_url: str, caption: str, parse_mode: str = "Markdown", 
                                     reply_markup: dict = None) -> bool:
    """ส่งรูปภาพพร้อมข้อความไปยัง Telegram
    
    รองรับทั้ง:
    - URL แบบเต็ม (https://...)
    - Path แบบ local (/static/... หรือ static/...) -> อ่านไฟล์และส่งโดยตรง
    
    Args:
        chat_id: Telegram chat ID
        photo_url: URL หรือ path ของรูปภาพ
        caption: ข้อความประกอบรูป
        parse_mode: "Markdown" หรือ "HTML" (default: Markdown)
        reply_markup: Inline keyboard หรือ other reply markup (optional)
    """
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  Warning: TELEGRAM_BOT_TOKEN not set")
        return False
    
    print(f"🔍  [DEBUG] send_telegram_photo_with_caption - chat_id: {chat_id}, photo_url: {photo_url}")
    
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        
        # ตรวจสอบว่าเป็น URL แบบเต็มหรือ path แบบ local
        if photo_url.startswith('http://') or photo_url.startswith('https://'):
            # เป็น URL แบบเต็ม - ส่งผ่าน JSON
            print(f"🔍  [DEBUG] Sending photo via URL: {photo_url}")
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            response = requests.post(url, json=payload, timeout=10)
        else:
            # เป็น path แบบ local - อ่านไฟล์และส่งผ่าน multipart/form-data
            print(f"🔍  [DEBUG] Sending photo via local file: {photo_url}")
            
            # แปลง path ให้เป็น absolute path
            if photo_url.startswith('/'):
                photo_path = photo_url.lstrip('/')
            else:
                photo_path = photo_url
            
            # ลองหาไฟล์ในโฟลเดอร์ต่างๆ
            possible_paths = [
                Path(photo_path),
                Path("static") / photo_path,
                Path("static/images") / photo_path.replace("images/", ""),
            ]
            
            file_path = None
            for p in possible_paths:
                print(f"🔍  [DEBUG] Checking path: {p} (exists: {p.exists()})")
                if p.exists():
                    file_path = p
                    break
            
            if not file_path:
                print(f"❌  [DEBUG] Image file not found: {photo_url}")
                # ถ้าไม่พบไฟล์ ส่งแค่ข้อความแทน
                return send_telegram_message(chat_id, caption, parse_mode)
            
            print(f"✅  [DEBUG] Found file at: {file_path}")
            
            # ส่งไฟล์ผ่าน multipart/form-data
            with open(file_path, 'rb') as f:
                files = {'photo': f}
                data = {
                    'chat_id': chat_id,
                    'caption': caption,
                    'parse_mode': parse_mode
                }
                if reply_markup:
                    import json
                    data['reply_markup'] = json.dumps(reply_markup)
                response = requests.post(url, data=data, files=files, timeout=30)
        
        result = response.json()
        print(f"🔍  [DEBUG] Telegram API response: {result}")
        
        if result.get("ok"):
            print("✅  [DEBUG] Photo sent successfully")
            return True
        else:
            print(f"❌  Telegram API Error (sendPhoto): {result.get('description')}")
            # ถ้าส่งรูปไม่สำเร็จ ลองส่งแค่ข้อความพร้อมปุ่ม
            return send_telegram_message(chat_id, caption, parse_mode, reply_markup=reply_markup)
    except Exception as e:
        print(f"❌  Error sending Telegram photo: {e}")
        # ถ้ามี error ลองส่งแค่ข้อความพร้อมปุ่ม
        return send_telegram_message(chat_id, caption, parse_mode, reply_markup=reply_markup)


@router.get("", response_model=List[TelegramConnection])
async def get_telegram_connections(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """ดึงข้อมูลการเชื่อมต่อ Telegram ทั้งหมด"""
    collection = get_collection("telegram_connections")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status
    
    cursor = collection.find(query)
    docs = await cursor.to_list(length=100)
    return [serialize_doc(doc) for doc in docs]


@router.get("/{id}", response_model=TelegramConnection)
async def get_telegram_connection(
    id: str,
):
    """ดึงข้อมูลการเชื่อมต่อ Telegram ตาม ID"""
    collection = get_collection("telegram_connections")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    doc = await collection.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    return serialize_doc(doc)


@router.get("/user/{user_id}")
async def get_telegram_by_user(
    user_id: str,
):
    """ดึงข้อมูลการเชื่อมต่อ Telegram ตาม user_id"""
    collection = get_collection("telegram_connections")
    
    print(f"[DEBUG] Getting Telegram connections for user_id: {user_id}")
    
    # รองรับทั้ง user_id (int) และ _id (ObjectId string)
    query_conditions = []
    
    # ลองแปลงเป็น int ถ้าเป็นเลข
    try:
        query_conditions.append({"user_id": int(user_id)})
    except (ValueError, TypeError):
        pass
    
    # ใช้ string เดิม (สำหรับ ObjectId)
    query_conditions.append({"user_id": user_id})
    
    print(f"[DEBUG] Query conditions: {query_conditions}")
    
    # ค้นหาด้วยเงื่อนไข OR
    cursor = collection.find({"$or": query_conditions})
    docs = await cursor.to_list(length=100)
    
    print(f"[DEBUG] Found {len(docs)} connections")
    
    return [serialize_doc(doc) for doc in docs]


@router.post("", response_model=TelegramConnection)
async def create_telegram_connection(
    connection: TelegramConnectionBase,
):
    """สร้างการเชื่อมต่อ Telegram ใหม่"""
    collection = get_collection("telegram_connections")
    
    # Check if user already has a connection
    existing = await collection.find_one({"user_id": connection.user_id})
    if existing:
        raise HTTPException(status_code=400, detail="User already has a Telegram connection")
    
    result = await collection.insert_one(connection.dict(exclude_unset=True))
    new_doc = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(new_doc)


@router.put("/{id}", response_model=TelegramConnection)
async def update_telegram_connection(
    id: str,
    connection: TelegramConnectionBase,
):
    """อัปเดตข้อมูลการเชื่อมต่อ Telegram"""
    collection = get_collection("telegram_connections")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    update_data = connection.dict(exclude_unset=True)
    result = await collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    
    updated = await collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.delete("/{id}")
async def delete_telegram_connection(
    id: str,
):
    """ลบการเชื่อมต่อ Telegram และแจ้งเตือนผู้ใช้"""
    collection = get_collection("telegram_connections")
    users_collection = get_collection("users")
    
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # ค้นหาการเชื่อมต่อก่อนลบ เพื่อส่งข้อความแจ้งเตือน
    connection = await collection.find_one({"_id": ObjectId(id)})
    if not connection:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    
    chat_id = connection.get("chat_id")
    user_id = connection.get("user_id")
    
    # ส่งข้อความแจ้งเตือนการยกเลิกการเชื่อมต่อ
    if chat_id:
        disconnect_message = f"""*❌ ยกเลิกการเชื่อมต่อ*

บัญชีของคุณถูกยกเลิกการเชื่อมต่อกับระบบ Vegetable Project แล้ว
คุณจะไม่ได้รับการแจ้งเตือนอีกต่อไป

หากต้องการเชื่อมต่อใหม่ กรุณาเข้าไปที่หน้า Telegram ในระบบ

ขอบคุณที่ใช้บริการ 🌱"""
        send_telegram_message(chat_id, disconnect_message)
    
    # ลบการเชื่อมต่อ
    result = await collection.delete_one({"_id": ObjectId(id)})
    
    # อัปเดตข้อมูลผู้ใช้ให้ลบ telegram_chat_id
    if user_id:
        await users_collection.update_one(
            {"_id": ObjectId(user_id)} if ObjectId.is_valid(user_id) else {"user_id": user_id},
            {
                "$set": {
                    "telegram_chat_id": None,
                    "telegram_connected_at": None,
                    "telegram_connection_code": None,
                    "telegram_code_expires": None
                }
            }
        )
    
    return {"message": "Telegram connection deleted successfully"}


@router.post("/request-code")
async def request_connection_code(
    data: dict,
):
    """ขอรหัสยืนยันใหม่สำหรับเชื่อมต่อ Telegram"""
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    # สร้างรหัสยืนยันใหม่
    code = generate_connection_code()
    
    # บันทึกรหัสลงฐานข้อมูล (หรืออัปเดตถ้ามีอยู่แล้ว)
    users_collection = get_collection("users")
    
    # สร้าง query ที่รองรับทั้ง user_id (int) และ _id (ObjectId)
    query_conditions = []
    
    # ลองแปลงเป็น int ถ้าเป็นเลข
    try:
        query_conditions.append({"user_id": int(user_id)})
    except (ValueError, TypeError):
        pass
    
    # ลองแปลงเป็น ObjectId ถ้าเป็น ObjectId string
    try:
        query_conditions.append({"_id": ObjectId(user_id)})
    except (Exception):
        pass
    
    if not query_conditions:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    # ค้นหา user ก่อน
    user = None
    for query in query_conditions:
        user = await users_collection.find_one(query)
        if user:
            break
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # อัปเดตรหัสยืนยัน
    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "telegram_connection_code": code,
                "telegram_connection_code": code,
                "telegram_code_expires": datetime.utcnow() + timedelta(minutes=10),
                "telegram_chat_id": None,
                "telegram_connected_at": None
            }
        }
    )
    
    # ส่งรหัสไปยัง Telegram ถ้ามี TELEGRAM_CHAT_ID ใน .env
    if TELEGRAM_CHAT_ID:
        message = f"""*🔐 รหัสยืนยันการเชื่อมต่อ*

รหัสของคุณ: `{code}`

กรุณากรอกรหัสนี้ในหน้าเว็บเพื่อเชื่อมต่อบัญชีของคุณ
⏰ รหัสนี้จะหมดอายุใน 10 นาที"""
        send_telegram_message(TELEGRAM_CHAT_ID, message)
    
    return {
        "success": True,
        "message": "Connection code generated",
        "code": code,  # ส่งกลับเพื่อ debug (ใน production อาจไม่ส่ง)
        "expires_in": "10 minutes"
    }


@router.post("/verify-code")
async def verify_connection_code(
    data: dict,
):
    """ยืนยันรหัสเชื่อมต่อ Telegram"""
    user_id = data.get("user_id")
    code = data.get("code", "").strip().upper()
    
    print(f"[DEBUG] Verify code: user_id={user_id}, code={code}")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    
    chat_id = None
    temp_code_doc = None  # กำหนดค่าเริ่มต้น
    
    # วิธีที่ 1: ตรวจสอบจาก temp_codes (ที่ Bot สร้างตอน /start)
    try:
        temp_codes_collection = get_collection("telegram_temp_codes")
        temp_code_doc = await temp_codes_collection.find_one({
            "verification_code": code,
            "expires_at": {"$gt": datetime.utcnow()},
            "verified": False
        })
        
        if temp_code_doc:
            print(f"[DEBUG] Found in temp_codes: {temp_code_doc}")
            chat_id = temp_code_doc.get("chat_id")
    except Exception as e:
        print(f"[DEBUG] Error checking temp_codes: {e}")
    
    # วิธีที่ 2: ถ้าไม่เจอใน temp_codes ตรวจสอบใน users (กรณี request code จากหน้าเว็บ)
    if not chat_id:
        try:
            users_collection = get_collection("users")
            
            # สร้าง query ที่รองรับทั้ง user_id (int) และ _id (ObjectId)
            query_conditions = []
            
            # ลองแปลงเป็น int ถ้าเป็นเลข
            try:
                query_conditions.append({"user_id": int(user_id)})
            except (ValueError, TypeError):
                pass
            
            # ลองแปลงเป็น ObjectId ถ้าเป็น ObjectId string
            try:
                query_conditions.append({"_id": ObjectId(user_id)})
            except (Exception):
                pass
            
            user = None
            for query in query_conditions:
                user = await users_collection.find_one(query)
                if user:
                    break
            
            if user:
                stored_code = user.get("telegram_connection_code", "").upper()
                code_expires = user.get("telegram_code_expires")
                
                print(f"[DEBUG] User found. stored_code={stored_code}, expires={code_expires}")
                
                if stored_code and stored_code == code:
                    if code_expires and datetime.utcnow() > code_expires:
                        return {"success": False, "message": "รหัสยืนยันหมดอายุแล้ว กรุณาขอรหัสใหม่"}
                    
                    chat_id = user.get("telegram_chat_id") or TELEGRAM_CHAT_ID
                    user_id = str(user["_id"])  # ใช้ _id เป็นหลัก
                    print(f"[DEBUG] Using chat_id from user: {chat_id}, user_id={user_id}")
                else:
                    print(f"[DEBUG] Code mismatch. Input: {code}, Stored: {stored_code}")
            else:
                print(f"[DEBUG] User not found: {user_id}")
        except Exception as e:
            print(f"[DEBUG] Error checking users: {e}")
    
    if not chat_id:
        print(f"[DEBUG] No chat_id found")
        return {"success": False, "message": "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ"}
    
    # รหัสถูกต้อง - สร้างการเชื่อมต่อ
    try:
        telegram_collection = get_collection("telegram_connections")
        users_collection = get_collection("users")
        
        # ดึง _id ของ user จาก database
        user_doc = None
        
        # กรณีพบใน temp_codes ให้ใช้ user_id จาก temp_codes (ถ้ามี)
        if temp_code_doc and temp_code_doc.get("user_id"):
            temp_user_id = temp_code_doc.get("user_id")
            print(f"[DEBUG] Trying to find user with temp_code user_id: {temp_user_id}")
            try:
                user_doc = await users_collection.find_one({"user_id": int(temp_user_id)})
            except:
                pass
            if not user_doc:
                try:
                    user_doc = await users_collection.find_one({"_id": ObjectId(str(temp_user_id))})
                except:
                    pass
        
        # ถ้ายังไม่เจอ ลองหาด้วย user_id จาก request
        if not user_doc:
            try:
                user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
            except:
                pass
        
        if not user_doc:
            # ลองหาด้วย user_id ถ้าเป็น int
            try:
                user_doc = await users_collection.find_one({"user_id": int(user_id)})
            except:
                pass
        
        # ถ้ายังไม่เจอ user และเป็น bypass mode ให้ใช้ user_id จาก temp_codes หรือสร้าง connection โดยตรง
        if not user_doc and temp_code_doc and temp_code_doc.get("user_id"):
            real_user_id = temp_code_doc.get("user_id")
            print(f"[DEBUG] Using user_id from temp_codes for bypass mode: {real_user_id}")
        elif not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prefer integer user_id if available, otherwise use ObjectId string
        if user_doc:
            real_user_id = user_doc.get("user_id")
            if not real_user_id:
                real_user_id = str(user_doc["_id"])
        else:
            # Bypass mode - use user_id from temp_codes
            real_user_id = temp_code_doc.get("user_id")
        
        # Current time in UTC+7
        now_th = datetime.utcnow() + timedelta(hours=7)
        
        connection_data = {
            "user_id": real_user_id,
            "chat_id": chat_id,
            "status": "active",
            "connection_code": code,
            "connected_at": now_th,
            "created_at": now_th,
            "updated_at": now_th
        }
        
        # อัปเดตหรือสร้างการเชื่อมต่อใหม่
        print(f"[DEBUG] Saving connection: {connection_data}")
        existing = await telegram_collection.find_one({"user_id": real_user_id})
        if existing:
            print(f"[DEBUG] Updating existing connection: {existing['_id']}")
            await telegram_collection.update_one(
                {"user_id": real_user_id},
                {"$set": connection_data}
            )
            connection_id = str(existing["_id"])
        else:
            print(f"[DEBUG] Creating new connection")
            result = await telegram_collection.insert_one(connection_data)
            connection_id = str(result.inserted_id)
            print(f"[DEBUG] New connection created: {connection_id}")
        
        # Update user info - ensure we use the correct _id for the update query (ถ้ามี user_doc)
        if user_doc:
            await users_collection.update_one(
                {"_id": user_doc["_id"]},
                {
                    "$set": {
                        "telegram_chat_id": chat_id,
                        "telegram_connected_at": now_th,
                        "telegram_connection_code": None,
                        "telegram_code_expires": None
                    }
                }
            )
        
        # อัปเดต temp_codes ว่า verified แล้ว (ถ้ามี)
        if temp_code_doc:
            await temp_codes_collection.update_one(
                {"_id": temp_code_doc["_id"]},
                {"$set": {"verified": True, "user_id": real_user_id}}
            )
        
        # ส่งข้อความยืนยันไปยัง Telegram
        user_fullname = user_doc.get('fullname', 'ผู้ใช้') if user_doc else 'ผู้ใช้'
        welcome_message = f"""*✅ เชื่อมต่อสำเร็จ!*

สวัสดีคุณ *{user_fullname}*!
บัญชีของคุณเชื่อมต่อกับระบบ Vegetable Project แล้ว
คุณจะได้รับการแจ้งเตือนเมื่อ:
• ตรวจพบโรคพืช
• ตรวจพบศัตรูพืช
• มีการแจ้งเตือนสำคัญจากระบบ

ขอบคุณที่ใช้บริการ 🌱"""
        send_telegram_message(chat_id, welcome_message)
        
        print(f"[DEBUG] Connection successful: connection_id={connection_id}")
        
        return {
            "success": True,
            "message": "เชื่อมต่อ Telegram สำเร็จ",
            "connection": {
                "_id": connection_id,
                "user_id": real_user_id,
                "chat_id": chat_id,
                "status": "active"
            }
        }
    except Exception as e:
        print(f"[DEBUG] Error creating connection: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")


@router.post("/{id}/send-test")
async def send_test_message(
    id: str,
):
    """ส่งข้อความทดสอบไปยัง Telegram"""
    collection = get_collection("telegram_connections")
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    connection = await collection.find_one({"_id": ObjectId(id)})
    if not connection:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    
    chat_id = connection.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="No chat_id found for this connection")
    
    # ส่งข้อความจริงผ่าน Telegram API
    message = f"""*🧪 ข้อความทดสอบ*

นี่คือข้อความทดสอบจากระบบ Vegetable Project
หากคุณเห็นข้อความนี้ แสดงว่าการเชื่อมต่อทำงานปกติ ✅

_ส่งเมื่อ: {(datetime.utcnow() + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')} (UTC+7)_"""
    
    success = send_telegram_message(chat_id, message)
    
    if success:
        return {
            "connection_id": id,
            "chat_id": chat_id,
            "status": "sent",
            "message": "Test message sent successfully"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")


@router.post("/send-notification")
async def send_notification(
    data: dict,
):
    """ส่งการแจ้งเตือนไปยัง Telegram ของผู้ใช้"""
    user_id = data.get("user_id")
    message_text = data.get("message")
    
    if not user_id or not message_text:
        raise HTTPException(status_code=400, detail="user_id and message are required")
    
    collection = get_collection("telegram_connections")
    
    # Try query with both int and string/ObjectId
    query_conditions = []
    
    # Try int
    try:
        query_conditions.append({
            "user_id": int(user_id),
            "status": "active"
        })
    except (ValueError, TypeError):
        pass

    # Try string/ObjectId
    query_conditions.append({
        "user_id": user_id,
        "status": "active"
    })
    
    connection = None
    for query in query_conditions:
        connection = await collection.find_one(query)
        if connection:
            break
    
    if not connection:
        raise HTTPException(status_code=404, detail="No active Telegram connection found")
    
    chat_id = connection.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="No chat_id found")
    
    # ส่งข้อความจริง
    success = send_telegram_message(chat_id, message_text)
    
    if success:
        return {
            "user_id": user_id,
            "chat_id": chat_id,
            "status": "sent",
            "message": message_text
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to send notification")


@router.post("/broadcast")
async def broadcast_message(
    data: dict,
):
    """ส่งข้อความ broadcast ไปยังผู้ใช้ทั้งหมดที่เชื่อมต่อ Telegram"""
    message_text = data.get("message")
    
    if not message_text:
        raise HTTPException(status_code=400, detail="message is required")
    
    collection = get_collection("telegram_connections")
    cursor = collection.find({"status": "active"})
    connections = await cursor.to_list(length=1000)
    
    sent_count = 0
    failed_count = 0
    
    for conn in connections:
        chat_id = conn.get("chat_id")
        if chat_id:
            success = send_telegram_message(chat_id, message_text)
            if success:
                sent_count += 1
            else:
                failed_count += 1
    
    return {
        "total": len(connections),
        "sent": sent_count,
        "failed": failed_count,
        "message": message_text
    }
