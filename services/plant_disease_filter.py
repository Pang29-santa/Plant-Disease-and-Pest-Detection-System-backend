"""
Plant Disease Classification with Insect Detection Filter
ระบบกรองผลลัพธ์โมเดลเพื่อแก้ปัญหาแมลงถูกจำแนกเป็นโรคพืช

ข้อจำกัดของโมเดลเดิม:
- ไม่มี class "insect" หรือ "unknown" ในการเทรน
- โมเดลถูกฝึกมาแค่ 3 classes: [mosaic, powdery, healthy]
- เมื่อเจอแมลง โมเดลจะ force fit ให้เป็น 1 ใน 3 classes

แนวทางแก้ไข (Backend-only):
1. Confidence Threshold - กรองผลที่โมเดลไม่มั่นใจ
2. Top-2 Comparison - ตรวจสอบความแตกต่างระหว่างอันดับ 1-2
3. Visual Feature Analysis - วิเคราะห์ลักษณะภาพเพิ่มเติม
4. Post-processing Override - แก้ไขผลตามเงื่อนไข
"""

import cv2
import numpy as np
import tensorflow as tf
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PredictionStatus(Enum):
    """สถานะการทำนาย"""
    CONFIDENT = "confident"           # มั่นใจสูง
    UNCERTAIN = "uncertain"           # ไม่มั่นใจ
    POSSIBLE_INSECT = "possible_insect"  # อาจเป็นแมลง
    UNKNOWN = "unknown"               # ไม่ทราบ
    OVERRIDE_HEALTHY = "override_healthy"  # บังคับเป็น healthy


@dataclass
class FilterConfig:
    """Configuration สำหรับการกรอง"""
    # 1. Confidence Threshold
    min_confidence: float = 0.60      # ขั้นต่ำที่ยอมรับได้
    
    # 2. Top-2 Comparison
    min_confidence_gap: float = 0.15  # ความต่างขั้นต่ำระหว่างอันดับ 1-2
    
    # 3. Visual Analysis
    min_lesion_area_ratio: float = 0.02  # พื้นที่ผิดปกติขั้นต่ำ (% ของภาพ)
    max_insect_like_spots: int = 50      # จำนวนจุดสูงสุดที่ยังถือเป็นโรค (มากกว่านี้อาจเป็นแมลง)
    
    # 4. Post-processing
    auto_override_low_conf: bool = True   # บังคับเป็น healthy ถ้า confidence ต่ำ
    low_conf_threshold: float = 0.40      # เกณฑ์ความมั่นใจต่ำ


class ImagePreprocessor:
    """Preprocessing ที่ถูกต้องตามการเทรน"""
    
    TARGET_SIZE = (224, 224)  # ปรับตามขนาดที่เทรน
    
    @classmethod
    def preprocess(cls, image_path: str) -> np.ndarray:
        """
        Preprocess ภาพให้เหมือนตอน train
        
        Steps:
        1. อ่านภาพ (BGR → RGB)
        2. Resize ให้ตรงขนาด
        3. Normalize (0-1 หรือ -1 ถึง 1)
        4. Data type conversion
        """
        # 1. อ่านภาพ
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 2. Auto brightness/contrast adjustment
        img = cls._auto_adjust(img)
        
        # 3. Resize (ใช้ INTER_AREA สำหรับ downscale จะได้ไม่ blurry)
        img = cv2.resize(img, cls.TARGET_SIZE, interpolation=cv2.INTER_AREA)
        
        # 4. Normalize (ตามที่ใช้ตอน train)
        # ถ้าใช้ preprocess_input ของ MobileNet/ResNet:
        # img = tf.keras.applications.mobilenet_v2.preprocess_input(img)
        # ถ้า normalize ธรรมดา 0-1:
        img = img.astype(np.float32) / 255.0
        
        # 5. Expand dimension สำหรับ batch
        img = np.expand_dims(img, axis=0)
        
        return img
    
    @staticmethod
    def _auto_adjust(img: np.ndarray) -> np.ndarray:
        """ปรับ brightness/contrast อัตโนมัติ"""
        # Convert to LAB color space เพื่อปรับแสง
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # ช่วยให้ภาพที่แสงไม่ดีดูชัดขึ้น
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        
        # Merge กลับ
        lab = cv2.merge([l_channel, a_channel, b_channel])
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return img


