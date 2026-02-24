"""
Hybrid AI Detection Routes
รวม TensorFlow Model (เร็ว) + Kimi AI (ละเอียด)
"""

import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
import asyncio
import numpy as np
import cv2
import json

from database import get_collection
from utils.file_handler import save_image, get_image_url
from services.tf_model_service import (
    analyze_with_tensorflow,
    get_tf_model_service,
)
from services.kimi_ai import analyze_plant_health
from auth_utils import get_current_user_optional
from routes.telegram import send_telegram_message
from services.iot_service import trigger_sprayer


router = APIRouter(prefix="/api/ai", tags=["AI Hybrid Detection"])

TEMP_DIR = Path("static/img/temp")


@router.post("/detect-hybrid")
async def detect_hybrid(
    file: UploadFile = File(...),
    save_result: bool = Form(False),
    send_telegram: bool = Form(False),
    plot_id: Optional[int] = Form(None),
    tf_threshold: float = Form(0.4),  # Optimized: best threshold from testing
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์รูปภาพแบบ Hybrid (TensorFlow + Kimi AI)
    
    Logic:
    1. เรียก TensorFlow ก่อน (เร็ว)
    2. ถ้า TF confidence >= threshold (default 60%) → ใช้ผล TF
    3. ถ้า TF confidence < threshold → Fallback ไปถาม Kimi AI
    4. ถ้า Kimi ก็ยังไม่แน่ใจ → บอกว่า Healthy
    
    Args:
        file: รูปภาพที่อัปโหลด
        save_result: บันทึกผลลัพธ์ลง database หรือไม่
        send_telegram: ส่งข้อความแจ้งเตือนไปยัง Telegram หรือไม่
        plot_id: ID ของแปลง
        tf_threshold: เกณฑ์ความมั่นใจขั้นต่ำของ TensorFlow (0.0-1.0)
        
    Returns:
        ผลการวิเคราะห์พร้อมบอกว่าใช้โมเดลไหน
    """
    # ตรวจสอบไฟล์
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # สร้างชื่อไฟล์ชั่วคราว
    temp_filename = f"hybrid_{uuid.uuid4().hex}_{file.filename}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # บันทึกไฟล์ชั่วคราว
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        contents = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(contents)
        
        print(f"🔍 [HYBRID] Starting analysis for: {file.filename}")
        
        # ========== STEP 1: เรียก TensorFlow ก่อน (เร็ว) ==========
        tf_service = get_tf_model_service()
        tf_result = None
        tf_confidence = 0
        
        if tf_service.is_ready():
            print(f"   → Step 1: TensorFlow analysis")
            tf_result = await asyncio.to_thread(
                analyze_with_tensorflow,
                str(temp_path),
                use_tta=False,      # Optimized params
                enhance=False,
                confidence_threshold=0.0  # ไม่ใช้ threshold ตอนนี้ จะใช้ weighting แทน
            )
        
        # เก็บค่า TF confidence
        if tf_result and tf_result.get("success"):
            tf_confidence = tf_result.get("primary", {}).get("confidence", 0)
            tf_prediction = tf_result.get("primary", {})
            print(f"   → TF Result: {tf_prediction.get('name_th')} (confidence: {tf_confidence:.2%})")
        
        # ========== STEP 2: เรียก Kimi AI (ละเอียด) ==========
        # เรียกเสมอเพื่อเอาไปชั่งน้ำหนัก
        print(f"   → Step 2: Kimi AI analysis")
        kimi_result = await asyncio.to_thread(
            analyze_plant_health,
            str(temp_path)
        )
        
        kimi_confidence = 0.5  # Default ถ้า Kimi ไม่บอก confidence
        kimi_prediction = None
        
        if kimi_result and kimi_result.get("success"):
            analysis = kimi_result.get("analysis", {})
            kimi_prediction = analysis
            # Kimi อาจไม่มี confidence ชัดเจน ให้ใช้ heuristic
            kimi_conf = analysis.get("confidence", "medium")
            if isinstance(kimi_conf, str):
                # แปลงเป็น number
                conf_map = {"very_high": 0.9, "high": 0.75, "medium": 0.5, "low": 0.3, "very_low": 0.1}
                kimi_confidence = conf_map.get(kimi_conf.lower(), 0.5)
            else:
                kimi_confidence = float(kimi_conf) if kimi_conf else 0.5
            
            print(f"   → Kimi Result: {analysis.get('target_name_th')} (confidence: {kimi_confidence:.2%})")
        
        # ========== STEP 3: Confidence-based Weighting ==========
        print(f"   → Weighting: TF={tf_confidence:.2%}, Kimi={kimi_confidence:.2%}")
        
        # คำนวณน้ำหนัก
        if tf_confidence >= 0.7:
            # TF มั่นใจมาก → ใช้ TF เป็นหลัก (70-90%)
            tf_weight = 0.8
            kimi_weight = 0.2
            weight_method = "tf_high_confidence"
            
        elif tf_confidence >= 0.5:
            # TF มั่นใจปานกลาง → ชั่งเท่า ๆ กัน
            tf_weight = 0.6
            kimi_weight = 0.4
            weight_method = "balanced"
            
        elif tf_confidence >= 0.3:
            # TF ไม่มั่นใจ → ให้ Kimi มากกว่า
            tf_weight = 0.4
            kimi_weight = 0.6
            weight_method = "kimi_preferred"
            
        else:
            # TF มั่นใจน้อยมาก → ให้ Kimi เป็นหลัก
            tf_weight = 0.2
            kimi_weight = 0.8
            weight_method = "kimi_high_confidence"
        
        # ตัดสินใจใช้ผลลัพธ์
        if tf_result and tf_result.get("success") and kimi_result and kimi_result.get("success"):
            # ถ้าทั้งสองตรงกัน → ใช้เลย
            tf_class = tf_prediction.get("class_name", "")
            kimi_class = kimi_prediction.get("target_name_en", "")
            
            # Normalize class names for comparison
            tf_class_norm = tf_class.replace(" ", "").lower()
            kimi_class_norm = kimi_class.replace(" ", "").lower()
            
            if tf_class_norm == kimi_class_norm or tf_class in kimi_class or kimi_class in tf_class:
                print(f"   ✓ Both models agree: {tf_prediction.get('name_th')}")
                response_data = _build_tf_response(tf_result, "both_agree")
                model_used = "both_agree"
            else:
                # ไม่ตรงกัน → ใช้ confidence weighting
                if tf_weight >= kimi_weight:
                    print(f"   ✓ Weighted: Using TensorFlow (weight={tf_weight:.0%})")
                    response_data = _build_tf_response(tf_result, "weighted_tf")
                    response_data["analysis"]["kimi_disagreement"] = kimi_prediction.get("target_name_th")
                    model_used = f"weighted_tf({tf_weight:.0%})"
                else:
                    print(f"   ✓ Weighted: Using Kimi AI (weight={kimi_weight:.0%})")
                    response_data = _build_kimi_response(kimi_result)
                    response_data["analysis"]["tf_disagreement"] = tf_prediction.get("name_th")
                    model_used = f"weighted_kimi({kimi_weight:.0%})"
                
                # เพิ่มข้อมูล weighting
                response_data["weighting_info"] = {
                    "tf_weight": tf_weight,
                    "kimi_weight": kimi_weight,
                    "tf_confidence": tf_confidence,
                    "kimi_confidence": kimi_confidence,
                    "method": weight_method
                }
                
        elif tf_result and tf_result.get("success"):
            # มีแค่ TF
            print(f"   ✓ Only TensorFlow available")
            response_data = _build_tf_response(tf_result, "tensorflow_only")
            model_used = "tensorflow_only"
            
        elif kimi_result and kimi_result.get("success"):
            # มีแค่ Kimi
            print(f"   ✓ Only Kimi AI available")
            response_data = _build_kimi_response(kimi_result)
            model_used = "kimi_only"
            
        else:
            # ทั้งสองล้ม
            raise HTTPException(status_code=500, detail="Both TensorFlow and Kimi AI failed")
        
        # เพิ่ม metadata
        response_data["hybrid_info"] = {
            "model_used": model_used,
            "tf_threshold": tf_threshold,
            "timestamp": datetime.now().isoformat(),
            "weighting_method": "confidence_based",
        }
        
        # เพิ่มข้อมูล weighting ถ้ามี
        if "weighting_info" in response_data:
            response_data["hybrid_info"]["weighting"] = response_data.pop("weighting_info")
        
        # บันทึกผลลง database (ถ้าเลือก)
        if save_result:
            await _save_detection(response_data, temp_path, plot_id, current_user, model_used)
        
        return response_data

        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ [HYBRID] Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")
    
    finally:
        # ลบไฟล์ชั่วคราว
        if temp_path.exists():
            temp_path.unlink()


@router.post("/analyze-public")
async def analyze_public(
    file: UploadFile = File(...),
):
    """
    วิเคราะห์รูปภาพแบบสาธารณะ (ไม่ต้อง Login)
    ให้ข้อมูลเบื้องต้นเกี่ยวกับโรค/แมลงที่พบ
    """
    # 1. วิเคราะห์ด้วย AI (ไม่บันทึกลง DB)
    response_data = await detect_hybrid(
        file=file,
        save_result=False,
        send_telegram=False
    )
    
    analysis = response_data.get("analysis", {})
    thai_name = analysis.get("thai_name")
    
    if not thai_name:
        return {"detected": False, "message": "ไม่พบโรคหรือแมลงในภาพ"}
    
    # 2. ค้นหาข้อมูลเพิ่มเติมจากฐานข้อมูล
    collection = get_collection("diseases_pest")
    disease_pest = await collection.find_one({"thai_name": thai_name})
    
    if not disease_pest:
        return {
            "detected": True,
            "found_in_db": False,
            "message": f"ตรวจพบ '{thai_name}' แต่ยังไม่มีข้อมูลวิธีรักษาในระบบ",
            "confidence": response_data.get("accuracy", 0)
        }
    
    # 3. ส่งผลลัพธ์พร้อมคำแนะนำ
    return {
        "detected": True,
        "found_in_db": True,
        "confidence": response_data.get("accuracy", 0),
        "details": {
            "id": str(disease_pest.get("_id")),
            "thai_name": disease_pest.get("thai_name"),
            "eng_name": disease_pest.get("eng_name"),
            "type": disease_pest.get("type"),
            "prevention": disease_pest.get("prevention") or "ไม่มีข้อมูลการป้องกัน",
            "treatment": disease_pest.get("treatment") or "ไม่มีข้อมูลการรักษา"
        }
    }


@router.post("/detect-cctv")
async def detect_cctv(
    file: UploadFile = File(...),
    plot_id: Optional[int] = Form(None),
    tf_threshold: float = Form(0.6),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    วิเคราะห์รูปภาพจากกล้องวงจรปิด (CCTV)
    ถ้าเจอศัตรูพืช (Pest) จะสั่งเครื่องพ่นน้ำอัตโนมัติ
    """
    # เรียกใช้ Logic การตรวจจับเดิม (ไม่บันทึกผลลง DB และไม่ส่ง Telegram ซ้ำซ้อนในโหมดนี้)
    # หรือจะบันทึกก็ได้ถ้าผู้ใช้ต้องการ
    response_data = await detect_hybrid(
        file=file,
        save_result=True,
        send_telegram=True,
        plot_id=plot_id,
        tf_threshold=tf_threshold,
        current_user=current_user
    )
    
    # สั่งงาน Arduino ถ้าเจอศัตรูพืช (Pest)
    if response_data.get("analysis", {}).get("category") == "pest":
        print("👾 [CCTV] Pest detected! Triggering water sprayer automatically...")
        trigger_sprayer(duration=5)
        response_data["iot_triggered"] = True
        
    return response_data


def _build_tf_response(tf_result: Dict, model: str) -> Dict:
    """สร้าง response จากผล TensorFlow"""
    primary = tf_result.get("primary", {})
    top_3 = tf_result.get("top_3", [])
    
    return {
        "success": True,
        "is_detected": tf_result.get("is_detected", False),
        "is_healthy": tf_result.get("is_healthy", False),
        "analysis": {
            "target_name_th": primary.get("name_th", "ไม่ระบุ"),
            "target_name_en": primary.get("name_en", "Unknown"),
            "category": primary.get("category", "unknown"),
            "confidence": primary.get("confidence_percent", 0),
            "confidence_level": _get_confidence_level(primary.get("confidence", 0)),
            "top_3_predictions": [
                {
                    "name_th": p.get("name_th"),
                    "confidence": p.get("confidence_percent"),
                }
                for p in top_3
            ],
            "model_used": model,
        }
    }


def _build_kimi_response(kimi_result: Dict) -> Dict:
    """สร้าง response จากผล Kimi AI"""
    analysis = kimi_result.get("analysis", {})
    
    return {
        "success": True,
        "is_detected": analysis.get("is_detected", False),
        "is_healthy": analysis.get("category") == "healthy",
        "analysis": {
            "target_name_th": analysis.get("target_name_th", "ไม่ระบุ"),
            "target_name_en": analysis.get("target_name_en", "Unknown"),
            "category": analysis.get("category", "unknown"),
            "confidence": analysis.get("confidence", 0),
            "description": analysis.get("description", ""),
            "treatment": analysis.get("treatment", []),
            "prevention": analysis.get("prevention", []),
            "model_used": "kimi",
        }
    }


def _get_confidence_level(confidence: float) -> str:
    """แปลง confidence เป็นระดับ"""
    if confidence >= 0.9:
        return "very_high"
    elif confidence >= 0.7:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    else:
        return "low"


async def _save_detection(response_data, image_path, plot_id, current_user, model_used):
    """บันทึกผลการตรวจจับลง database"""
    try:
        detection_collection = get_collection("detection")
        
        # หา detection_id ถัดไป
        last = await detection_collection.find_one(sort=[("detection_id", -1)])
        new_id = (int(last.get("detection_id") or 0) + 1) if last else 1
        
        # จัดการ user_id
        user_id_str = None
        if current_user:
            user_id_val = current_user.get("user_id") or current_user.get("_id")
            if user_id_val:
                try:
                    user_id_str = int(user_id_val)
                except:
                    user_id_str = str(user_id_val)
        
        # หา vegetable_id
        vegetable_id = None
        if plot_id:
            try:
                planting = get_collection("planting_veg")
                active = await planting.find_one({
                    "plot_id": int(plot_id),
                    "status": {"$in": [0, 1]}
                }, sort=[("planting_date", -1)])
                if active:
                    vegetable_id = active.get("vegetable_id")
            except:
                pass
        
        # บันทึก
        await detection_collection.insert_one({
            "detection_id": new_id,
            "timestamp": datetime.now(),
            "plot_id": plot_id,
            "user_id": user_id_str,
            "image_path": str(image_path),
            "ai_model": model_used,
            "result": response_data.get("analysis", {}),
        })
        
        response_data["saved"] = True
        
    except Exception as e:
        print(f"⚠ Save error: {e}")
        response_data["save_error"] = str(e)


async def _send_telegram_notification(response_data, current_user):
    """ส่งข้อความแจ้งเตือน Telegram"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            return
        
        analysis = response_data.get("analysis", {})
        name_th = analysis.get("target_name_th", "ไม่ระบุ")
        category = analysis.get("category", "unknown")
        
        category_text = "โรคพืช" if category == "disease" else "ศัตรูพืช" if category == "pest" else "พืชสุขภาพดี"
        
        message = f"<b>🚨 แจ้งเตือนการตรวจพบ{category_text}</b>\n\n"
        message += f"ผลการวิเคราะห์: {name_th}\n"
        message += f"โมเดลที่ใช้: {analysis.get('model_used', 'hybrid').upper()}"
        
        # หา chat_id
        chat_id = None
        if user_id == "bypass_user":
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
        else:
            telegram = get_collection("telegram_connections")
            conn = await telegram.find_one({"user_id": user_id})
            if conn:
                chat_id = conn.get("chat_id")
        
        if chat_id:
            send_telegram_message(chat_id, message, parse_mode="HTML")
            response_data["telegram_sent"] = True
            
    except Exception as e:
        print(f"⚠ Telegram error: {e}")
