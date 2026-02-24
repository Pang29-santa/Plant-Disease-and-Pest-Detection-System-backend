"""
TensorFlow Model Service - Restored & Updated
Service สำหรับโหลดและใช้งานโมเดล TensorFlow วิเคราะห์รูปภาพโรคพืชและศัตรูพืช
รองรับ Image Preprocessing และ Test Time Augmentation (TTA) เพื่อความแม่นยำสูง
"""

import os
import json
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logging.getLogger(__name__).warning("OpenCV not available. Smart cropping disabled.")

try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    logging.getLogger(__name__).warning("rembg not available. Background removal disabled.")

logger = logging.getLogger(__name__)

# ============================================
# Model Configuration
# ============================================
BASE_DIR = Path("D:/pang/project/backend_fastapi")
# ใช้โมเดล round3 ตามที่ระบบปัจจุบันใช้
MODEL_PATH = BASE_DIR / "models" / "model_round3.h5"
CLASS_NAMES_PATH = BASE_DIR / "models" / "class_names_round3.json"
IMG_SIZE = 160  # ขนาดรูปภาพที่โมเดลต้องการ

# ============================================
# Class Mapping (16 Classes)
# แมปชื่อคลาสจากโมเดลไปยังข้อมูลโรค/ศัตรูพืช
# ============================================
CLASS_MAPPING = {
    "Anthracnose": {
        "name_th": "โรคแอนแทรคโนส",
        "name_en": "Anthracnose",
        "category": "disease",
        "type": "1",
    },
    "Bemisia tabaci": {
        "name_th": "แมลงหวี่ขาว",
        "name_en": "Bemisia tabaci",
        "category": "pest",
        "type": "2",
    },
    "Cercospora Leaf Spot": {
        "name_th": "โรคแผลวงกลมสีน้ำตาลไหม้",
        "name_en": "Cercospora Leaf Spot",
        "category": "disease",
        "type": "1",
    },
    "Common Cutworm": {
        "name_th": "หนอนกระทู้ผัก",
        "name_en": "Common Cutworm",
        "category": "pest",
        "type": "2",
    },
    "Diamondback Moth": {
        "name_th": "หนอนใยผัก",
        "name_en": "Diamondback Moth",
        "category": "pest",
        "type": "2",
    },
    "Downy Mildew": {
        "name_th": "โรคราน้ำค้าง",
        "name_en": "Downy Mildew",
        "category": "disease",
        "type": "1",
    },
    "Flea Beetle": {
        "name_th": "ด้วงหมัดผัก",
        "name_en": "Flea Beetle",
        "category": "pest",
        "type": "2",
    },
    "Leaf Blight": {
        "name_th": "โรคใบไหม้",
        "name_en": "Leaf Blight",
        "category": "disease",
        "type": "1",
    },
    "Leaf Miner": {
        "name_th": "หนอนชอนใบ",
        "name_en": "Leaf Miner",
        "category": "pest",
        "type": "2",
    },
    "Leaf Spot Disease": {
        "name_th": "โรคใบจุด",
        "name_en": "Leaf Spot Disease",
        "category": "disease",
        "type": "1",
    },
    "Leafhopper": {
        "name_th": "เพลี้ยจักจั่น",
        "name_en": "Leafhopper",
        "category": "pest",
        "type": "2",
    },
    "Powdery Mildew": {
        "name_th": "โรคราแป้ง",
        "name_en": "Powdery Mildew",
        "category": "disease",
        "type": "1",
    },
    "Red Pumpkin Beetle": {
        "name_th": "ด้วงเต่าแตงแดง",
        "name_en": "Red Pumpkin Beetle",
        "category": "pest",
        "type": "2",
    },
    "Rust Disease": {
        "name_th": "โรคราสนิม",
        "name_en": "Rust Disease",
        "category": "disease",
        "type": "1",
    },
    "Thrips": {
        "name_th": "เพลี้ยไฟ",
        "name_en": "Thrips",
        "category": "pest",
        "type": "2",
    },
    "White Rust Disease": {
        "name_th": "โรคราสนิมขาว",
        "name_en": "White Rust Disease",
        "category": "disease",
        "type": "1",
    },
}