class VisualFeatureAnalyzer:
    """วิเคราะห์ลักษณะภาพเพื่อแยกโรคกับแมลง"""
    
    @staticmethod
    def analyze(image_path: str) -> Dict:
        """
        วิเคราะห์ลักษณะภาพ
        
        Returns:
            {
                'total_lesion_area_ratio': float,  # พื้นที่ผิดปกติ/พื้นที่ทั้งหมด
                'num_spots': int,                  # จำนวนจุดแยกกัน
                'avg_spot_size': float,            # ขนาดจุดเฉลี่ย
                'is_scattered': bool,              # กระจายหรือรวมกัน
                'suspicious_insect': bool,         # น่าสงสัยว่าเป็นแมลง
            }
        """
        img = cv2.imread(image_path)
        if img is None:
            return {}
        
        # Convert to HSV สำหรับวิเคราะห์สี
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # หาพื้นที่ผิดปกติ (สีไม่เขียวสุขภาพดี)
        # ช่วงสีเขียวสุขภาพดี
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        # Mask พื้นที่ไม่ใช่สีเขียว (อาจเป็นโรคหรือแมลง)
        healthy_mask = cv2.inRange(hsv, lower_green, upper_green)
        non_healthy_mask = cv2.bitwise_not(healthy_mask)
        
        # ตัด noise ออก
        kernel = np.ones((5, 5), np.uint8)
        non_healthy_mask = cv2.morphologyEx(non_healthy_mask, cv2.MORPH_OPEN, kernel)
        non_healthy_mask = cv2.morphologyEx(non_healthy_mask, cv2.MORPH_CLOSE, kernel)
        
        # หาพื้นที่
        total_pixels = img.shape[0] * img.shape[1]
        lesion_pixels = np.sum(non_healthy_mask > 0)
        lesion_ratio = lesion_pixels / total_pixels
        
        # หาจำนวนจุดแยกกัน (connected components)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            non_healthy_mask, connectivity=8
        )
        
        # ไม่นับ background (index 0)
        num_spots = max(0, num_labels - 1)
        
        # ขนาดจุดเฉลี่ย (ไม่นับ background)
        if num_spots > 0:
            areas = stats[1:, cv2.CC_STAT_AREA]  # Skip background
            avg_spot_size = np.mean(areas)
            
            # ถ้าจุดเล็กมากๆ และเยอะมาก → น่าจะเป็นรอยกัดของแมลง
            small_spots = np.sum(areas < 100)  # จุดเล็กกว่า 100 pixels
            suspicious_insect = (small_spots > 20) or (num_spots > 50 and avg_spot_size < 200)
        else:
            avg_spot_size = 0
            suspicious_insect = False
        
        # ตรวจสอบการกระจาย (scattered vs clustered)
        if num_spots > 1:
            # คำนวณระยะห่างเฉลี่ยระหว่างจุด
            distances = []
            for i in range(len(centroids[1:])):
                for j in range(i + 1, len(centroids[1:])):
                    dist = np.linalg.norm(centroids[i + 1] - centroids[j + 1])
                    distances.append(dist)
            
            avg_distance = np.mean(distances) if distances else 0
            is_scattered = avg_distance > (min(img.shape[:2]) * 0.1)  # กระจายถ้าห่างกัน > 10% ของภาพ
        else:
            is_scattered = False
        
        return {
            'total_lesion_area_ratio': float(lesion_ratio),
            'num_spots': int(num_spots),
            'avg_spot_size': float(avg_spot_size),
            'is_scattered': bool(is_scattered),
            'suspicious_insect': bool(suspicious_insect),
        }


