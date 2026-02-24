"""
TensorFlow Model Service - Updated for model_round3.h5
Service สำหรับโหลดและใช้งานโมเดล TensorFlow วิเคราะห์รูปภาพโรคพืชและศัตรูพืช
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
# Model Configuration - UPDATED
# ============================================
BASE_DIR = Path(__file__).parent.parent  # backend_fastapi root
MODEL_PATH = BASE_DIR / "models" / "model_round3.h5"
CLASS_NAMES_PATH = BASE_DIR / "models" / "class_names_round3.json"
IMG_SIZE = 160  # ขนาดรูปภาพที่โมเดลต้องการ

# Load class names from JSON
CLASS_NAMES = []
if CLASS_NAMES_PATH.exists():
    with open(CLASS_NAMES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        CLASS_NAMES = [data[str(i)] for i in range(len(data))]
    logger.info(f"Loaded {len(CLASS_NAMES)} classes from JSON")
else:
    logger.error(f"Class names file not found: {CLASS_NAMES_PATH}")

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
    """
    Validator สำหรับตรวจสอบความสอดคล้องของผลการทำนาย
    """
    
    DISEASE_LOOKING_LIKE_PEST = {
        "Leaf Spot Disease",
        "Leaf Blight",
        "Cercospora Leaf Spot",
    }
    
    PEST_LOOKING_LIKE_DISEASE = {
        "Leaf Miner",
        "Flea Beetle",
    }
    
    @classmethod
    def validate_prediction_consistency(cls, results: List[Dict], pred_probs: np.ndarray, class_names: List[str]) -> Dict:
        """ตรวจสอบความสอดคล้องระหว่าง top predictions"""
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
                    "confidence_gap": round(float(confidence_gap), 3),
                })
            elif confidence_gap < 0.30:
                warnings.append({
                    "type": "category_conflict",
                    "level": "medium",
                    "message": f"โมเดลอาจสับสนระหว่าง{cls._get_category_name(primary_category)}กับ{cls._get_category_name(secondary_category)}",
                    "suggestion": "พิจารณาดูอาการเพิ่มเติม",
                    "confidence_gap": round(float(confidence_gap), 3),
                })
        
        primary_class = primary.get("class_name", "")
        if primary_class in cls.DISEASE_LOOKING_LIKE_PEST and primary_category == "disease":
            has_pest_in_top3 = any(r.get("category") == "pest" for r in results)
            if has_pest_in_top3:
                warnings.append({
                    "type": "look_alike",
                    "level": "medium",
                    "message": "อาการนี้อาจดูคล้ายแมลงกัด โปรดตรวจสอบว่ามีตัวแมลงหรือรอยกัดจริงหรือไม่",
                    "suggestion": "ถ้าพบตัวแมลงหรือรูกัด อาจเป็นศัตรูพืชมากกว่าโรค",
                })
        
        elif primary_class in cls.PEST_LOOKING_LIKE_DISEASE and primary_category == "pest":
            has_disease_in_top3 = any(r.get("category") == "disease" for r in results)
            if has_disease_in_top3:
                warnings.append({
                    "type": "look_alike",
                    "level": "medium",
                    "message": "อาการนี้อาจดูคล้ายโรคใบ โปรดตรวจสอบว่ามีตัวแมลงหรือไม่",
                    "suggestion": "ถ้าไม่พบตัวแมลง อาจเป็นโรคใบมากกว่าศัตรูพืช",
                })
        
        disease_confidence = sum(
            float(pred_probs[i]) for i, name in enumerate(class_names)
            if CLASS_MAPPING.get(name, {}).get("category") == "disease"
        )
        pest_confidence = sum(
            float(pred_probs[i]) for i, name in enumerate(class_names)
            if CLASS_MAPPING.get(name, {}).get("category") == "pest"
        )
        
        category_analysis = {
            "disease_total_confidence": round(float(disease_confidence), 4),
            "pest_total_confidence": round(float(pest_confidence), 4),
            "predicted_category": primary_category,
            "category_confidence_ratio": round(float(max(disease_confidence, pest_confidence) / (disease_confidence + pest_confidence + 1e-7)), 4),
        }
        
        return {
            "is_consistent": len(warnings) == 0,
            "warnings": warnings,
            "category_analysis": category_analysis,
            "has_category_conflict": category_conflict,
        }
    
    @staticmethod
    def _get_category_name(category: str) -> str:
        """แปลง category code เป็นภาษาไทย"""
        return "โรคพืช" if category == "disease" else "ศัตรูพืช" if category == "pest" else category


class TensorFlowModelService:
    """
    Singleton Service สำหรับจัดการโมเดล TensorFlow
    """
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
        """โหลดโมเดล TensorFlow จากไฟล์ .h5"""
        try:
            import tensorflow as tf
            from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
            
            if not MODEL_PATH.exists():
                logger.error(f"Model file not found: {MODEL_PATH}")
                return False

            logger.info(f"Loading TensorFlow model from: {MODEL_PATH}")
            
            # โหลดโมเดล
            self._model = tf.keras.models.load_model(str(MODEL_PATH))
            
            # ใช้ class names จาก JSON
            self._class_names = CLASS_NAMES if CLASS_NAMES else list(CLASS_MAPPING.keys())
            
            self._is_loaded = True
            logger.info(f"TensorFlow model loaded successfully!")
            logger.info(f"   - Input shape: {self._model.input_shape}")
            logger.info(f"   - Output classes: {len(self._class_names)}")
            logger.info(f"   - Classes: {', '.join(self._class_names)}")
            
            return True
            
        except ImportError:
            logger.error("TensorFlow not installed. Run: pip install tensorflow")
            return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def is_ready(self) -> bool:
        """ตรวจสอบว่าโมเดลพร้อมใช้งานหรือไม่"""
        return self._is_loaded and self._model is not None

    def preprocess_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        ประมวลผลรูปภาพก่อนนำเข้าโมเดล
        ใช้ preprocess_input ของ MobileNetV2
        """
        try:
            from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
            
            # โหลดรูปภาพ
            img = Image.open(image_path).convert('RGB')
            
            # Resize ให้ตรงกับขนาดที่โมเดลต้องการ
            img_resized = img.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.BILINEAR)
            
            # แปลงเป็น numpy array
            img_array = np.array(img_resized, dtype=np.float32)
            
            # ใช้ preprocess_input ของ MobileNetV2 (สำคัญ!)
            img_array = preprocess_input(img_array)
            
            # เพิ่ม batch dimension (1, 160, 160, 3)
            img_array = np.expand_dims(img_array, axis=0)
            
            return img_array
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return None
    
    def predict(
        self, 
        image_path: str, 
        confidence_threshold: float = 0.5
    ) -> Optional[Dict]:
        """
        ทำนายรูปภาพด้วยโมเดล TensorFlow
        """
        if not self.is_ready():
            logger.error("Model not loaded")
            return None

        try:
            logger.info(f"Predicting image: {image_path}")
            
            # Preprocess
            img_array = self.preprocess_image(image_path)
            if img_array is None:
                return None
            
            # Predict
            predictions = self._model.predict(img_array, verbose=0)
            pred_probs = predictions[0]
            
            # หา top 3 predictions
            top_3_indices = np.argsort(pred_probs)[-3:][::-1]
            
            # สร้างผลลัพธ์
            results = []
            for idx in top_3_indices:
                class_name = self._class_names[idx]
                class_info = CLASS_MAPPING.get(class_name, {})
                
                results.append({
                    "class_name": class_name,
                    "name_th": class_info.get("name_th", class_name),
                    "name_en": class_info.get("name_en", class_name),
                    "confidence": float(pred_probs[idx]),
                    "confidence_percent": round(float(pred_probs[idx]) * 100, 2),
                    "category": class_info.get("category", "unknown"),
                    "type": class_info.get("type", "0"),
                })
            
            # ตรวจสอบความสอดคล้อง
            validation = ResultValidator.validate_prediction_consistency(
                results, pred_probs, self._class_names
            )
            
            # ตรวจสอบว่าเป็น Healthy หรือไม่ (ใช้ threshold)
            is_healthy = results[0]["confidence"] < confidence_threshold
            
            return {
                "success": True,
                "predictions": results,
                "primary_prediction": results[0],
                "is_healthy": is_healthy,
                "validation": validation,
                "model_version": "model_round3",
            }
            
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return None
    
    def get_model_info(self) -> Dict:
        """ข้อมูลเกี่ยวกับโมเดล"""
        return {
            "loaded": self.is_ready(),
            "model_path": str(MODEL_PATH),
            "num_classes": len(self._class_names) if self._class_names else 0,
            "input_size": IMG_SIZE,
            "classes": self._class_names,
            "version": "model_round3",
        }


# Global instance
_tf_service = None

def get_tf_model_service() -> TensorFlowModelService:
    """Get or create TensorFlow model service instance"""
    global _tf_service
    if _tf_service is None:
        _tf_service = TensorFlowModelService()
    return _tf_service


# ฟังก์ชันสำหรับเรียกใช้งานง่าย
def analyze_with_tensorflow(image_path: str, confidence_threshold: float = 0.5) -> Optional[Dict]:
    """
    วิเคราะห์รูปภาพด้วย TensorFlow Model
    
    Args:
        image_path: Path ของรูปภาพ
        confidence_threshold: เกณฑ์ความมั่นใจขั้นต่ำ (ค่าต่ำกว่านี้ = Healthy)
        
    Returns:
        Dictionary ผลลัพธ์การทำนาย
    """
    service = get_tf_model_service()
    return service.predict(image_path, confidence_threshold=confidence_threshold)
