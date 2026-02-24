"""Test TensorFlow Model"""
import sys
from pathlib import Path

# Test 1: Check model loaded
print("="*60)
print("Test 1: Checking Model")
print("="*60)

from services.tf_model_service import get_tf_model_service, analyze_with_tensorflow

service = get_tf_model_service()
info = service.get_model_info()

print(f"[OK] Model loaded: {info['loaded']}")
print(f"[OK] Model type: {info['model_type']}")
print(f"[OK] Accuracy: {info['accuracy']}")
print(f"[OK] Classes: {info['num_classes']}")

# Test 2: Find test image
print("\n" + "="*60)
print("Test 2: Prediction")
print("="*60)

test_dirs = [
    Path("C:/Users/ADMINS/Downloads/Dataset/test"),
]

test_img = None
for d in test_dirs:
    if d.exists():
        imgs = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
        if imgs:
            test_img = imgs[0]
            break

if test_img:
    print(f"Testing with: {test_img}")
    
    result = analyze_with_tensorflow(str(test_img), use_tta=False, enhance=True)
    
    if result.get('success'):
        print(f"\n[SUCCESS] PREDICTION SUCCESS!")
        print(f"  Prediction: {result['primary']['name_th']}")
        print(f"  English: {result['primary']['name_en']}")
        print(f"  Confidence: {result['primary']['confidence_percent']}%")
        print(f"  Category: {result['primary']['category']}")
        print(f"\n  Top 3:")
        for i, p in enumerate(result['top_3'][:3], 1):
            print(f"    {i}. {p['name_th']}: {p['confidence_percent']}%")
    else:
        print(f"\n[ERROR] {result.get('error')}")
else:
    print("[ERROR] No test images found")

print("\n" + "="*60)
print("Done!")
print("="*60)