class ResultValidator:
    """Validator สำหรับตรวจสอบความสอดคล้องของผลการทำนาย"""
    
    DISEASE_LOOKING_LIKE_PEST = {"Leaf Spot Disease", "Leaf Blight", "Cercospora Leaf Spot"}
    PEST_LOOKING_LIKE_DISEASE = {"Leaf Miner", "Flea Beetle"}
    
    @classmethod
    def validate_prediction_consistency(cls, results: List[Dict], pred_probs: np.ndarray, class_names: List[str]) -> Dict:
        if len(results) < 2:
            return {"is_consistent": True, "warnings": []}
        
        warnings = []
        primary = results[0]
        secondary = results[1]
        
        primary_category = primary.get("category", "unknown")
        secondary_category = secondary.get("category", "unknown")
        primary_conf = primary.get("confidence", 0)
        secondary_conf = secondary.get("confidence", 0)
        
        category_conflict = (primary_category != secondary_category and 
                            primary_category in ["disease", "pest"] and
                            secondary_category in ["disease", "pest"])
        
        if category_conflict:
            confidence_gap = abs(primary_conf - secondary_conf)
            if confidence_gap < 0.15:
                warnings.append({
                    "type": "category_conflict",
                    "level": "high",
                    "message": f"โมเดลสับสนระหว่าง{cls._get_category_name(primary_category)}กับ{cls._get_category_name(secondary_category)}",
                    "suggestion": "ควรถ่ายรูปเพิ่มหรือตรวจสอบด้วยตาเปล่า",
                })
        
        # Calculate category confidence
        disease_confidence = sum(float(pred_probs[i]) for i, name in enumerate(class_names) 
                                if CLASS_MAPPING.get(name, {}).get("category") == "disease")
        pest_confidence = sum(float(pred_probs[i]) for i, name in enumerate(class_names) 
                             if CLASS_MAPPING.get(name, {}).get("category") == "pest")
        
        return {
            "is_consistent": len(warnings) == 0,
            "warnings": warnings,
            "category_analysis": {
                "disease_total_confidence": round(float(disease_confidence), 4),
                "pest_total_confidence": round(float(pest_confidence), 4),
                "category_confidence_ratio": round(float(max(disease_confidence, pest_confidence) / (disease_confidence + pest_confidence + 1e-7)), 4),
            },
            "has_category_conflict": category_conflict,
        }
    
    @staticmethod
    def _get_category_name(category: str) -> str:
        return "โรคพืช" if category == "disease" else "ศัตรูพืช" if category == "pest" else category

class ImagePreprocessor:
    """ตัวปรับแต่งรูปภาพสำหรับโมเดล"""
    
    @staticmethod
    def preprocess_for_model(image_path: str, enhance: bool = True) -> Image.Image:
        img = Image.open(image_path).convert('RGB')
        if not enhance:
            return img
        
        # ปรับ White Balance พื้นฐาน
        img_array = np.array(img).astype(np.float32)
        avg = np.mean(img_array, axis=(0, 1))
        img_array = np.clip(img_array * (np.mean(avg) / (avg + 1e-6)), 0, 255)
        img = Image.fromarray(img_array.astype(np.uint8))
        
        # ปรับ Contrast & Sharpness
        img = ImageOps.autocontrast(img, cutoff=1)
        img = ImageEnhance.Contrast(img).enhance(1.1)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        
        return img

