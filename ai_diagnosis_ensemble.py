"""
AI Diagnosis Ensemble System
============================
ระบบชั่งน้ำหนักและรวมผลระหว่าง CNN และ KIMI สำหรับการวินิจฉัยโรคพืช/แมลง

การทำงาน:
1. รับผลลัพธ์จาก CNN (confidence score + class prediction)
2. รับผลลัพธ์จาก KIMI (ผ่าน prompt ที่กำหนด)
3. ชั่งน้ำหนักตามปัจจัยต่างๆ
4. ตัดสินใจสุดท้ายหรือรวมผล
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json


class DiagnosisSource(Enum):
    """แหล่งที่มาของการวินิจฉัย"""
    CNN = "cnn"
    KIMI = "kimi"
    ENSEMBLE = "ensemble"


@dataclass
class CNNPrediction:
    """ผลลัพธ์จาก CNN Model"""
    predicted_class: str
    confidence: float  # 0-1
    top_k: List[Tuple[str, float]]  # Top K predictions with scores
    inference_time_ms: float
    
    def get_top_confidence_gap(self) -> float:
        """คำนวณความต่างระหว่างอันดับ 1 กับ 2"""
        if len(self.top_k) >= 2:
            return self.top_k[0][1] - self.top_k[1][1]
        return 1.0


@dataclass
class KimiPrediction:
    """ผลลัพธ์จาก KIMI (LLM)"""
    predicted_class: str
    raw_response: str
    is_uncertain: bool  # True ถ้าตอบ "No disease or pest found"
    reasoning_quality: float  # 0-1 (คุณภาพของการให้เหตุผล)
    response_time_ms: float


@dataclass
class EnsembleResult:
    """ผลลัพธ์สุดท้ายจาก Ensemble"""
    final_diagnosis: str
    confidence: float
    source: DiagnosisSource
    cnn_weight: float
    kimi_weight: float
    cnn_prediction: Optional[CNNPrediction]
    kimi_prediction: Optional[KimiPrediction]
    reasoning: str
    recommendations: List[str]


class DiagnosisWeightingSystem:
    """
    ระบบชั่งน้ำหนักสำหรับการวินิจฉัยโรคพืช
    """
    
    def __init__(self):
        # น้ำหนักเริ่มต้นสำหรับแต่ละปัจจัย
        self.weights = {
            'cnn_confidence': 0.30,
            'kimi_certainty': 0.25,
            'top_k_separation': 0.15,
            'image_quality': 0.15,
            'class_complexity': 0.15
        }
        
        # ค่า threshold สำหรับการตัดสินใจ
        self.thresholds = {
            'cnn_high_confidence': 0.85,
            'cnn_medium_confidence': 0.60,
            'cnn_uncertain': 0.40,
            'kimi_uncertain_markers': ['no disease', 'not sure', 'unclear', 'cannot'],
            'ensemble_agreement_required': 0.70
        }
        
        # ความซับซ้อนของแต่ละคลาส (ยิ่งสูง = KIMI ยิ่งมีโอกาสถูก)
        self.class_complexity = {
            # Diseases
            'Powdery Mildew': 0.3,      # ง่าย - ผงขาวชัดเจน
            'Downy Mildew': 0.6,        # ปานกลาง - ต้องดูสองด้านใบ
            'Anthracnose': 0.5,         # ปานกลาง
            'Cercospora Leaf Spot': 0.5,
            'Rust Disease': 0.4,        # ตุ่มสนิมค่อนข้างชัด
            'White Rust Disease': 0.6,  # ต้องดูด้านล่างใบ
            'Leaf Blight': 0.4,
            'Leaf Spot Disease': 0.5,
            # Pests
            'Bemisia tabaci': 0.7,      # ยาก - ต้องดูหลาย sign
            'Thrips': 0.7,              # ยาก - ผิวเงินอาจดูยาก
            'Leaf Miner': 0.5,          # เส้นทางค่อนข้างชัด
            'Diamondback Moth': 0.6,
            'Flea Beetle': 0.4,         # รูพรุนค่อนข้างชัด
            'Common Cutworm': 0.4,
            'Red Pumpkin Beetle': 0.5,
            'Leafhopper': 0.6,
        }
    
    def calculate_cnn_weight(self, cnn_pred: CNNPrediction, 
                            image_quality: float = 1.0) -> float:
        """
        คำนวณน้ำหนักสำหรับ CNN
        
        Args:
            cnn_pred: ผลลัพธ์จาก CNN
            image_quality: คุณภาพภาพ (0-1)
        
        Returns:
            float: น้ำหนัก CNN (0-1)
        """
        base_score = cnn_pred.confidence
        
        # Bonus ถ้า top-1 ห่างจาก top-2 มาก (แยกแยะชัดเจน)
        separation_bonus = min(cnn_pred.get_top_confidence_gap() * 0.2, 0.1)
        
        # Penalty ถ้าภาพคุณภาพต่ำ
        quality_factor = 0.7 + (0.3 * image_quality)
        
        # Class complexity factor (CNN ดีกว่าสำหรับ class ง่ายๆ)
        complexity = self.class_complexity.get(cnn_pred.predicted_class, 0.5)
        complexity_factor = 1.0 - (complexity * 0.2)  # ง่าย = ได้คะแนนเต็ม
        
        final_weight = (base_score * 0.7 + separation_bonus) * quality_factor * complexity_factor
        return min(final_weight, 1.0)
    
    def calculate_kimi_weight(self, kimi_pred: KimiPrediction,
                             cnn_pred: Optional[CNNPrediction] = None) -> float:
        """
        คำนวณน้ำหนักสำหรับ KIMI
        
        Args:
            kimi_pred: ผลลัพธ์จาก KIMI
            cnn_pred: ผลลัพธ์จาก CNN (optional)
        
        Returns:
            float: น้ำหนัก KIMI (0-1)
        """
        # ถ้า KIMI ไม่มั่นใจ → น้ำหนักต่ำ
        if kimi_pred.is_uncertain:
            return 0.2
        
        base_score = 0.75  # KIMI เริ่มต้นที่ 0.75 (มีความรู้พื้นฐานสูง)
        
        # Quality bonus
        quality_bonus = kimi_pred.reasoning_quality * 0.15
        
        # Class complexity factor (KIMI ดีกว่าสำหรับ class ซับซ้อน)
        complexity = self.class_complexity.get(kimi_pred.predicted_class, 0.5)
        complexity_factor = 0.8 + (complexity * 0.2)  # ซับซ้อน = ได้คะแนนเพิ่ม
        
        # Disagreement penalty (ถ้าขัดแย้งกับ CNN ที่มั่นใจสูง)
        disagreement_penalty = 0
        if cnn_pred and cnn_pred.confidence > 0.9:
            if cnn_pred.predicted_class != kimi_pred.predicted_class:
                disagreement_penalty = 0.15
        
        final_weight = (base_score + quality_bonus) * complexity_factor - disagreement_penalty
        return max(0.2, min(final_weight, 1.0))
    
    def decide_ensemble(self, cnn_pred: Optional[CNNPrediction],
                       kimi_pred: Optional[KimiPrediction],
                       image_quality: float = 1.0) -> EnsembleResult:
        """
        ตัดสินใจสุดท้ายโดยใช้ Ensemble
        
        Returns:
            EnsembleResult: ผลลัพธ์พร้อมรายละเอียด
        """
        # Case 1: มีแค่ CNN
        if cnn_pred and not kimi_pred:
            return self._cnn_only_result(cnn_pred)
        
        # Case 2: มีแค่ KIMI
        if kimi_pred and not cnn_pred:
            return self._kimi_only_result(kimi_pred)
        
        # Case 3: มีทั้งสองตัว
        return self._ensemble_both(cnn_pred, kimi_pred, image_quality)
    
    def _cnn_only_result(self, cnn_pred: CNNPrediction) -> EnsembleResult:
        """กรณีมี CNN อย่างเดียว"""
        confidence = cnn_pred.confidence
        
        if confidence >= self.thresholds['cnn_high_confidence']:
            reasoning = f"CNN มั่นใจสูง ({confidence:.1%}) ไม่ต้องใช้ KIMI"
            recommendations = ["ใช้ผล CNN โดยตรง", "ความแม่นยำสูง"]
        elif confidence >= self.thresholds['cnn_medium_confidence']:
            reasoning = f"CNN มั่นใจปานกลาง ({confidence:.1%}) แนะนำให้ใช้ KIMI ยืนยัน"
            recommendations = ["ใช้ CNN เป็นหลัก", "ควรมี KIMI ตรวจสอบเพิ่ม"]
        else:
            reasoning = f"CNN ไม่มั่นใม ({confidence:.1%}) ควรใช้ KIMI เป็นหลัก"
            recommendations = ["ใช้ KIMI เป็นหลัก", "CNN เป็น secondary"]
            confidence = confidence * 0.7
        
        return EnsembleResult(
            final_diagnosis=cnn_pred.predicted_class,
            confidence=confidence,
            source=DiagnosisSource.CNN,
            cnn_weight=1.0,
            kimi_weight=0.0,
            cnn_prediction=cnn_pred,
            kimi_prediction=None,
            reasoning=reasoning,
            recommendations=recommendations
        )
    
    def _kimi_only_result(self, kimi_pred: KimiPrediction) -> EnsembleResult:
        """กรณีมี KIMI อย่างเดียว"""
        if kimi_pred.is_uncertain:
            return EnsembleResult(
                final_diagnosis="No disease or pest found",
                confidence=0.5,
                source=DiagnosisSource.KIMI,
                cnn_weight=0.0,
                kimi_weight=1.0,
                cnn_prediction=None,
                kimi_prediction=kimi_pred,
                reasoning="KIMI ไม่พบความผิดปกติที่ชัดเจน",
                recommendations=["ถ่ายภาพใหม่ที่ชัดกว่า", "ตรวจสอบภาพด้วยตนเอง"]
            )
        
        return EnsembleResult(
            final_diagnosis=kimi_pred.predicted_class,
            confidence=0.75,
            source=DiagnosisSource.KIMI,
            cnn_weight=0.0,
            kimi_weight=1.0,
            cnn_prediction=None,
            kimi_prediction=kimi_pred,
            reasoning="ใช้ KIMI อย่างเดียว (ไม่มี CNN)",
            recommendations=["ใช้ผล KIMI", "แนะนำให้มี CNN สำหรับความเร็ว"]
        )
    
    def _ensemble_both(self, cnn_pred: CNNPrediction,
                      kimi_pred: KimiPrediction,
                      image_quality: float) -> EnsembleResult:
        """กรณีมีทั้ง CNN และ KIMI"""
        
        # คำนวณน้ำหนัก
        cnn_weight = self.calculate_cnn_weight(cnn_pred, image_quality)
        kimi_weight = self.calculate_kimi_weight(kimi_pred, cnn_pred)
        
        # Normalize weights
        total = cnn_weight + kimi_weight
        cnn_weight = cnn_weight / total
        kimi_weight = kimi_weight / total
        
        # Case: KIMI ไม่พบโรค หรือ คลาสเป็นปกติ
        is_kimi_healthy = kimi_pred.is_uncertain or kimi_pred.predicted_class.lower() in ["none", "healthy", "no disease or pest found", "พืชสุขภาพดี"]
        
        if is_kimi_healthy:
            # 🚨 พิเศษ: เนื่องจาก CNN ของเรา "ไม่มีคลาสพืชสุขภาพดี" (มีแต่โรค 16 คลาส) 
            # ทำให้เวลานำภาพพืชปกติไปสแกน CNN จะถูกบังคับให้บีบความน่าจะเป็นไปที่โรคใดโรคหนึ่ง 
            # และอาจจะได้ Confidence > 0.8 ได้ง่ายมาก (False Positive)
            # ดังนั้น ถ้า KIMI (ซึ่งมีคลาส Healthy) บอกว่าไม่มีโรค เราควรเชื่อ KIMI มากกว่าอย่างมาก!
            
            if cnn_pred.confidence > 0.95:
                # CNN มั่นใจมากๆๆๆ (>95%) อาจจะมีรอยโรคเล็กๆ ที่ KIMI มองข้าม 
                # (ลด confidence ลงฮวบเพื่อให้ระบบแจ้งเตือนว่าไม่ชัวร์)
                return EnsembleResult(
                    final_diagnosis=cnn_pred.predicted_class,
                    confidence=cnn_pred.confidence * 0.5,  # หั่น confidence ลงครึ่งนึงทันที
                    source=DiagnosisSource.ENSEMBLE,
                    cnn_weight=0.7,
                    kimi_weight=0.3, # ค่าน้ำหนักปรับตามความน่าจะเป็น
                    cnn_prediction=cnn_pred,
                    kimi_prediction=kimi_pred,
                    reasoning="CNN มั่นใจสูงลิ่ว (>95%) ว่ามีโรค แต่ KIMI ไม่พบ (อาจเป็นภาพพืชปกติที่ CNN มองผิดพลาด ควรตรวจสอบซ้ำ)",
                    recommendations=["ตรวจสอบด้วยตาเปล่าอีกครั้ง", "CNN ขัดแย้งกับ AI อย่างรุนแรง"]
                )
            else:
                # ทั้งคู่ไม่มั่นใจ หรือ CNN confidence 0.8-0.94 ซึ่งถือว่าเชื่อถือไม่ได้ในกรณีถ่ายภาพพืชปกติ
                return EnsembleResult(
                    final_diagnosis="No disease or pest found / พืชสุขภาพดี",
                    confidence=0.85, # มั่นใจใน Kimi
                    source=DiagnosisSource.ENSEMBLE,
                    cnn_weight=0.1,
                    kimi_weight=0.9,
                    cnn_prediction=cnn_pred,
                    kimi_prediction=kimi_pred,
                    reasoning="KIMI ระบุว่าไม่พบโรค/เป็นพืชปกติ (CNN ไม่มีคลาสปกติจึงต้องตกไป)",
                    recommendations=["พืชดูมีสุขภาพดี", "หากพบความผิดปกติให้ลองถ่ายรูปซูมใกล้ๆ อีกครั้ง"]
                )
        
        # Case: ตรงกัน
        if cnn_pred.predicted_class == kimi_pred.predicted_class:
            confidence = min(0.95, max(cnn_pred.confidence, 0.75) + 0.15)
            return EnsembleResult(
                final_diagnosis=cnn_pred.predicted_class,
                confidence=confidence,
                source=DiagnosisSource.ENSEMBLE,
                cnn_weight=cnn_weight,
                kimi_weight=kimi_weight,
                cnn_prediction=cnn_pred,
                kimi_prediction=kimi_pred,
                reasoning=f"CNN และ KIMI ตรงกัน ({cnn_pred.predicted_class})",
                recommendations=["ความมั่นใจสูงมาก", "ใช้ผลนี้ได้เลย"]
            )
        
        # Case: ไม่ตรงกัน → Weighted decision
        # สร้าง score สำหรับแต่ละ class
        scores = {}
        
        # CNN score
        for cls, score in cnn_pred.top_k:
            scores[cls] = scores.get(cls, 0) + (score * cnn_weight)
        
        # KIMI score
        scores[kimi_pred.predicted_class] = scores.get(kimi_pred.predicted_class, 0) + (0.8 * kimi_weight)
        
        # เลือก class ที่มี score สูงสุด
        final_class = max(scores, key=scores.get)
        final_confidence = scores[final_class]
        
        reasoning = f"CNN: {cnn_pred.predicted_class} ({cnn_pred.confidence:.1%}) vs KIMI: {kimi_pred.predicted_class} → เลือก {final_class}"
        
        return EnsembleResult(
            final_diagnosis=final_class,
            confidence=final_confidence,
            source=DiagnosisSource.ENSEMBLE,
            cnn_weight=cnn_weight,
            kimi_weight=kimi_weight,
            cnn_prediction=cnn_pred,
            kimi_prediction=kimi_pred,
            reasoning=reasoning,
            recommendations=["ตรวจสอบด้วยตนเองเพิ่ม", "พิจารณาถ่ายภาพเพิ่ม"]
        )


class DiagnosisAPI:
    """
    API สำหรับเรียกใช้ระบบวินิจฉัยแบบ Ensemble
    """
    
    def __init__(self):
        self.ensemble = DiagnosisWeightingSystem()
    
    def diagnose(self, 
                 image_path: str,
                 cnn_result: Optional[Dict] = None,
                 kimi_result: Optional[Dict] = None,
                 image_quality: float = 1.0) -> Dict:
        """
        วินิจฉัยโรคพืช/แมลง
        
        Args:
            image_path: พาธของภาพ
            cnn_result: ผลจาก CNN {"class": "...", "confidence": 0.85, "top_k": [...]}
            kimi_result: ผลจาก KIMI {"class": "...", "raw_response": "...", "is_uncertain": false}
            image_quality: คุณภาพภาพ (0-1)
        
        Returns:
            Dict: ผลลัพธ์การวินิจฉัย
        """
        # Convert dict to objects
        cnn_pred = None
        if cnn_result:
            cnn_pred = CNNPrediction(
                predicted_class=cnn_result['class'],
                confidence=cnn_result['confidence'],
                top_k=cnn_result.get('top_k', [(cnn_result['class'], cnn_result['confidence'])]),
                inference_time_ms=cnn_result.get('inference_time_ms', 0)
            )
        
        kimi_pred = None
        if kimi_result:
            kimi_pred = KimiPrediction(
                predicted_class=kimi_result['class'],
                raw_response=kimi_result.get('raw_response', ''),
                is_uncertain=kimi_result.get('is_uncertain', False),
                reasoning_quality=kimi_result.get('reasoning_quality', 0.8),
                response_time_ms=kimi_result.get('response_time_ms', 0)
            )
        
        # Run ensemble
        result = self.ensemble.decide_ensemble(cnn_pred, kimi_pred, image_quality)
        
        return {
            'diagnosis': result.final_diagnosis,
            'confidence': round(result.confidence, 3),
            'source': result.source.value,
            'weights': {
                'cnn': round(result.cnn_weight, 3),
                'kimi': round(result.kimi_weight, 3)
            },
            'details': {
                'cnn_prediction': cnn_result['class'] if cnn_result else None,
                'kimi_prediction': kimi_result['class'] if kimi_result else None,
            },
            'reasoning': result.reasoning,
            'recommendations': result.recommendations
        }


# ============ ตัวอย่างการใช้งาน ============

def example_usage():
    """ตัวอย่างการใช้งาน"""
    
    api = DiagnosisAPI()
    
    print("=" * 70)
    print("🌿 AI Plant Disease Diagnosis Ensemble")
    print("=" * 70)
    
    # ตัวอย่าง 1: CNN มั่นใจสูง
    print("\n📸 Case 1: CNN มั่นใจสูง (Powdery Mildew)")
    result = api.diagnose(
        image_path="/path/to/image.jpg",
        cnn_result={
            'class': 'Powdery Mildew',
            'confidence': 0.92,
            'top_k': [('Powdery Mildew', 0.92), ('Downy Mildew', 0.05)],
            'inference_time_ms': 45
        },
        kimi_result={
            'class': 'Powdery Mildew',
            'raw_response': 'Powdery Mildew',
            'is_uncertain': False,
            'reasoning_quality': 0.9,
            'response_time_ms': 1200
        },
        image_quality=0.9
    )
    print(f"   ผล: {result['diagnosis']} (confidence: {result['confidence']})")
    print(f"   น้ำหนัก: CNN {result['weights']['cnn']}, KIMI {result['weights']['kimi']}")
    print(f"   💡 {result['reasoning']}")
    
    # ตัวอย่าง 2: CNN ไม่มั่นใจ แต่ KIMI ชัดเจน
    print("\n📸 Case 2: CNN ไม่มั่นใจ (Bemisia tabaci)")
    result = api.diagnose(
        image_path="/path/to/image.jpg",
        cnn_result={
            'class': 'Bemisia tabaci',
            'confidence': 0.45,
            'top_k': [('Bemisia tabaci', 0.45), ('Thrips', 0.40)],
            'inference_time_ms': 45
        },
        kimi_result={
            'class': 'Bemisia tabaci',
            'raw_response': 'Bemisia tabaci',
            'is_uncertain': False,
            'reasoning_quality': 0.85,
            'response_time_ms': 1200
        },
        image_quality=0.7
    )
    print(f"   ผล: {result['diagnosis']} (confidence: {result['confidence']})")
    print(f"   น้ำหนัก: CNN {result['weights']['cnn']}, KIMI {result['weights']['kimi']}")
    print(f"   💡 {result['reasoning']}")
    
    # ตัวอย่าง 3: KIMI ไม่พบโรค
    print("\n📸 Case 3: KIMI ไม่พบโรค")
    result = api.diagnose(
        image_path="/path/to/image.jpg",
        cnn_result={
            'class': 'Anthracnose',
            'confidence': 0.75,
            'top_k': [('Anthracnose', 0.75), ('Leaf Spot Disease', 0.15)],
            'inference_time_ms': 45
        },
        kimi_result={
            'class': 'No disease or pest found',
            'raw_response': 'No disease or pest found',
            'is_uncertain': True,
            'reasoning_quality': 0.7,
            'response_time_ms': 1200
        },
        image_quality=0.6
    )
    print(f"   ผล: {result['diagnosis']} (confidence: {result['confidence']})")
    print(f"   น้ำหนัก: CNN {result['weights']['cnn']}, KIMI {result['weights']['kimi']}")
    print(f"   💡 {result['reasoning']}")
    
    # ตัวอย่าง 4: ไม่ตรงกัน
    print("\n📸 Case 4: CNN และ KIMI ไม่ตรงกัน")
    result = api.diagnose(
        image_path="/path/to/image.jpg",
        cnn_result={
            'class': 'Downy Mildew',
            'confidence': 0.68,
            'top_k': [('Downy Mildew', 0.68), ('Powdery Mildew', 0.25)],
            'inference_time_ms': 45
        },
        kimi_result={
            'class': 'Powdery Mildew',
            'raw_response': 'Powdery Mildew',
            'is_uncertain': False,
            'reasoning_quality': 0.9,
            'response_time_ms': 1200
        },
        image_quality=0.8
    )
    print(f"   ผล: {result['diagnosis']} (confidence: {result['confidence']})")
    print(f"   น้ำหนัก: CNN {result['weights']['cnn']}, KIMI {result['weights']['kimi']}")
    print(f"   💡 {result['reasoning']}")
    print(f"   📋 {result['recommendations']}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    example_usage()