class PredictionFilter:
    """ระบบกรองผลลัพธ์หลังจากโมเดลทำนาย"""
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        self.classes = ['mosaic', 'powdery', 'healthy']
    
    def filter(
        self, 
        predictions: np.ndarray, 
        image_path: str
    ) -> Dict:
        """
        กรองผลลัพธ์จากโมเดล
        
        Args:
            predictions: softmax output จากโมเดล [prob_mosaic, prob_powdery, prob_healthy]
            image_path: path ของภาพ (สำหรับวิเคราะห์เพิ่ม)
            
        Returns:
            ผลลัพธ์ที่ผ่านการกรองพร้อม metadata
        """
        # เรียงลำดับความน่าจะเป็น
        sorted_indices = np.argsort(predictions)[::-1]
        top1_idx = sorted_indices[0]
        top2_idx = sorted_indices[1]
        
        top1_prob = float(predictions[top1_idx])
        top2_prob = float(predictions[top2_idx])
        confidence_gap = top1_prob - top2_prob
        
        # วิเคราะห์ลักษณะภาพ
        visual_features = VisualFeatureAnalyzer.analyze(image_path)
        
        result = {
            'original_prediction': self.classes[top1_idx],
            'original_confidence': top1_prob,
            'all_probabilities': {
                cls: float(prob) 
                for cls, prob in zip(self.classes, predictions)
            },
            'visual_features': visual_features,
        }
        
        # ============================================
        # 1. Confidence Threshold Filtering
        # ============================================
        if top1_prob < self.config.min_confidence:
            result.update({
                'final_prediction': 'uncertain',
                'status': PredictionStatus.UNCERTAIN.value,
                'reason': f'Confidence {top1_prob:.3f} < threshold {self.config.min_confidence}',
                'suggestion': 'ถ่ายภาพใหม่หรือตรวจสอบด้วยตาเปล่า',
            })
            return result
        
        # ============================================
        # 2. Top-2 Comparison
        # ============================================
        if confidence_gap < self.config.min_confidence_gap:
            result.update({
                'final_prediction': 'possible_insect_or_unknown',
                'status': PredictionStatus.POSSIBLE_INSECT.value,
                'reason': f'Top-1 and Top-2 too close ({confidence_gap:.3f} < {self.config.min_confidence_gap})',
                'top_2_alternatives': [
                    {'class': self.classes[top1_idx], 'prob': top1_prob},
                    {'class': self.classes[top2_idx], 'prob': top2_prob},
                ],
                'suggestion': 'โมเดลสับสนระหว่างโรค อาจเป็นแมลงหรือภาพไม่ชัดเจน',
            })
            return result
        
        # ============================================
        # 3. Rule-based Filtering (Visual Features)
        # ============================================
        if visual_features.get('suspicious_insect', False):
            # ถ้าโมเดลบอกเป็นโรค แต่ลักษณะเหมือนแมลง
            if self.classes[top1_idx] in ['mosaic', 'powdery']:
                result.update({
                    'final_prediction': 'possible_insect',
                    'status': PredictionStatus.POSSIBLE_INSECT.value,
                    'reason': 'Visual features suggest insect damage (many small spots)',
                    'model_prediction': self.classes[top1_idx],
                    'model_confidence': top1_prob,
                    'suggestion': 'พบจุดเล็กจำนวนมาก อาจเป็นรอยกัดของแมลง ควรตรวจหาตัวแมลง',
                })
                return result
        
        # ตรวจสอบพื้นที่ผิดปกติน้อยเกินไป
        if visual_features.get('total_lesion_area_ratio', 0) < self.config.min_lesion_area_ratio:
            if self.classes[top1_idx] in ['mosaic', 'powdery']:
                result.update({
                    'final_prediction': 'healthy_or_minor_damage',
                    'status': PredictionStatus.OVERRIDE_HEALTHY.value,
                    'reason': f'Lesion area too small ({visual_features["total_lesion_area_ratio"]:.4f})',
                    'suggestion': 'พื้นที่ผิดปกติน้อย อาจเป็นสุขภาพดีหรือความเสียหายเล็กน้อย',
                })
                return result
        
        # ============================================
        # 4. Post-processing Override
        # ============================================
        if self.config.auto_override_low_conf:
            if top1_prob < self.config.low_conf_threshold:
                result.update({
                    'final_prediction': 'healthy',
                    'status': PredictionStatus.OVERRIDE_HEALTHY.value,
                    'reason': f'Low confidence ({top1_prob:.3f}), override to healthy',
                    'model_prediction': self.classes[top1_idx],
                })
                return result
        
        # ============================================
        # 5. Pass (Confident Prediction)
        # ============================================
        result.update({
            'final_prediction': self.classes[top1_idx],
            'status': PredictionStatus.CONFIDENT.value,
            'confidence': top1_prob,
            'message': 'ผลลัพธ์น่าเชื่อถือ',
        })
        
        return result


class PlantDiseaseClassifier:
    """คลาสหลักสำหรับใช้งาน"""
    
    def __init__(self, model_path: str, config: FilterConfig = None):
        self.model = tf.keras.models.load_model(model_path)
        self.filter = PredictionFilter(config)
        self.preprocessor = ImagePreprocessor()
        
        logger.info(f"Model loaded from: {model_path}")
        logger.info(f"Model input shape: {self.model.input_shape}")
        logger.info(f"Model output shape: {self.model.output_shape}")
    
    def predict(self, image_path: str) -> Dict:
        """
        ทำนายภาพพร้อมกรองผล
        
        Usage:
            classifier = PlantDiseaseClassifier('model.h5')
            result = classifier.predict('image.jpg')
            print(result['final_prediction'])
            print(result['status'])
        """
        # 1. Preprocess
        img = self.preprocessor.preprocess(image_path)
        
        # 2. Model prediction
        predictions = self.model.predict(img, verbose=0)[0]
        
        # 3. Filter results
        result = self.filter.filter(predictions, image_path)
        
        return result


# ============================================
# ตัวอย่างการใช้งาน
# ============================================
if __name__ == "__main__":
    # ตั้งค่า
    config = FilterConfig(
        min_confidence=0.60,
        min_confidence_gap=0.15,
        auto_override_low_conf=True,
        low_confidence_threshold=0.40
    )
    
    # สร้าง classifier
    # classifier = PlantDiseaseClassifier('path/to/model.h5', config)
    
    # ทำนาย
    # result = classifier.predict('path/to/image.jpg')
    # print(result)
    
    pass