class TensorFlowModelService:
    _instance = None
    _model = None
    _class_names = None
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._is_loaded:
            self.load_model()

    def load_model(self) -> bool:
        try:
            import tensorflow as tf
            if not MODEL_PATH.exists():
                logger.error(f"Model file not found: {MODEL_PATH}")
                return False

            self._model = tf.keras.models.load_model(str(MODEL_PATH))
            
            if CLASS_NAMES_PATH.exists():
                with open(CLASS_NAMES_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._class_names = [data[str(i)] for i in range(len(data))]
            else:
                self._class_names = list(CLASS_MAPPING.keys())
            
            self._is_loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def is_ready(self) -> bool:
        return self._is_loaded and self._model is not None

    def preprocess_image(self, image_path: str, enhance: bool = False) -> Optional[np.ndarray]:
        try:
            from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
            img = ImagePreprocessor.preprocess_for_model(image_path, enhance=enhance)
            img_resized = img.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS)
            img_array = np.array(img_resized, dtype=np.float32)
            
            # ใช้ preprocess_input ของ MobileNetV2 ตามที่ระบุว่าสำคัญ
            img_array = preprocess_input(img_array)
            return np.expand_dims(img_array, axis=0)
        except Exception as e:
            logger.error(f"Error preprocessing: {e}")
            return None

    def predict_with_tta(self, image_path: str, enhance: bool = True) -> Optional[np.ndarray]:
        try:
            img = ImagePreprocessor.preprocess_for_model(image_path, enhance=enhance)
            img_resized = img.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS)
            
            all_preds = []
            # Orignal, H-Flip, V-Flip
            variants = [
                img_resized,
                img_resized.transpose(Image.FLIP_LEFT_RIGHT),
                img_resized.transpose(Image.FLIP_TOP_BOTTOM)
            ]
            
            from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
            for v in variants:
                arr = preprocess_input(np.array(v, dtype=np.float32))
                pred = self._model.predict(np.expand_dims(arr, axis=0), verbose=0)
                all_preds.append(pred[0])
            
            return np.mean(all_preds, axis=0)
        except Exception as e:
            logger.error(f"TTA Error: {e}")
            return None

    def predict(
        self, 
        image_path: str, 
        use_tta: bool = False,      # Optimized: TTA makes results worse
        enhance: bool = False,      # Optimized: Enhancement makes results worse
        confidence_threshold: float = 0.4  # Optimized: Best accuracy (80%)
    ) -> Optional[Dict]:
        if not self.is_ready(): return None

        try:
            if use_tta:
                pred_probs = self.predict_with_tta(image_path, enhance=enhance)
            else:
                img_arr = self.preprocess_image(image_path, enhance=enhance)
                if img_arr is None: return None
                pred_probs = self._model.predict(img_arr, verbose=0)[0]

            top_3_idx = np.argsort(pred_probs)[-3:][::-1]
            results = []
            for idx in top_3_idx:
                name = self._class_names[idx]
                info = CLASS_MAPPING.get(name, {})
                results.append({
                    "class_name": name,
                    "name_th": info.get("name_th", name),
                    "name_en": info.get("name_en", name),
                    "confidence": float(pred_probs[idx]),
                    "confidence_percent": round(float(pred_probs[idx]) * 100, 2),
                    "category": info.get("category", "unknown"),
                })

            primary = results[0]
            is_detected = primary["confidence"] >= confidence_threshold
            uncertainty = float(pred_probs[top_3_idx[0]] - pred_probs[top_3_idx[1]])
            validation = ResultValidator.validate_prediction_consistency(results, pred_probs, self._class_names)

            # ถ้าความมั่นใจต่ำกว่า threshold ถือว่าเป็นพืชสุขภาพดี (Healthy)
            if not is_detected:
                healthy_confidence = 1.0 - primary["confidence"]
                return {
                    "success": True,
                    "is_detected": False,
                    "is_healthy": True,
                    "is_uncertain": False,
                    "primary": {
                        "class_name": "Healthy",
                        "name_th": "พืชสุขภาพดี",
                        "name_en": "Healthy",
                        "confidence": float(healthy_confidence),
                        "confidence_percent": round(healthy_confidence * 100, 2),
                        "category": "healthy",
                        "adjusted_confidence_percent": round(healthy_confidence * 100, 2)
                    },
                    "top_3": results,  # ยังคงส่ง top 3 จริงกลับไปเพื่อ debug
                    "preprocessing": {"enhanced": enhance, "tta": use_tta},
                    "validation": validation,
                    "uncertainty_score": round(uncertainty, 4),
                    "message": "ความมั่นใจต่ำกว่าเกณฑ์ ระบบจึงระบุว่าเป็นพืชสุขภาพดี"
                }

            return {
                "success": True,
                "is_detected": True,
                "is_healthy": False,
                "is_uncertain": bool(uncertainty < 0.2),
                "primary": {
                    **primary,
                    "adjusted_confidence_percent": primary["confidence_percent"]
                },
                "top_3": results,
                "preprocessing": {"enhanced": enhance, "tta": use_tta},
                "validation": validation,
                "uncertainty_score": round(uncertainty, 4)
            }
        except Exception as e:
            logger.error(f"Predict error: {e}")
            return {"success": False, "error": str(e)}

    def get_model_info(self) -> Dict:
        return {"loaded": self.is_ready(), "model": "model_round3.h5"}

_service = None
def get_tf_model_service():
    global _service
    if _service is None: _service = TensorFlowModelService()
    return _service

def analyze_with_tensorflow(image_path, use_tta=True, enhance=True, confidence_threshold=0.5):
    service = get_tf_model_service()
    return service.predict(image_path, use_tta=use_tta, enhance=enhance, confidence_threshold=confidence_threshold)
