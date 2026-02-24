"""
AI Detection Routes
API สำหรับวิเคราะห์รูปภาพโรคพืชและศัตรูพืชด้วย Kimi AI และ TensorFlow
"""

import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import html
import socket
import asyncio

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

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from bson import ObjectId

from database import get_collection
from utils.file_handler import save_image, delete_image, get_image_url
from services.kimi_ai import (
    analyze_plant_health, 
    chat_with_assistant
)
from services.tf_model_service import (
    analyze_with_tensorflow,
    get_tf_model_service,
)
from auth_utils import get_current_user_optional
from routes.telegram import send_telegram_message, send_telegram_photo_with_caption

router = APIRouter(prefix="/api/ai", tags=["AI Detection"])

# Temporary upload directory for analysis
TEMP_DIR = Path("static/img/temp")


@router.get("/health")
async def ai_health_check():
    """ตรวจสอบสถานะการเชื่อมต่อ AI Services"""
    import requests
    
    results = {
        "kimi": {"available": False, "error": None},
        "openai": {"available": False, "error": None},
        "tensorflow": {"available": False, "error": None, "model_info": None}
    }
    
    # Test Kimi
    try:
        from services.kimi_ai import get_kimi_service
        kimi = get_kimi_service()
        if kimi.api_key:
            response = requests.post(
                f"{kimi.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {kimi.api_key}", "Content-Type": "application/json"},
                json={"model": "kimi-latest", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=10
            )
            results["kimi"]["available"] = response.status_code == 200
            if not results["kimi"]["available"]:
                results["kimi"]["error"] = f"HTTP {response.status_code}"
    except Exception as e:
        results["kimi"]["error"] = str(e)[:100]
    
    # Test OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from services.openai_ai import get_openai_service
            openai = get_openai_service()
            response = requests.post(
                f"{openai.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {openai.api_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=10
            )
            results["openai"]["available"] = response.status_code == 200
            if not results["openai"]["available"]:
                results["openai"]["error"] = f"HTTP {response.status_code}"
        except Exception as e:
            results["openai"]["error"] = str(e)[:100]
    else:
        results["openai"]["error"] = "API key not configured"
    
    # Test TensorFlow Model
    try:
        tf_service = get_tf_model_service()
        results["tensorflow"]["available"] = tf_service.is_ready()
        results["tensorflow"]["model_info"] = tf_service.get_model_info()
        if not tf_service.is_ready():
            results["tensorflow"]["error"] = "Model not loaded"
    except Exception as e:
        results["tensorflow"]["error"] = str(e)[:100]
    
    return {
        "success": True,
        "services": results,
        "recommendation": "Use VPN (Singapore/Hong Kong) if Kimi is unavailable"
    }


