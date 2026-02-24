"""
ตัวอย่างการใช้งาน Plant Disease Filter
"""

from plant_disease_filter import (
    PlantDiseaseClassifier, 
    FilterConfig,
    PredictionStatus
)

# ============================================
# วิธีใช้งานแบบง่าย
# ============================================

def simple_example():
    """ตัวอย่างพื้นฐาน"""
    
    # 1. สร้าง classifier
    classifier = PlantDiseaseClassifier('model.h5')
    
    # 2. ทำนาย
    result = classifier.predict('image.jpg')
    
    # 3. ตรวจสอบผล
    print(f"ผลลัพธ์: {result['final_prediction']}")
    print(f"สถานะ: {result['status']}")
    
    # 4. ตัดสินใจตามผล
    if result['status'] == PredictionStatus.CONFIDENT.value:
        print(f"มั่นใจ: {result['final_prediction']}")
        
    elif result['status'] == PredictionStatus.POSSIBLE_INSECT.value:
        print("⚠️ อาจเป็นแมลง กรุณาตรวจสอบ:")
        print(result.get('suggestion', ''))
        
    elif result['status'] == PredictionStatus.UNCERTAIN.value:
        print("❓ ไม่แน่ใจ กรุณาถ่ายภาพใหม่")


# ============================================
# วิธีใช้งานแบบปรับ config
# ============================================

def custom_config_example():
    """ปรับ config ตามความต้องการ"""
    
    config = FilterConfig(
        min_confidence=0.70,          # เข้มงวดขึ้น
        min_confidence_gap=0.20,       # ต้องห่างกันมาก
        auto_override_low_conf=True,
        low_confidence_threshold=0.50
    )
    
    classifier = PlantDiseaseClassifier('model.h5', config)
    result = classifier.predict('image.jpg')
    
    return result


# ============================================
# วิธีใช้งานกับ API (FastAPI)
# ============================================

from fastapi import FastAPI, UploadFile, File
import tempfile
import os

app = FastAPI()

# Load model once
classifier = PlantDiseaseClassifier('model.h5')

@app.post("/predict")
async def predict_disease(file: UploadFile = File(...)):
    """API Endpoint สำหรับทำนาย"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Predict
        result = classifier.predict(tmp_path)
        
        # Format response for frontend
        response = {
            'success': True,
            'prediction': result['final_prediction'],
            'status': result['status'],
            'confidence': result.get('confidence', 0),
            'message': result.get('message', ''),
            'suggestion': result.get('suggestion', ''),
        }
        
        # Add warning if needed
        if result['status'] == PredictionStatus.POSSIBLE_INSECT.value:
            response['warning'] = {
                'type': 'insect_suspected',
                'message': 'โมเดลตรวจพบลักษณะคล้ายแมลง',
                'action': 'ตรวจหาตัวแมลงบนใบพืช'
            }
        
        return response
        
    finally:
        os.unlink(tmp_path)


# ============================================
# ตัวอย่างผลลัพธ์
# ============================================

def example_outputs():
    """ตัวอย่างผลลัพธ์ที่ได้จากแต่ละกรณี"""
    
    # กรณี 1: โรคจริง มั่นใจ
    case1 = {
        'final_prediction': 'powdery',
        'status': 'confident',
        'confidence': 0.92,
        'message': 'ผลลัพธ์น่าเชื่อถือ',
        'visual_features': {
            'total_lesion_area_ratio': 0.25,
            'num_spots': 12,
            'suspicious_insect': False
        }
    }
    
    # กรณี 2: แมลง (ถูกจับได้)
    case2 = {
        'final_prediction': 'possible_insect',
        'status': 'possible_insect',
        'original_prediction': 'mosaic',
        'original_confidence': 0.55,
        'reason': 'Visual features suggest insect damage (many small spots)',
        'suggestion': 'พบจุดเล็กจำนวนมาก อาจเป็นรอยกัดของแมลง',
        'visual_features': {
            'num_spots': 85,
            'avg_spot_size': 45.2,
            'suspicious_insect': True
        }
    }
    
    # กรณี 3: ไม่แน่ใจ
    case3 = {
        'final_prediction': 'uncertain',
        'status': 'uncertain',
        'reason': 'Confidence 0.45 < threshold 0.60',
        'suggestion': 'ถ่ายภาพใหม่หรือตรวจสอบด้วยตาเปล่า',
        'all_probabilities': {
            'mosaic': 0.45,
            'powdery': 0.30,
            'healthy': 0.25
        }
    }
    
    # กรณี 4: โมเดลสับสน
    case4 = {
        'final_prediction': 'possible_insect_or_unknown',
        'status': 'possible_insect',
        'reason': 'Top-1 and Top-2 too close (0.08 < 0.15)',
        'top_2_alternatives': [
            {'class': 'mosaic', 'prob': 0.42},
            {'class': 'healthy', 'prob': 0.34}
        ],
        'suggestion': 'โมเดลสับสนระหว่างโรค อาจเป็นแมลง'
    }
    
    return [case1, case2, case3, case4]


# ============================================
# ตัวอย่างการแสดงผลใน Frontend
# ============================================

"""
// React/Vue ตัวอย่าง
function PredictionResult({ result }) {
    const { prediction, status, confidence, warning } = result;
    
    // กรณีมั่นใจ
    if (status === 'confident') {
        return (
            <div className="alert alert-success">
                <h3>พบ: {prediction}</h3>
                <p>ความมั่นใจ: {(confidence * 100).toFixed(1)}%</p>
            </div>
        );
    }
    
    // กรณีอาจเป็นแมลง
    if (status === 'possible_insect') {
        return (
            <div className="alert alert-warning">
                <h3>⚠️ ตรวจพบความผิดปกติ</h3>
                <p>ลักษณะคล้าย: {prediction}</p>
                <p>แต่มีโอกาสเป็นแมลง</p>
                <div className="action-box">
                    <h4>แนะนำ:</h4>
                    <ul>
                        <li>ตรวจหาตัวแมลงบนใบพืช</li>
                        <li>ถ่ายรูปเพิ่มหลายมุม</li>
                        <li>ตรวจด้านหลังใบ</li>
                    </ul>
                </div>
            </div>
        );
    }
    
    // กรณีไม่แน่ใจ
    if (status === 'uncertain') {
        return (
            <div className="alert alert-info">
                <h3>❓ ไม่สามารถระบุได้</h3>
                <p>โมเดลไม่มั่นใจในผลลัพธ์</p>
                <button onClick={retakePhoto}>
                    ถ่ายภาพใหม่
                </button>
            </div>
        );
    }
}
"""


if __name__ == "__main__":
    # Run examples
    print("ตัวอย่างผลลัพธ์:")
    for i, case in enumerate(example_outputs(), 1):
        print(f"\nกรณี {i}:")
        print(f"  Status: {case['status']}")
        print(f"  Prediction: {case['final_prediction']}")
