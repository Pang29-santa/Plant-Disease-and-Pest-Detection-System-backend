"""
OpenAI Alternative Service
ใช้แทน Kimi AI เมื่อ api.moonshot.cn ไม่สามารถเข้าถึงได้
"""

import os
import base64
import json
from typing import Optional, Dict, Any
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

class OpenAIService:
    """Service สำหรับเชื่อมต่อกับ OpenAI API"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        if self.api_key:
            print(f"✅ OpenAI Key loaded: {self.api_key[:15]}...")
        else:
            print("ℹ️ OpenAI Key not found")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_image(
        self,
        image_path: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """วิเคราะห์รูปภาพด้วย OpenAI Vision"""
        try:
            base64_image = self._encode_image_to_base64(image_path)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "content": content,
                    "model": result.get("model"),
                    "usage": result.get("usage", {})
                }
            else:
                return {
                    "success": False,
                    "error": f"OpenAI API Error: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {"success": False, "error": f"Connection Error: {str(e)}"}


# Create instance
_openai_service: Optional[OpenAIService] = None

def get_openai_service() -> OpenAIService:
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service


def analyze_plant_health_openai(image_path: str) -> Dict[str, Any]:
    """วิเคราะห์สุขภาพพืชด้วย OpenAI"""
    from services.kimi_ai import DISEASE_CLASSES, PEST_CLASSES, _extract_json
    
    service = get_openai_service()
    
    disease_list = "\n".join([f"- ID: {c['id']}, Name: {c['name']}" for c in DISEASE_CLASSES])
    pest_list = "\n".join([f"- ID: {c['id']}, Name: {c['name']}" for c in PEST_CLASSES])
    
    prompt = f"""คุณเป็นผู้เชี่ยวชาญด้านกีฏวิทยาและโรคพืช
วิเคราะห์รูปภาพพืชเพื่อระบุปัญหา (โรคหรือแมลง)

โรคที่รองรับ:
{disease_list}

แมลงศัตรูพืช:
{pest_list}

ตอบกลับเป็น JSON:
{{
    "is_plant": true/false,
    "is_detected": true/false,
    "category": "disease" | "pest" | "none",
    "detected_class_id": "ID หรือ null",
    "target_name_th": "ชื่อภาษาไทย",
    "target_name_en": "ชื่อภาษาอังกฤษ",
    "confidence": 0-100,
    "severity_level": "ต่ำ" | "ปานกลาง" | "สูง",
    "symptoms": "อธิบายอาการ"
}}

ห้ามตอบนอกเหนือจาก JSON"""

    result = service.analyze_image(image_path, prompt, temperature=0.2)
    
    if result["success"]:
        analysis = _extract_json(result["content"])
        return {
            "success": True,
            "analysis": analysis,
            "raw_response": result["content"]
        }
    else:
        return result
