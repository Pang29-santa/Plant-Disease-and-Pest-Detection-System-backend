"""
TensorFlow Model Service
Service สำหรับโหลดและใช้งานโมเดล TensorFlow วิเคราะห์รูปภาพโรคพืชและศัตรูพืช
รองรับ Image Preprocessing และ Test Time Augmentation (TTA) เพื่อแก้ปัญหา Domain Gap
"""

import os
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
    logging.getLogger(__name__).warning("OpenCV not available. Smart cropping disabled. Run: pip install opencv-python")

try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    logging.getLogger(__name__).warning("rembg not available. Background removal disabled. Run: pip install rembg")

logger = logging.getLogger(__name__)

# ============================================
# Model Configuration
# ============================================
MODEL_PATH = Path("D:/pang/project/backend_fastapi/fine_tuned_v2/fine_tuned_v2_final.keras")
IMG_SIZE = 160  # ขนาดรูปภาพที่โมเดลต้องการ

# ============================================
# Class Mapping (16 Classes)
# แมปชื่อคลาสจากโมเดล Fine-tuned ไปยังข้อมูลโรค/ศัตรูพืช
# อ้างอิงจาก fine_tuned_v2 (ความแม่นยำ 98.1%)
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
    แก้ปัญหาโมเดลสับสนระหว่างโรคพืชกับศัตรูพืช
    """
    
    # คลาสที่มักจะสับสนกัน (Confusable Classes)
    # โรคที่มีอาการคล้ายแมลงกัด
    DISEASE_LOOKING_LIKE_PEST = {
        "Leaf_Spot_Disease",  # ใบจุด อาจดูคล้ายรอยกัด
        "Leaf_Blight",        # ใบไหม้ อาจดูคล้ายรอยไหม้จากแมลง
        "Cercospora_Leaf",    # ใบจุดเซอร์โคสpora
    }
    
    # แมลงที่มีอาการคล้ายโรค
    PEST_LOOKING_LIKE_DISEASE = {
        "Leaf_Miner",         # หนอนชอนใบ อาจดูคล้ายเส้นโรค
        "flea_beetle",        # ด้วงหมัดผัก รูกัดเล็กๆ อาจดูคล้ายจุดโรค
    }
    
    @classmethod
    def validate_prediction_consistency(cls, results: List[Dict], pred_probs: np.ndarray, class_names: List[str]) -> Dict:
        """
        ตรวจสอบความสอดคล้องระหว่าง top predictions
        
        Args:
            results: รายการผลลัพธ์ top 3
            pred_probs: ความน่าจะเป็นของทุกคลาส
            class_names: รายชื่อคลาสทั้งหมด
            
        Returns:
            Dictionary ข้อมูลการตรวจสอบ
        """
        if len(results) < 2:
            return {"is_consistent": True, "warnings": []}
        
        warnings = []
        primary = results[0]
        secondary = results[1]
        
        primary_category = primary.get("category", "unknown")
        secondary_category = secondary.get("category", "unknown")
        primary_conf = primary.get("confidence", 0)
        secondary_conf = secondary.get("confidence", 0)
        
        # 1. ตรวจสอบว่า Top 2 เป็นคนละประเภทกัน (โรค vs แมลง) หรือไม่
        category_conflict = (primary_category != secondary_category and 
                            primary_category in ["disease", "pest"] and
                            secondary_category in ["disease", "pest"])
        
        if category_conflict:
            confidence_gap = abs(primary_conf - secondary_conf)
            
            if confidence_gap < 0.15:  # ถ้าความต่างน้อยกว่า 15%
                warnings.append({
                    "type": "category_conflict",
                    "level": "high",
                    "message": f"โมเดลสับสนระหว่าง{cls._get_category_name(primary_category)}กับ{cls._get_category_name(secondary_category)}",
                    "suggestion": "ควรถ่ายรูปเพิ่มหรือตรวจสอบด้วยตาเปล่า",
                    "confidence_gap": round(float(confidence_gap), 3),
                })
            elif confidence_gap < 0.30:  # ถ้าความต่าง 15-30%
                warnings.append({
                    "type": "category_conflict",
                    "level": "medium",
                    "message": f"โมเดลอาจสับสนระหว่าง{cls._get_category_name(primary_category)}กับ{cls._get_category_name(secondary_category)}",
                    "suggestion": "พิจารณาดูอาการเพิ่มเติม",
                    "confidence_gap": round(float(confidence_gap), 3),
                })
        
        # 2. ตรวจสอบว่า primary prediction เป็นคลาสที่มักสับสนหรือไม่
        primary_class = primary.get("class_name", "")
        if primary_class in cls.DISEASE_LOOKING_LIKE_PEST and primary_category == "disease":
            # ตรวจสอบว่ามีแมลงใน top 3 หรือไม่
            has_pest_in_top3 = any(r.get("category") == "pest" for r in results)
            if has_pest_in_top3:
                warnings.append({
                    "type": "look_alike",
                    "level": "medium",
                    "message": "อาการนี้อาจดูคล้ายแมลงกัด โปรดตรวจสอบว่ามีตัวแมลงหรือรอยกัดจริงหรือไม่",
                    "suggestion": "ถ้าพบตัวแมลงหรือรูกัด อาจเป็นศัตรูพืชมากกว่าโรค",
                })
        
        elif primary_class in cls.PEST_LOOKING_LIKE_DISEASE and primary_category == "pest":
            # ตรวจสอบว่ามีโรคใน top 3 หรือไม่
            has_disease_in_top3 = any(r.get("category") == "disease" for r in results)
            if has_disease_in_top3:
                warnings.append({
                    "type": "look_alike",
                    "level": "medium",
                    "message": "อาการนี้อาจดูคล้ายโรคใบ โปรดตรวจสอบว่ามีตัวแมลงหรือไม่",
                    "suggestion": "ถ้าไม่พบตัวแมลง อาจเป็นโรคใบมากกว่าศัตรูพืช",
                })
        
        # 3. คำนวณ category confidence (รวมความมั่นใจของโรคและแมลงแยกกัน)
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


class ImagePreprocessor:
    """
    Preprocessor สำหรับปรับแต่งรูปภาพให้ใกล้เคียงกับ dataset ที่ใช้เทรน
    แก้ปัญหา Domain Gap ระหว่างรูปจริงกับรูปเทรน
    """
    
    @staticmethod
    def center_crop(img: Image.Image, crop_ratio: float = 0.9) -> Image.Image:
        """Crop กึ่งกลางรูปเพื่อโฟกัสที่วัตถุหลัก"""
        width, height = img.size
        new_width = int(width * crop_ratio)
        new_height = int(height * crop_ratio)
        left = (width - new_width) // 2
        top = (height - new_height) // 2
        right = left + new_width
        bottom = top + new_height
        return img.crop((left, top, right, bottom))
    
    @staticmethod
    def auto_contrast(img: Image.Image, cutoff: int = 0) -> Image.Image:
        """ปรับ contrast อัตโนมัติให้สมดุล"""
        return ImageOps.autocontrast(img, cutoff=cutoff)
    
    @staticmethod
    def equalize_histogram(img: Image.Image) -> Image.Image:
        """ปรับ histogram ให้สมดุล"""
        return ImageOps.equalize(img)
    
    @staticmethod
    def adjust_brightness(img: Image.Image, factor: float = 1.0) -> Image.Image:
        """ปรับความสว่าง"""
        enhancer = ImageEnhance.Brightness(img)
        return enhancer.enhance(factor)
    
    @staticmethod
    def adjust_contrast(img: Image.Image, factor: float = 1.0) -> Image.Image:
        """ปรับความคมชัด"""
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)
    
    @staticmethod
    def adjust_sharpness(img: Image.Image, factor: float = 1.0) -> Image.Image:
        """ปรับความคมชัดของขอบ"""
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(factor)
    
    @staticmethod
    def denoise(img: Image.Image) -> Image.Image:
        """ลด noise ในรูปภาพ"""
        return img.filter(ImageFilter.MedianFilter(size=3))
    
    @staticmethod
    def remove_color_cast(img: Image.Image) -> Image.Image:
        """ปรับสีขาวให้เป็นสีขาวจริง (white balance)"""
        # แปลงเป็น numpy array
        img_array = np.array(img).astype(np.float32)
        
        # คำนวณค่าเฉลี่ยของแต่ละช่องสี
        r_mean = np.mean(img_array[:, :, 0])
        g_mean = np.mean(img_array[:, :, 1])
        b_mean = np.mean(img_array[:, :, 2])
        
        # หาค่าเฉลี่ยรวม
        avg = (r_mean + g_mean + b_mean) / 3.0
        
        # ปรับสี
        img_array[:, :, 0] = np.clip(img_array[:, :, 0] * (avg / r_mean), 0, 255)
        img_array[:, :, 1] = np.clip(img_array[:, :, 1] * (avg / g_mean), 0, 255)
        img_array[:, :, 2] = np.clip(img_array[:, :, 2] * (avg / b_mean), 0, 255)
        
        return Image.fromarray(img_array.astype(np.uint8))
    
    @staticmethod
    def remove_background_if_available(img: Image.Image) -> Image.Image:
        """ลบพื้นหลังทิ้งให้เหลือแต่วัตถุหลัก (ต้องติดตั้ง rembg)"""
        if not REMBG_AVAILABLE:
            return img
        try:
            logger.info("Applying background removal...")
            # rembg ต้องการรูปภาพแบบ PIL
            result = remove(img)
            # rembg คืนค่าเป็น RGBA (โปร่งใส) เราต้องซ้อนบนพื้นหลังสีขาว
            background = Image.new("RGB", result.size, (255, 255, 255))
            background.paste(result, mask=result.split()[3]) 
            return background
        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            return img

    @staticmethod
    def smart_crop_if_available(img: Image.Image) -> Image.Image:
        """ครอปภาพหาจุดที่มีสีเขียว/น้ำตาลเยอะที่สุด (ต้องติดตั้ง opencv-python)"""
        if not OPENCV_AVAILABLE:
            return img
        try:
            logger.info("Applying smart crop...")
            # แปลง PIL เป็น OpenCV format (BGR)
            open_cv_image = np.array(img.convert('RGB'))
            open_cv_image = open_cv_image[:, :, ::-1].copy() # RGB to BGR

            # แปลงเป็น HSV
            hsv = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2HSV)

            # สีเขียว
            lower_green = np.array([25, 40, 40])
            upper_green = np.array([90, 255, 255])
            mask_green = cv2.inRange(hsv, lower_green, upper_green)

            # สีน้ำตาล/เหลือง/แดง (โรคมักจะเป็นสีแปลกๆ ท่ามกลางใบสีเขียว)
            lower_brown = np.array([0, 40, 40])
            upper_brown = np.array([25, 255, 255])
            mask_brown = cv2.inRange(hsv, lower_brown, upper_brown)

            full_mask = cv2.bitwise_or(mask_green, mask_brown)

            # หา Contours
            contours, _ = cv2.findContours(full_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return img
                
            x_min, y_min = img.width, img.height
            x_max, y_max = 0, 0
            
            for c in contours:
                if cv2.contourArea(c) < 500: # กรอง noise
                    continue
                x, y, w, h = cv2.boundingRect(c)
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x + w)
                y_max = max(y_max, y + h)
                
            if x_min >= x_max or y_min >= y_max:
                return img
                
            # เพิ่ม padding เล็กน้อย
            pad_w = int((x_max - x_min) * 0.1)
            pad_h = int((y_max - y_min) * 0.1)
            
            x_min = max(0, x_min - pad_w)
            y_min = max(0, y_min - pad_h)
            x_max = min(img.width, x_max + pad_w)
            y_max = min(img.height, y_max + pad_h)
            
            return img.crop((x_min, y_min, x_max, y_max))

        except Exception as e:
            logger.error(f"Smart cropping failed: {e}")
            return img

    @classmethod
    def preprocess_for_model(
        cls, 
        image_path: str, 
        enhance: bool = True,
        remove_bg_tint: bool = True,
        remove_bg: bool = True,
        smart_crop: bool = True
    ) -> Image.Image:
        """
        ประมวลผลรูปภาพแบบสมบูรณ์ก่อนนำเข้าโมเดล
        
        Args:
            image_path: Path ของรูปภาพ
            enhance: ปรับปรุงคุณภาพรูปหรือไม่
            remove_bg_tint: ปรับ white balance หรือไม่
            remove_bg: ลบพื้นหลังให้เหลือแต่พืชหรือไม่
            smart_crop: ครอปเข้าหาเป้าหมายอัตโนมัติหรือไม่
            
        Returns:
            PIL Image ที่ประมวลผลแล้ว
        """
        # โหลดรูปภาพ
        img = Image.open(image_path).convert('RGB')
        
        # [ใหม่] 1. Smart Crop - ครอปโฟกัสเอาเฉพาะใบไม้/รอยโรค
        if smart_crop:
            img = cls.smart_crop_if_available(img)
            
        # [ใหม่] 2. ลบพื้นหลังให้เหลือแต่พืช
        if remove_bg:
            img = cls.remove_background_if_available(img)
        
        if not enhance:
            return img
        
        # 1. ปรับ white balance
        if remove_bg_tint:
            img = cls.remove_color_cast(img)
        
        # 2. ปรับ auto contrast
        img = cls.auto_contrast(img, cutoff=1)
        
        # 3. ปรับ brightness ให้อยู่ในระดับปานกลาง
        img = cls.adjust_brightness(img, factor=1.1)
        
        # 4. ปรับ contrast
        img = cls.adjust_contrast(img, factor=1.1)
        
        # 5. ลด noise
        img = cls.denoise(img)
        
        # 6. ปรับ sharpness
        img = cls.adjust_sharpness(img, factor=1.2)
        
        return img


class TensorFlowModelService:
    """
    Singleton Service สำหรับจัดการโมเดล TensorFlow
    รองรับ Test Time Augmentation (TTA) เพื่อเพิ่มความแม่นยำ
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
        """
        โหลดโมเดล TensorFlow จากไฟล์ .keras
        
        Returns:
            bool: True ถ้าโหลดสำเร็จ, False ถ้าไม่สำเร็จ
        """
        try:
            import tensorflow as tf
            
            if not MODEL_PATH.exists():
                logger.error(f"❌ Model file not found: {MODEL_PATH}")
                return False

            logger.info(f"🔄 Loading TensorFlow model from: {MODEL_PATH}")
            
            # โหลดโมเดล
            self._model = tf.keras.models.load_model(str(MODEL_PATH))
            
            # ดึงชื่อคลาสจาก mapping
            self._class_names = list(CLASS_MAPPING.keys())
            
            self._is_loaded = True
            logger.info(f"✅ TensorFlow model loaded successfully!")
            logger.info(f"   - Input shape: {self._model.input_shape}")
            logger.info(f"   - Output classes: {len(self._class_names)}")
            logger.info(f"   - Classes: {', '.join(self._class_names)}")
            
            return True
            
        except ImportError:
            logger.error("❌ TensorFlow not installed. Run: pip install tensorflow")
            return False
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
            return False

    def is_ready(self) -> bool:
        """ตรวจสอบว่าโมเดลพร้อมใช้งานหรือไม่"""
        return self._is_loaded and self._model is not None

    def preprocess_image(self, image_path: str, enhance: bool = True) -> Optional[np.ndarray]:
        """
        ประมวลผลรูปภาพก่อนนำเข้าโมเดล
        
        Args:
            image_path: Path ของรูปภาพ
            enhance: ปรับปรุงคุณภาพรูปหรือไม่
            
        Returns:
            numpy array ที่พร้อมสำหรับโมเดล หรือ None ถ้ามี error
        """
        try:
            # ใช้ ImagePreprocessor
            img = ImagePreprocessor.preprocess_for_model(image_path, enhance=enhance)
            
            # Resize ให้ตรงกับขนาดที่โมเดลต้องการ
            img_resized = img.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS)
            
            # แปลงเป็น numpy array และ normalize (0-1)
            img_array = np.array(img_resized) / 255.0
            
            # เพิ่ม batch dimension (1, 160, 160, 3)
            img_array = np.expand_dims(img_array, axis=0)
            
            return img_array
            
        except Exception as e:
            logger.error(f"❌ Error preprocessing image: {e}")
            return None
    
    def predict_with_tta(
        self, 
        image_path: str, 
        n_augmentations: int = 5,
        enhance: bool = True
    ) -> Optional[Dict]:
        """
        ทำนายด้วย Test Time Augmentation (TTA)
        ทำนายหลายครั้งด้วยการ augment รูปต่างๆ แล้วเอาเฉลี่ย
        
        Args:
            image_path: Path ของรูปภาพ
            n_augmentations: จำนวนการ augment (default: 5)
            enhance: ปรับปรุงคุณภาพรูปก่อนทำนาย
            
        Returns:
            Dictionary ผลลัพธ์การทำนาย
        """
        if not self.is_ready():
            logger.error("❌ Model not loaded")
            return None
        
        try:
            # โหลดและประมวลผลรูปภาพหลัก
            img = ImagePreprocessor.preprocess_for_model(image_path, enhance=enhance)
            img_resized = img.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS)
            
            all_predictions = []
            
            # 1. ทำนายรูปต้นฉบับ
            img_array = np.array(img_resized) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            pred = self._model.predict(img_array, verbose=0)
            all_predictions.append(pred[0])
            
            # 2. ทำนายด้วยการ flip แนวนอน
            img_flipped_h = img_resized.transpose(Image.FLIP_LEFT_RIGHT)
            img_array = np.array(img_flipped_h) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            pred = self._model.predict(img_array, verbose=0)
            all_predictions.append(pred[0])
            
            # 3. ทำนายด้วยการ flip แนวตั้ง
            img_flipped_v = img_resized.transpose(Image.FLIP_TOP_BOTTOM)
            img_array = np.array(img_flipped_v) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            pred = self._model.predict(img_array, verbose=0)
            all_predictions.append(pred[0])
            
            # 4. ทำนายด้วยการหมุนเล็กน้อย (±5 องศา)
            img_rotated_p5 = img_resized.rotate(5, fillcolor=(128, 128, 128))
            img_array = np.array(img_rotated_p5) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            pred = self._model.predict(img_array, verbose=0)
            all_predictions.append(pred[0])
            
            img_rotated_m5 = img_resized.rotate(-5, fillcolor=(128, 128, 128))
            img_array = np.array(img_rotated_m5) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            pred = self._model.predict(img_array, verbose=0)
            all_predictions.append(pred[0])
            
            # คำนวณค่าเฉลี่ยของทุกการทำนาย
            avg_predictions = np.mean(all_predictions, axis=0)
            
            logger.info(f"🔍 TTA completed with {len(all_predictions)} augmentations")
            
            return avg_predictions
            
        except Exception as e:
            logger.error(f"❌ Error during TTA: {e}")
            return None

    def predict(
        self, 
        image_path: str, 
        use_tta: bool = True,
        enhance: bool = True,
        confidence_threshold: float = 0.5
    ) -> Optional[Dict]:
        """
        ทำนายรูปภาพด้วยโมเดล TensorFlow
        
        Args:
            image_path: Path ของรูปภาพที่ต้องการทำนาย
            use_tta: ใช้ Test Time Augmentation หรือไม่
            enhance: ปรับปรุงคุณภาพรูปหรือไม่
            confidence_threshold: เกณฑ์ความมั่นใจขั้นต่ำ
            
        Returns:
            Dictionary ผลลัพธ์การทำนาย หรือ None ถ้ามี error
        """
        if not self.is_ready():
            logger.error("❌ Model not loaded")
            return None

        try:
            logger.info(f"🔍 Predicting image: {image_path}")
            logger.info(f"   - Use TTA: {use_tta}")
            logger.info(f"   - Enhance: {enhance}")
            
            # ทำนายด้วยหรือไม่มี TTA
            if use_tta:
                pred_probs = self.predict_with_tta(image_path, enhance=enhance)
                if pred_probs is None:
                    # Fallback ถ้า TTA ล้มเหลว
                    img_array = self.preprocess_image(image_path, enhance=enhance)
                    if img_array is None:
                        return None
                    predictions = self._model.predict(img_array, verbose=0)
                    pred_probs = predictions[0]
            else:
                img_array = self.preprocess_image(image_path, enhance=enhance)
                if img_array is None:
                    return None
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

            # ผลลัพธ์หลัก (อันดับ 1)
            primary_result = results[0]
            
            # ตรวจสอบว่าพบโรค/ศัตรูพืชหรือไม่ (ใช้เกณฑ์ที่กำหนด)
            is_detected = bool(primary_result["confidence"] > confidence_threshold)
            
            # คำนวณ uncertainty (ความไม่แน่นอน) จากความแตกต่างระหว่าง top 2
            uncertainty = float(pred_probs[top_3_indices[0]] - pred_probs[top_3_indices[1]])
            is_uncertain = bool(uncertainty < 0.2)  # ถ้าความต่างน้อยกว่า 20% = ไม่แน่ใจ
            
            # ตรวจสอบความสอดคล้องของผลลัพธ์ (โรค vs แมลง)
            validation_result = ResultValidator.validate_prediction_consistency(
                results, pred_probs, self._class_names
            )
            
            # ถ้ามี category conflict และโมเดลไม่แน่ใจ ให้ปรับ is_uncertain
            if validation_result.get("has_category_conflict", False) and uncertainty < 0.25:
                is_uncertain = True
            
            # ปรับ confidence ตาม category analysis
            category_analysis = validation_result.get("category_analysis", {})
            category_conf_ratio = category_analysis.get("category_confidence_ratio", 1.0)
            
            # ถ้าโมเดลมั่นใจในประเภทน้อยกว่า 60% ให้ลด confidence ลง
            adjusted_confidence = primary_result["confidence"]
            if category_conf_ratio < 0.6:
                adjusted_confidence *= 0.8  # ลด confidence 20%
                is_uncertain = True
            
            return {
                "success": True,
                "model": "TensorFlow_MobileNetV2",
                "is_detected": bool(is_detected),
                "is_uncertain": bool(is_uncertain),
                "uncertainty_score": round(float(uncertainty), 4),
                "is_plant": True,
                "primary": {
                    **primary_result,
                    "adjusted_confidence": round(float(adjusted_confidence), 4),
                    "adjusted_confidence_percent": round(float(adjusted_confidence) * 100, 2),
                },
                "top_3": results,
                "all_predictions": [
                    {
                        "class_name": str(self._class_names[i]),
                        "confidence": float(pred_probs[i]),
                        "confidence_percent": round(float(pred_probs[i]) * 100, 2),
                    }
                    for i in range(len(self._class_names))
                ],
                "preprocessing": {
                    "enhanced": bool(enhance),
                    "tta_used": bool(use_tta),
                },
                "validation": validation_result,  # ⭐ ใหม่: ข้อมูลการตรวจสอบ
            }
            
        except Exception as e:
            logger.error(f"❌ Error during prediction: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_model_info(self) -> Dict:
        """ดึงข้อมูลเกี่ยกับโมเดล"""
        return {
            "loaded": self.is_ready(),
            "model_path": str(MODEL_PATH),
            "model_type": "MobileNetV2 (Fine-tuned v2)",
            "accuracy": "98.1%",
            "input_size": IMG_SIZE,
            "num_classes": len(CLASS_MAPPING) if self._class_names else 0,
            "classes": self._class_names,
            "class_mapping": {
                cls: info["name_th"] 
                for cls, info in CLASS_MAPPING.items()
            },
            "features": {
                "tta_supported": True,
                "enhancement_supported": True,
                "uncertainty_estimation": True,
                "smart_crop": OPENCV_AVAILABLE,
                "background_removal": REMBG_AVAILABLE,
            }
        }


# ============================================
# Global Instance
# ============================================
_tf_model_service = None


def get_tf_model_service() -> TensorFlowModelService:
    """Get singleton instance of TensorFlowModelService"""
    global _tf_model_service
    if _tf_model_service is None:
        _tf_model_service = TensorFlowModelService()
    return _tf_model_service


def analyze_with_tensorflow(
    image_path: str,
    use_tta: bool = True,
    enhance: bool = True,
    confidence_threshold: float = 0.5
) -> Dict:
    """
    ฟังก์ชัน wrapper สำหรับวิเคราะห์รูปภาพด้วย TensorFlow
    
    Args:
        image_path: Path ของรูปภาพ
        use_tta: ใช้ Test Time Augmentation หรือไม่
        enhance: ปรับปรุงคุณภาพรูปหรือไม่
        confidence_threshold: เกณฑ์ความมั่นใจขั้นต่ำ
        
    Returns:
        Dictionary ผลลัพธ์การวิเคราะห์
    """
    service = get_tf_model_service()
    
    if not service.is_ready():
        return {
            "success": False,
            "error": "TensorFlow model not loaded. Please check if model file exists.",
        }
    
    result = service.predict(
        image_path, 
        use_tta=use_tta,
        enhance=enhance,
        confidence_threshold=confidence_threshold
    )
    
    if result is None:
        return {
            "success": False,
            "error": "Prediction failed",
        }
    
    return result