@router.post("/detect")
async def detect_all(
    file: UploadFile = File(...),
    save_result: bool = Form(False),
    send_telegram: bool = Form(False),
    plot_id: Optional[int] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์สุขภาพพืชแบบรวม (ตรวจทั้งโรคและแมลง) ด้วย Kimi AI
    
    Args:
        file: รูปภาพที่อัปโหลด
        save_result: บันทึกผลลัพธ์ลง database หรือไม่
        send_telegram: ส่งข้อความแจ้งเตือนไปยัง Telegram หรือไม่
        plot_id: ID ของแปลง
    """
    # ตรวจสอบไฟล์
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # สร้างชื่อไฟล์ชั่วคราว
    temp_filename = f"temp_{uuid.uuid4().hex}_{file.filename}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # บันทึกไฟล์ชั่วคราว
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        contents = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(contents)
        
        # เรียก Kimi AI วิเคราะห์แบบไม่รบกวน Thread หลัก
        print(f"Starting AI Analysis for file: {file.filename}")
        result = await asyncio.to_thread(
            analyze_plant_health,
            str(temp_path)
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Analysis failed")
            print(f"AI Analysis Logic Error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"AI Analysis Error: {error_msg}")
        
        analysis = result.get("analysis")
        if not analysis:
            raw_resp = result.get("raw_response", "No raw response")
            print(f"AI returned invalid JSON content: {raw_resp}")
            raise HTTPException(status_code=500, detail="AI response could not be parsed as JSON")

        # ตรวจสอบฟิลด์พื้นฐาน
        if "is_plant" not in analysis:
             analysis["is_plant"] = True
        if "is_detected" not in analysis:
             analysis["is_detected"] = analysis.get("category") not in [None, "none", "healthy"]

        # เติมข้อมูลจาก Database หากพบ Class ที่ระบุ
        class_id_raw = analysis.get("detected_class_id")
        class_id = None
        
        # ตรวจสอบและแปลง ID ให้เป็น int อย่างปลอดภัย
        if class_id_raw and str(class_id_raw).lower() != "null":
            try:
                import re
                # หาตัวเลขใน string เช่น "ID: 30" -> 30
                nums = re.findall(r'\d+', str(class_id_raw))
                if nums:
                    class_id = int(nums[0])
            except (ValueError, TypeError, IndexError):
                class_id = None
        
        if class_id:
            try:
                diseases_collection = get_collection("diseases_pest")
                db_info = await diseases_collection.find_one({"ID": class_id})
                
                if db_info:
                    print(f"Enriching results with info from DB for ID: {class_id}")
                    analysis["target_name_th"] = db_info.get("thai_name", analysis.get("target_name_th"))
                    analysis["target_name_en"] = db_info.get("eng_name", analysis.get("target_name_en"))
                    analysis["cause"] = db_info.get("cause")
                    
                    if db_info.get("treatment"):
                        analysis["treatment"] = [db_info["treatment"]]
                    if db_info.get("prevention"):
                        analysis["prevention"] = [db_info["prevention"]]
            except Exception as db_err:
                print(f"Database enrichment error: {db_err}")
                # ไม่หยุดการทำงานหากดึงข้อมูลเสริมไม่ได้

        response_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
        }
        
        # บันทึกผลลัพธ์ลง database (เฉพาะเมื่อเลือก save_result)
        # ตรวจสอบ is_detected ให้ครอบคลุมทั้ง bool และ string
        is_detected_bool = str(analysis.get("is_detected")).lower() == "true" or analysis.get("is_detected") is True
        
        if save_result and is_detected_bool:
            try:
                # บันทึกรูปถาวร
                await file.seek(0)
                image_path = await save_image(
                    file=file,
                    image_type="detections",
                    entity_id=str(uuid.uuid4().hex[:8]),
                    filename=f"ai_detect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
                
                # เตรียมข้อมูลบันทึก
                detection_collection = get_collection("detection")
                
                # 1. จัดการ detection_id (Auto Increment)
                last_detection = await detection_collection.find_one(sort=[("detection_id", -1)])
                new_detection_id = (int(last_detection.get("detection_id") or 0) + 1) if last_detection else 1
                
                # 2. จัดการ plot_id (ถ้ามี)
                valid_plot_id = None
                if plot_id:
                    try:
                        valid_plot_id = int(plot_id)
                    except:
                        valid_plot_id = None

                # 3. จัดการ user_id
                user_id_str = None
                if current_user:
                    # รองรับทั้ง user_id (int/str) และ _id (ObjectId)
                    user_id_val = current_user.get("user_id") or current_user.get("_id")
                    if user_id_val:
                        # พยายามแปลงเป็น int ถ้าทำได้ (ตาม schema เก่า) หรือ string ถ้าจำเป็น
                        try:
                             user_id_str = int(user_id_val)
                        except:
                             user_id_str = str(user_id_val)

                # 4. จัดการ vegetable_id (หาจากแปลงที่ปลูกอยู่)
                vegetable_id = None
                if valid_plot_id:
                    try:
                        planting_collection = get_collection("planting_veg")
                        # หาการปลูกที่สถานะ active (1) หรือวางแผน (0) ในแปลงนี้
                        active_planting = await planting_collection.find_one({
                            "plot_id": valid_plot_id,
                            "status": {"$in": [0, 1]} 
                        }, sort=[("planting_date", -1)])
                        
                        if active_planting:
                            vegetable_id = active_planting.get("vegetable_id")
                    except Exception as e:
                        print(f"Error finding vegetable_id: {e}")

                # สร้างข้อมูลตาม Schema ที่ผู้ใช้ต้องการ
                detection_data = {
                    "detection_id": new_detection_id,
                    "timestamp": datetime.now(),
                    "plot_id": valid_plot_id,
                    "disease_pest_id": class_id,
                    "vegetable_id": vegetable_id,
                    "user_id": user_id_str,
                    "image_path": image_path,
                    "confidence": analysis.get("confidence"),
                    # ไม่บันทึกข้อมูล text ยาวๆ (ใช้ ID เชื่อมตารางเอา)
                }
                
                inserted = await detection_collection.insert_one(detection_data)
                response_data["detection_id"] = str(inserted.inserted_id)
                response_data["image_url"] = get_image_url(image_path)
            except Exception as save_err:
                print(f"Error saving detection history: {save_err}")
                response_data["save_error"] = str(save_err)
        
        # ส่งข้อความแจ้งเตือนไปยัง Telegram (ถ้าเลือกส่งและมีการตรวจพบ)
        print(f"🔍  [DEBUG] Telegram check - send_telegram: {send_telegram}, is_detected: {is_detected_bool}, has_user: {current_user is not None}")
        if send_telegram and is_detected_bool and current_user:
            try:
                user_id = current_user.get("user_id")
                print(f"🔍  [DEBUG] User ID from token: {user_id}")
                if user_id:
                    chat_id = None
                    
                    # ถ้าเป็น bypass_user ให้ใช้ TELEGRAM_CHAT_ID จาก .env โดยตรง
                    if user_id == "bypass_user":
                        chat_id = os.getenv("TELEGRAM_CHAT_ID")
                        print(f"🔍  [DEBUG] Bypass mode - using TELEGRAM_CHAT_ID: {chat_id}")
                    else:
                        # ค้นหาการเชื่อมต่อ Telegram ของ user (รองรับทั้ง int, string, ObjectId)
                        telegram_collection = get_collection("telegram_connections")
                        
                        # สร้าง query ที่รองรับหลายรูปแบบของ user_id
                        user_id_queries = [{"user_id": user_id}]
                        try:
                            # ลองแปลงเป็น int ถ้าเป็นเลข
                            user_id_int = int(user_id)
                            user_id_queries.append({"user_id": user_id_int})
                        except (ValueError, TypeError):
                            pass
                        
                        # สร้าง query ที่รองรับ status หลายแบบ
                        status_queries = [
                            {"status": "active"},
                            {"status": None},
                            {"status": {"$exists": False}}
                        ]
                        
                        # ค้นหาโดยรวมเงื่อนไข (user_id ตรงกัน) AND (status เป็น active หรือ null)
                        query = {
                            "$and": [
                                {"$or": user_id_queries},
                                {"$or": status_queries}
                            ]
                        }
                        print(f"🔍  [DEBUG] Telegram query: {query}")
                        connection = await telegram_collection.find_one(query)
                        
                        print(f"✅  [DEBUG] Telegram connection found: {connection is not None}")
                        if connection:
                            chat_id = connection.get("chat_id")
                    
                    print(f"🔍  [DEBUG] Chat ID: {chat_id}")
                    if chat_id:
                        # ดึงข้อมูลโรค/ศัตรูพืชจาก database เพื่อเอาข้อมูลการรักษาและ ID
                        db_treatment = None
                        disease_pest_id = None
                        if class_id:
                            try:
                                diseases_collection = get_collection("diseases_pest")
                                db_info = await diseases_collection.find_one({"ID": class_id})
                                if db_info:
                                    db_treatment = db_info.get("treatment")
                                    disease_pest_id = db_info.get("ID")
                            except Exception as db_err:
                                print(f"❌  [DEBUG] Error fetching disease info: {db_err}")
                        
                        # ดึงข้อมูลมาไว้ในตัวแปรก่อน
                        target_name = analysis.get("target_name_th", "ไม่ระบุ")
                        target_name_en = analysis.get("target_name_en", "")
                        category = analysis.get("category", "")
                        confidence = analysis.get("confidence", 0)
                        severity = analysis.get("severity_level", "ไม่ระบุ")
                        category_text = "โรคพืช" if category == "disease" else "ศัตรูพืช" if category == "pest" else "พบการตรวจจับ"

                        # ป้องกันตัวอักษรพิเศษทำลาย HTML format
                        target_name = html.escape(str(target_name))
                        target_name_en = html.escape(str(target_name_en))
                        severity = html.escape(str(severity))
                        
                        telegram_message = f"<b>🚨 แจ้งเตือนการตรวจพบ {category_text}</b>\n\n"
                        telegram_message += f"<b>ชื่อ:</b> {target_name}\n"
                        telegram_message += f"<b>ชื่อภาษาอังกฤษ:</b> {target_name_en}\n"
                        telegram_message += f"<b>ความมั่นใจ:</b> {confidence}%\n"
                        telegram_message += f"<b>ระดับความรุนแรง:</b> {severity}\n\n"
                        telegram_message += "<b>การรักษา:</b>\n"
                        
                        # ใช้ข้อมูลการรักษาจาก database ถ้ามี ไม่ก็ใช้จาก AI analysis
                        treatment_text = db_treatment if db_treatment else ""
                        if not treatment_text:
                            treatment_list = analysis.get("treatment", [])
                            if treatment_list:
                                treatment_text = treatment_list[0] if isinstance(treatment_list, list) else treatment_list
                        
                        if treatment_text:
                            # ลบ HTML tags และแบ่งเป็นข้อๆ
                            import re
                            clean_treatment = re.sub(r'<[^>]+>', '', treatment_text)
                            clean_treatment = html.escape(clean_treatment) # Escape content
                            # แบ่งตามตัวเลขหรือขึ้นบรรทัดใหม่
                            steps = re.split(r'(?:\d+[.)]\s*|\n+)', clean_treatment)
                            steps = [s.strip() for s in steps if s.strip()]
                            for i, step in enumerate(steps[:5], 1):  # สูงสุด 5 ขั้นตอน
                                telegram_message += f"{i}. {step}\n"
                        else:
                            telegram_message += "ไม่มีข้อมูล\n"
                        
                        # เพิ่มเวลาบันทึกและเตรียมลิงก์
                        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
                        telegram_message += f"\n<i>บันทึกเมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
                        
                        reply_markup = None
                        if class_id:
                            detail_url = f"{frontend_url}/diseases-pest/details/{class_id}"
                            
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


                        # ส่งรูปพร้อมข้อความ (ถ้ามี image_url)
                        image_url = response_data.get("image_url")
                        print(f"🔍  [DEBUG] Image URL from response_data: {image_url}")

                        if image_url:
                            success = send_telegram_photo_with_caption(chat_id, image_url, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
                        else:
                            print(f"⚠️  [DEBUG] No image_url found, sending text only")
                            success = send_telegram_message(chat_id, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
                        
                        if success:
                            response_data["telegram_sent"] = True
                            print(f"✅  [DEBUG] Telegram notification sent to user {user_id}")
                        else:
                            response_data["telegram_error"] = "Failed to send Telegram message"
                            print(f"❌  [DEBUG] Failed to send Telegram message")
                    else:
                        print(f"❌  [DEBUG] No chat_id found in connection")
                else:
                    print(f"❌  [DEBUG] No active Telegram connection for user {user_id}")
            except Exception as tele_err:
                print(f"❌  [DEBUG] Error sending Telegram notification: {tele_err}")
                response_data["telegram_error"] = str(tele_err)
            
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"CRITICAL ERROR in detect_all: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/detect/disease")
async def detect_disease(
    file: UploadFile = File(...),
    save_result: bool = Form(False),
    send_telegram: bool = Form(False),
    plot_id: Optional[int] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์โรคพืชจากรูปภาพด้วย Kimi AI (Legacy endpoint, uses unified logic)
    """
    return await detect_all(file, save_result, send_telegram, plot_id, current_user)


@router.post("/detect/pest")
async def detect_pest(
    file: UploadFile = File(...),
    save_result: bool = Form(False),
    send_telegram: bool = Form(False),
    plot_id: Optional[int] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์แมลงศัตรูพืชจากรูปภาพด้วย Kimi AI (Legacy endpoint, uses unified logic)
    """
    return await detect_all(file, save_result, send_telegram, plot_id, current_user)


@router.post("/detect/tf")
async def detect_with_tensorflow(
    file: UploadFile = File(...),
    save_result: bool = Form(False),
    send_telegram: bool = Form(False),
    plot_id: Optional[int] = Form(None),
    use_tta: bool = Form(True),
    enhance: bool = Form(True),
    confidence_threshold: float = Form(0.5),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์รูปภาพโรคพืชและศัตรูพืชด้วย TensorFlow Model (MobileNetV2)
    รองรับ Image Enhancement และ Test Time Augmentation (TTA) เพื่อเพิ่มความแม่นยำ
    
    Args:
        file: รูปภาพที่อัปโหลด
        save_result: บันทึกผลลัพธ์ลง database หรือไม่
        send_telegram: ส่งข้อความแจ้งเตือนไปยัง Telegram หรือไม่
        plot_id: ID ของแปลง
        use_tta: ใช้ Test Time Augmentation (เพิ่มความแม่นยำ)
        enhance: ปรับปรุงคุณภาพรูปภาพ (white balance, contrast, denoise)
        confidence_threshold: เกณฑ์ความมั่นใจขั้นต่ำ (0.0 - 1.0)
        
    Returns:
        ผลการวิเคราะห์จากโมเดล TensorFlow
    """
    # ตรวจสอบไฟล์
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # ตรวจสอบว่าโมเดลพร้อมใช้งานหรือไม่
    tf_service = get_tf_model_service()
    if not tf_service.is_ready():
        raise HTTPException(
            status_code=503, 
            detail="TensorFlow model not available. Please check model file at D:/pang/project/trainmodel/final_tf_model.keras"
        )
    
    # สร้างชื่อไฟล์ชั่วคราว
    temp_filename = f"tf_temp_{uuid.uuid4().hex}_{file.filename}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # บันทึกไฟล์ชั่วคราว
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        contents = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(contents)
        
        # วิเคราะห์ด้วย TensorFlow
        print(f"🔍 Starting TensorFlow Analysis for file: {file.filename}")
        print(f"   - TTA: {use_tta}, Enhance: {enhance}, Threshold: {confidence_threshold}")
        result = await asyncio.to_thread(
            analyze_with_tensorflow,
            str(temp_path),
            use_tta=use_tta,
            enhance=enhance,
            confidence_threshold=confidence_threshold
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Analysis failed")
            print(f"❌ TensorFlow Analysis Error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"TensorFlow Analysis Error: {error_msg}")
        
        # ดึงข้อมูลผลลัพธ์หลัก
        primary = result.get("primary", {})
        top_3 = result.get("top_3", [])
        is_detected = result.get("is_detected", False)
        
        # ดึง class_id จาก database ถ้ามี
        class_id = None
        detected_class_name = primary.get("class_name", "")
        
        try:
            diseases_collection = get_collection("diseases_pest")
            # ค้นหาจากชื่อภาษาอังกฤษหรือชื่อภาษาไทย
            db_info = await diseases_collection.find_one({
                "$or": [
                    {"eng_name": {"$regex": detected_class_name, "$options": "i"}},
                    {"thai_name": primary.get("name_th", "")}
                ]
            })
            if db_info:
                class_id = db_info.get("ID")
                print(f"✅ Found disease in DB with ID: {class_id}")
        except Exception as db_err:
            print(f"⚠️ Database lookup error: {db_err}")
        
        # ดึงข้อมูล uncertainty และ validation
        is_uncertain = result.get("is_uncertain", False)
        uncertainty_score = result.get("uncertainty_score", 0)
        preprocessing_info = result.get("preprocessing", {})
        validation_info = result.get("validation", {})
        
        # ใช้ adjusted confidence ถ้ามี
        adjusted_confidence = primary.get("adjusted_confidence_percent", primary.get("confidence_percent", 0))
        original_confidence = primary.get("confidence_percent", 0)
        
        # กำหนดระดับความรุนแรงตาม confidence และ uncertainty
        confidence = adjusted_confidence  # ใช้ adjusted confidence
        if is_uncertain or confidence < 60:
            severity_level = "ต้องตรวจสอบเพิ่มเติม"
        elif confidence >= 80:
            severity_level = "สูง"
        elif confidence >= 60:
            severity_level = "ปานกลาง"
        else:
            severity_level = "ต่ำ"
        
        # ดึง warnings จาก validation
        validation_warnings = validation_info.get("warnings", [])
        category_analysis = validation_info.get("category_analysis", {})
        
        # สร้างข้อความแนะนำเพิ่มเติมจาก validation
        additional_notes = []
        if validation_warnings:
            for warning in validation_warnings:
                additional_notes.append(warning.get("message", ""))
        
        # ถ้ามี category conflict ให้แสดง top 2 เพื่อเปรียบเทียบ
        show_alternatives = validation_info.get("has_category_conflict", False)
        
        # กำหนด confidence_level สำหรับ Frontend
        if is_uncertain or confidence < 60:
            confidence_level = "low"
        elif confidence >= 80:
            confidence_level = "high"
        else:
            confidence_level = "medium"
        
        # สร้าง response ในรูปแบบเดียวกับ detect_all
        analysis = {
            "is_plant": result.get("is_plant", True),
            "is_detected": is_detected,
            "is_uncertain": is_uncertain,
            "category": primary.get("category", "unknown"),
            "target_name_th": primary.get("name_th", "ไม่ระบุ"),
            "target_name_en": primary.get("name_en", "Unknown"),
            "confidence": confidence,
            "confidence_level": confidence_level,  # ⭐ สำหรับ badge สีใน Frontend
            "model": "MobileNetV2",  # ⭐ สำหรับแสดงใน Frontend
            "original_confidence": original_confidence,  # ⭐ แสดง confidence ก่อนปรับ
            "uncertainty": {
                "is_uncertain": is_uncertain,
                "top_1_confidence": primary.get("confidence_percent", 0),
                "top_2_confidence": top_3[1].get("confidence_percent", 0) if len(top_3) > 1 else 0,
            } if len(top_3) > 1 else None,
            "uncertainty_score": uncertainty_score,
            "severity_level": severity_level,
            "symptoms": "กำลังโหลดข้อมูล...",  # ⭐ Default รอ DB enrichment
            "detected_class_id": class_id,
            "top_3_predictions": [
                {
                    "name_th": p.get("name_th"),
                    "name_en": p.get("name_en"),
                    "confidence": p.get("confidence_percent"),
                    "category": p.get("category"),
                }
                for p in top_3
            ],
            "model_used": "TensorFlow_MobileNetV2",
            "preprocessing": preprocessing_info,
            "confidence_threshold_used": confidence_threshold,
            "validation": {
                "is_consistent": validation_info.get("is_consistent", True),
                "has_conflict": validation_info.get("has_category_conflict", False),
                "warnings": validation_warnings,
                "has_category_conflict": show_alternatives,
                "category_confidence": category_analysis,
                "detected_category": primary.get("category"),
                "suggested_category": category_analysis.get("suggested_category") if validation_info.get("has_category_conflict") else None,
            },
            "additional_notes": additional_notes if additional_notes else None,
            "show_alternatives": show_alternatives,  # บ่งบอกว่าควรแสดงตัวเลือกอื่นหรือไม่
        }
        
        # เติมข้อมูลจาก Database ถ้าพบ class_id
        if class_id:
            try:
                if db_info:
                    analysis["target_name_th"] = db_info.get("thai_name", analysis["target_name_th"])
                    analysis["target_name_en"] = db_info.get("eng_name", analysis["target_name_en"])
                    analysis["symptoms"] = db_info.get("cause") or db_info.get("symptoms") or "ไม่มีข้อมูลอาการ"
                    analysis["cause"] = db_info.get("cause")
                    if db_info.get("treatment"):
                        analysis["treatment"] = [db_info["treatment"]]
                    else:
                        analysis["treatment"] = ["ไม่มีข้อมูลการรักษาในระบบ"]
                    if db_info.get("prevention"):
                        analysis["prevention"] = [db_info["prevention"]]
                    else:
                        analysis["prevention"] = ["ไม่มีข้อมูลการป้องกันในระบบ"]
            except Exception as db_err:
                print(f"Database enrichment error: {db_err}")
        else:
            # ไม่พบข้อมูลใน DB
            analysis["symptoms"] = "ไม่พบข้อมูลในระบบ"
            analysis["treatment"] = ["ไม่มีข้อมูลการรักษา"]
            analysis["prevention"] = ["ไม่มีข้อมูลการป้องกัน"]
        
        response_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
        }
        
        # บันทึกผลลัพธ์ลง database (ถ้าเลือก save_result)
        if save_result and is_detected:
            try:
                # บันทึกรูปถาวร
                await file.seek(0)
                image_path = await save_image(
                    file=file,
                    image_type="detections",
                    entity_id=str(uuid.uuid4().hex[:8]),
                    filename=f"tf_detect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
                
                # เตรียมข้อมูลบันทึก
                detection_collection = get_collection("detection")
                
                # 1. จัดการ detection_id (Auto Increment)
                last_detection = await detection_collection.find_one(sort=[("detection_id", -1)])
                new_detection_id = (int(last_detection.get("detection_id") or 0) + 1) if last_detection else 1
                
                # 2. จัดการ plot_id
                valid_plot_id = None
                if plot_id:
                    try:
                        valid_plot_id = int(plot_id)
                    except:
                        valid_plot_id = None
                
                # 3. จัดการ user_id
                user_id_str = None
                if current_user:
                    user_id_val = current_user.get("user_id") or current_user.get("_id")
                    if user_id_val:
                        try:
                            user_id_str = int(user_id_val)
                        except:
                            user_id_str = str(user_id_val)
                
                # 4. จัดการ vegetable_id
                vegetable_id = None
                if valid_plot_id:
                    try:
                        planting_collection = get_collection("planting_veg")
                        active_planting = await planting_collection.find_one({
                            "plot_id": valid_plot_id,
                            "status": {"$in": [0, 1]}
                        }, sort=[("planting_date", -1)])
                        if active_planting:
                            vegetable_id = active_planting.get("vegetable_id")
                    except Exception as e:
                        print(f"Error finding vegetable_id: {e}")
                
                detection_data = {
                    "detection_id": new_detection_id,
                    "timestamp": datetime.now(),
                    "plot_id": valid_plot_id,
                    "disease_pest_id": class_id,
                    "vegetable_id": vegetable_id,
                    "user_id": user_id_str,
                    "image_path": image_path,
                    "confidence": primary.get("confidence_percent", 0) / 100,
                    "ai_model": "tensorflow",
                }
                
                inserted = await detection_collection.insert_one(detection_data)
                response_data["detection_id"] = str(inserted.inserted_id)
                response_data["image_url"] = get_image_url(image_path)
                
            except Exception as save_err:
                print(f"Error saving detection history: {save_err}")
                response_data["save_error"] = str(save_err)
        
        # ส่งข้อความแจ้งเตือนไปยัง Telegram (ถ้าเลือกส่ง)
        if send_telegram and is_detected and current_user:
            try:
                user_id = current_user.get("user_id")
                if user_id:
                    chat_id = None
                    
                    # Bypass mode
                    if user_id == "bypass_user":
                        chat_id = os.getenv("TELEGRAM_CHAT_ID")
                    else:
                        telegram_collection = get_collection("telegram_connections")
                        user_id_queries = [{"user_id": user_id}]
                        try:
                            user_id_int = int(user_id)
                            user_id_queries.append({"user_id": user_id_int})
                        except (ValueError, TypeError):
                            pass
                        
                        status_queries = [
                            {"status": "active"},
                            {"status": None},
                            {"status": {"$exists": False}}
                        ]
                        
                        query = {
                            "$and": [
                                {"$or": user_id_queries},
                                {"$or": status_queries}
                            ]
                        }
                        connection = await telegram_collection.find_one(query)
                        if connection:
                            chat_id = connection.get("chat_id")
                    
                    if chat_id:
                        target_name = html.escape(str(primary.get("name_th", "ไม่ระบุ")))
                        target_name_en = html.escape(str(primary.get("name_en", "")))
                        confidence = primary.get("confidence_percent", 0)
                        category = primary.get("category", "")
                        category_text = "โรคพืช" if category == "disease" else "ศัตรูพืช" if category == "pest" else "พบการตรวจจับ"
                        
                        telegram_message = f"<b>🚨 แจ้งเตือนการตรวจพบ {category_text} (TensorFlow)</b>\n\n"
                        telegram_message += f"<b>ชื่อ:</b> {target_name}\n"
                        telegram_message += f"<b>ชื่อภาษาอังกฤษ:</b> {target_name_en}\n"
                        telegram_message += f"<b>ความมั่นใจ:</b> {confidence}%\n\n"
                        telegram_message += f"<i>บันทึกเมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
                        
                        reply_markup = None
                        if class_id:
                            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
                            detail_url = f"{frontend_url}/diseases-pest/details/{class_id}"
                            if "localhost" in detail_url or "127.0.0.1" in detail_url:
                                local_ip = get_local_ip()
                                detail_url = detail_url.replace("localhost", local_ip).replace("127.0.0.1", local_ip)
                            reply_markup = {
                                "inline_keyboard": [
                                    [{"text": "🔗 ดูรายละเอียดและวิธีการจัดการ", "url": detail_url}]
                                ]
                            }
                        
                        image_url = response_data.get("image_url")
                        if image_url:
                            success = send_telegram_photo_with_caption(chat_id, image_url, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
                        else:
                            success = send_telegram_message(chat_id, telegram_message, parse_mode="HTML", reply_markup=reply_markup)
                        
                        if success:
                            response_data["telegram_sent"] = True
                        else:
                            response_data["telegram_error"] = "Failed to send Telegram message"
                            
            except Exception as tele_err:
                print(f"❌ Error sending Telegram notification: {tele_err}")
                response_data["telegram_error"] = str(tele_err)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"CRITICAL ERROR in detect_with_tensorflow: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("/tf/model-info")
async def get_tensorflow_model_info():
    """
    ดึงข้อมูลเกี่ยวกับ TensorFlow Model
    
    Returns:
        ข้อมูลโมเดล เช่น ชื่อคลาส, input size, model path
    """
    try:
        tf_service = get_tf_model_service()
        return {
            "success": True,
            "model_info": tf_service.get_model_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model info: {str(e)}")


@router.post("/detect/tf/compare")
async def detect_with_tensorflow_compare(
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    เปรียบเทียบผลการวิเคราะห์ระหว่างแบบปกติ vs แบบปรับปรุง (TTA + Enhancement)
    ใช้สำหรับทดสอบว่าการ preprocess ช่วยให้ผลดีขึ้นหรือไม่
    
    Args:
        file: รูปภาพที่อัปโหลด
        
    Returns:
        ผลการเปรียบเทียบทั้ง 4 แบบ:
        1. แบบปกติ (ไม่มี TTA, ไม่ Enhance)
        2. มี TTA อย่างเดียว
        3. Enhance อย่างเดียว
        4. ทั้ง TTA + Enhance (แนะนำ)
    """
    # ตรวจสอบไฟล์
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # ตรวจสอบว่าโมเดลพร้อมใช้งานหรือไม่
    tf_service = get_tf_model_service()
    if not tf_service.is_ready():
        raise HTTPException(
            status_code=503, 
            detail="TensorFlow model not available."
        )
    
    # สร้างชื่อไฟล์ชั่วคราว
    temp_filename = f"tf_compare_{uuid.uuid4().hex}_{file.filename}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # บันทึกไฟล์ชั่วคราว
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        contents = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(contents)
        
        # ทดสอบทั้ง 4 แบบ
        results = {}
        
        # 1. แบบปกติ (ไม่มี TTA, ไม่ Enhance)
        print("🔍 Testing: Normal (No TTA, No Enhance)")
        results["normal"] = await asyncio.to_thread(
            analyze_with_tensorflow, str(temp_path), use_tta=False, enhance=False
        )
        
        # 2. มี TTA อย่างเดียว
        print("🔍 Testing: TTA Only")
        results["tta_only"] = await asyncio.to_thread(
            analyze_with_tensorflow, str(temp_path), use_tta=True, enhance=False
        )
        
        # 3. Enhance อย่างเดียว
        print("🔍 Testing: Enhance Only")
        results["enhance_only"] = await asyncio.to_thread(
            analyze_with_tensorflow, str(temp_path), use_tta=False, enhance=True
        )
        
        # 4. ทั้ง TTA + Enhance (แนะนำ)
        print("🔍 Testing: TTA + Enhance (Recommended)")
        results["tta_enhance"] = await asyncio.to_thread(
            analyze_with_tensorflow, str(temp_path), use_tta=True, enhance=True
        )
        
        # สร้างสรุปการเปรียบเทียบ
        comparison = []
        for mode, result in results.items():
            if result.get("success"):
                primary = result.get("primary", {})
                comparison.append({
                    "mode": mode,
                    "prediction": primary.get("name_th", "N/A"),
                    "confidence": primary.get("confidence_percent", 0),
                    "is_uncertain": result.get("is_uncertain", False),
                })
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "comparison": comparison,
            "detailed_results": results,
            "recommendation": "ใช้ mode 'tta_enhance' เพื่อผลลัพธ์ที่แม่นยำที่สุด"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"CRITICAL ERROR in detect_with_tensorflow_compare: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/chat")
async def ai_chat(
    message: str = Form(...),
    context: Optional[str] = Form(None),
):
    """
    สนทนากับผู้ช่วย AI เกี่ยวกับการเกษตร
    
    Args:
        message: ข้อความคำถาม
        context: บริบทเพิ่มเติม (optional)
    
    Returns:
        คำตอบจาก AI
    """
    try:
        result = chat_with_assistant(message, context)
        
        if result.get("success"):
            return {
                "success": True,
                "response": result["content"],
                "model": result.get("model"),
                "usage": result.get("usage")
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Chat failed"))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/detection-history")
async def get_detection_history(
    limit: int = 20,
    skip: int = 0,
):
    """
    ดึงประวัติการตรวจจับด้วย AI
    
    Args:
        limit: จำนวนรายการที่ต้องการ
        skip: จำนวนรายการที่ข้าม
    
    Returns:
        รายการประวัติการตรวจจับ
    """
    try:
        detection_collection = get_collection("detection")
        
        cursor = detection_collection.find(
            {}
        ).sort("timestamp", -1).skip(skip).limit(limit)
        
        detections = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["timestamp"] = doc["timestamp"].isoformat() if doc.get("timestamp") else None
            if doc.get("image_path"):
                doc["image_url"] = get_image_url(doc["image_path"])
            detections.append(doc)
        
        return {
            "success": True,
            "count": len(detections),
            "detections": detections
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/verify-detection/{detection_id}")
async def verify_detection(
    detection_id: str,
    is_correct: bool = Form(...),
    correct_disease_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    ยืนยันหรือแก้ไขผลการตรวจจับ AI
    
    Args:
        detection_id: ID ของการตรวจจับ
        is_correct: ผลการตรวจจับถูกต้องหรือไม่
        correct_disease_id: ID ของโรคที่ถูกต้อง (ถ้าผล AI ผิด)
        notes: หมายเหตุเพิ่มเติม
    
    Returns:
        ผลการอัปเดต
    """
    try:
        if not ObjectId.is_valid(detection_id):
            raise HTTPException(status_code=400, detail="Invalid detection ID")
        
        detection_collection = get_collection("detection")
        
        update_data = {
            "is_verified": True,
            "ai_result_correct": is_correct,
            "verified_at": datetime.now(),
        }
        
        if not is_correct and correct_disease_id:
            update_data["corrected_disease_id"] = correct_disease_id
        
        if notes:
            update_data["verification_notes"] = notes
        
        result = await detection_collection.update_one(
            {"_id": ObjectId(detection_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        return {
            "success": True,
            "message": "Verification recorded successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")
