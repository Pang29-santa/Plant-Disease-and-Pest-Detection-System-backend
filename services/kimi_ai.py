"""
Kimi AI (Moonshot AI) Service
เชื่อมต่อกับ Kimi AI API สำหรับวิเคราะห์รูปภาพโรคพืชและศัตรูพืช
"""

import os
import base64
import json
from typing import Optional, Dict, Any
from pathlib import Path

import requests
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()

# แมปชื่อโรค/ศัตรูพืชภาษาอังกฤษเป็นภาษาไทย
DISEASE_NAME_MAPPING = {
    "Anthracnose": "โรคแอนแทรคโนส",
    "Cercospora Leaf Spot": "โรคแผลวงกลมสีน้ำตาลไหม้",
    "Downy Mildew": "โรคราน้ำค้าง",
    "Leaf Blight": "โรคใบไหม้",
    "Leaf Spot Disease": "โรคใบจุด",
    "Powdery Mildew": "โรคราแป้ง",
    "Rust Disease": "โรคราสนิม",
    "White Rust Disease": "โรคราสนิมขาว"
}

PEST_NAME_MAPPING = {
    "Bemisia tabaci": "แมลงหวี่ขาว",
    "Common Cutworm": "หนอนกระทู้ผัก",
    "Diamondback Moth": "หนอนใยผัก",
    "Flea Beetle": "ด้วงหมัดผัก",
    "Leaf Miner": "หนอนชอนใบ",
    "Leafhopper": "เพลี้ยจักจั่น",
    "Red Pumpkin Beetle": "ด้วงเต่าแตงแดง",
    "Thrips": "เพลี้ยไฟ"
}

class KimiAIService:
    """Service สำหรับเชื่อมต่อกับ Kimi AI API"""
    
    def __init__(self):
        # โหลดค่าจาก environment ทุกครั้งที่สร้าง instance
        self.api_key = os.getenv("KIMI_API_KEY", "").strip()
        self.api_url = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1").strip()
        self.model = os.getenv("KIMI_MODEL", "kimi-latest").strip()
        self.vision_model = os.getenv("KIMI_VISION_MODEL", "kimi-latest").strip()
        
        # Debug: ตรวจสอบว่าอ่านค่าได้ไหม (ตามคำแนะนำของคุณ)
        if self.api_key:
            print(f"✅ Kimi Key loaded: {self.api_key[:15]}... (length: {len(self.api_key)})")
            if " " in self.api_key:
                print("⚠️ Warning: Kimi Key has spaces!")
        else:
            # ไม่ Raise error ทันทีเพื่อให้ service อื่นทำงานได้
            print("ℹ️ Info: KIMI_API_KEY not found (Using Legacy Service)")
    
    def _get_headers(self) -> Dict[str, str]:
        """สร้าง HTTP headers สำหรับเรียก API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """
        แปลงรูปภาพเป็น base64
        
        Args:
            image_path: path ของรูปภาพ
            
        Returns:
            base64 encoded string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_image(
        self,
        image_path: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096  # เพิ่มตามที่ผู้ใช้ส่งมา
    ) -> Dict[str, Any]:
        """
        วิเคราะห์รูปภาพด้วย Kimi AI Vision
        """
        try:
            # แปลงรูปภาพเป็น base64
            base64_image = self._encode_image_to_base64(image_path)
            
            # สร้าง payload ตามาตัวอย่างที่ผู้ใช้ส่งมา
            payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
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
            
            # เรียก API พร้อม retry
            max_retries = 3
            response = None
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{self.api_url}/chat/completions",
                        headers=self._get_headers(),
                        json=payload,
                        timeout=120  # เพิ่ม timeout เป็น 120 วินาที
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(5)  # Wait 5 seconds before retry
                    else:
                        raise  # Re-raise on last attempt
            
            if response is None:
                return {
                    "success": False,
                    "error": "Connection failed after 3 attempts. Please check your internet or use VPN."
                }
            
            # จัดการ Error แบบเจาะจงตามที่ผู้ใช้ส่งมา
            if response.status_code == 401:
                return {
                    "success": False, 
                    "error": "API Key ไม่ถูกต้องหรือหมดอายุ (401) กรุณาตรวจสอบ Key ในไฟล์ .env หรือเช็คว่า URL ถูกต้องสำหรับ Key นี้หรือไม่"
                }
            elif response.status_code != 200:
                return {
                    "success": False, 
                    "error": f"Kimi API Error: {response.status_code} - {response.text}"
                }
            
            result = response.json()
            
            # ดึงคำตอบจาก response
            if "choices" in result and len(result["choices"]) > 0:
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
                    "error": "AI ตอบกลับว่างเปล่า",
                    "raw_response": result
                }
        except Exception as e:
            return {"success": False, "error": f"Connection Error: {str(e)}"}
    
    def analyze_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        วิเคราะห์ข้อความด้วย Kimi AI
        
        Args:
            prompt: คำถามหรือคำสั่ง
            temperature: ความสร้างสรรค์ของคำตอบ
            max_tokens: จำนวน token สูงสุด
            
        Returns:
            Dict ที่มีผลการวิเคราะห์
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
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
        
        if response.status_code != 200:
            raise Exception(f"Kimi AI API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
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
                "error": "No response from AI"
            }


# สร้าง instance สำหรับใช้งานทั่วไป
_kimi_service: Optional[KimiAIService] = None


def get_kimi_service() -> KimiAIService:
    """ได้ instance ของ KimiAIService (Singleton)"""
    global _kimi_service
    if _kimi_service is None:
        _kimi_service = KimiAIService()
    return _kimi_service


# โรคพืชและแมลงศัตรูพืชที่รองรับ (Classes) พร้อม ID จาก Database
# โรคพืชและแมลงศัตรูพืชที่รองรับ (Classes) พร้อมลักษณะเด่นเพื่อช่วย AI วิเคราะห์
DISEASE_CLASSES = [
    {
        "id": 29, 
        "name": "โรคใบจุด (Leaf Spot Disease)",
        "description": "พบจุดเล็กๆ สีน้ำตาลหรือดำบนใบ บางครั้งมีวงแหวนสีเหลืองล้อมรอบ จุดอาจขยายรวมกันเป็นแผลใหญ่"
    },
    {
        "id": 30, 
        "name": "โรคราน้ำค้าง (Downy Mildew)",
        "description": "ด้านบนใบเป็นปื้นสีเหลืองหรือเขียวอมเหลือง ขอบเขตเป็นเหลี่ยมตามเส้นใบ ด้านใต้ใบพบผงละเอียดสีเทาหรือม่วงอ่อน"
    },
    {
        "id": 31, 
        "name": "โรคแผลวงกลมสีน้ำตาลไหม้ (Cercospora Leaf Spot)",
        "description": "แผลเป็นวงกลมขนาดเล็ก ศูนย์กลางสีเทาขาว ขอบแผลสีน้ำตาลเข้มหรือแดง เห็นเป็นวงซ้อนกันคล้ายเป้ายิงปืน"
    },
    {
        "id": 32, 
        "name": "โรคใบไหม้ (Leaf Blight)",
        "description": "แผลขนาดใหญ่ สีน้ำตาลแห้ง มักเริ่มจากขอบใบหรือปลายใบ ลุกลามอย่างรวดเร็วทำให้ใบแห้งตายทั้งใบ"
    },
    {
        "id": 33, 
        "name": "โรคแอนแทรคโนส (Anthracnose)",
        "description": "แผลมีลักษณะบุ๋มลงไป (sunken) สีน้ำตาลเข้มหรือดำ มักพบเป็นวงซ้อนกัน ตรงกลางแผลอาจมีสปอร์สีส้มหรือชมพู"
    },
    {
        "id": 34, 
        "name": "โรคราสนิม (Rust Disease)",
        "description": "พบเป็นตุ่มนูนขนาดเล็ก (pustules) สีส้ม น้ำตาลแดง หรือเหลืองคล้ายสนิมเหล็ก มักพบมากที่ด้านใต้ใบ"
    },
    {
        "id": 35, 
        "name": "โรคราแป้ง (Powdery Mildew)",
        "description": "พบผงสีขาวคล้ายแป้งโรยปกคลุมบนผิวใบ กิ่ง หรือลำต้น ทำให้ใบหงิกงอและแห้งเหี่ยว"
    },
    {
        "id": 36, 
        "name": "โรคราสนิมขาว (White Rust Disease)",
        "description": "ด้านใต้ใบพบตุ่มนูนสีขาวคล้ายแป้ง ด้านบนใบเหลืองซีด มักระบาดหนักในพืชตระกูลผักบุ้งหรือผักกาด"
    }
]

PEST_CLASSES = [
    {
        "id": 38, 
        "name": "ด้วงเต่าแตงแดง (Red Pumpkin Beetle)",
        "description": "ตัวเต็มวัยเป็นด้วงปีกแข็งสีส้มแดง กัดกินใบเป็นวงกลมหรือครึ่งวงกลม ทำให้ใบแหว่งเป็นรู"
    },
    {
        "id": 39, 
        "name": "ด้วงหมัดผัก (Flea Beetle)",
        "description": "ตัวมีขนาดเล็กมาก สีดำหรือน้ำตาล กระโดดได้ กัดกินใบเป็นรูพรุนขนาดเล็กกระจายทั่วใบ (Shot-hole)"
    },
    {
        "id": 40, 
        "name": "หนอนใยผัก (Diamondback Moth)",
        "description": "ตัวหนอนสีเขียวอ่อน กินผิวใบด้านล่างจนใสเหลือเฉพาะผิวใบด้านบน (Window pane appearance)"
    },
    {
        "id": 41, 
        "name": "หนอนกระทู้ผัก (Common Cutworm)",
        "description": "หนอนตัวอ้วนสีน้ำตาลหรือเทาดำ กัดกินใบส่วนใหญ่จนเหลือเฉพาะก้านใบ หรือกัดโคนต้นขาด"
    },
    {
        "id": 42, 
        "name": "แมลงหวี่ขาว (Bemisia tabaci)",
        "description": "แมลงขนาดเล็กมาก ปีกสีขาว รวมกลุ่มใต้ใบ ดูดน้ำเลี้ยงทำให้ใบเหลืองหรือหงิกงอ พบคราบเหนียว (ราดำ)"
    },
    {
        "id": 43, 
        "name": "หนอนชอนใบ (Leaf Miner)",
        "description": "พบเส้นทางสีขาวคดเคี้ยวไปมาคล้ายแผนที่อยู่ภายในเนื้อใบ เกิดจากหนอนกัดกินเนื้อเยื่อระหว่างผิวใบ"
    },
    {
        "id": 44, 
        "name": "เพลี้ยอ่อนถั่ว (Cowpea Aphid)",
        "description": "แมลงตัวจิ๋วสีดำหรือเขียวเข้ม รูปร่างคล้ายหยดน้ำ รวมกลุ่มหนาแน่นตามยอดอ่อนหรือฝัก ดูดน้ำเลี้ยงทำให้พืชชะงักการโต"
    },
    {
        "id": 45, 
        "name": "เพลี้ยไฟ (Thrips)",
        "description": "ตัวมีขนาดเล็กมาก ทรงเรียวยาว สีเหลืองหรือน้ำตาล ทำให้ใบมีรอยสีเงิน ขอบใบม้วน หรือยอดหงิก"
    },
    {
        "id": 46, 
        "name": "เพลี้ยจักจั่น (Leafhopper)",
        "description": "แมลงรูปลิ่ม สีเขียวหรือน้ำตาล เดินเฉียงหรือดีดตัวหนี พ่นสารทำให้ขอบใบเหลืองซีด (Hopper burn)"
    }
]


def _extract_json(content: str) -> Dict[str, Any]:
    """แยก JSON ออกจากข้อความของ AI"""
    import re
    # หา JSON ใน code block ก่อน
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # ถ้าไม่มี code block ให้หาจากปีกกา
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = content
    
    try:
        return json.loads(json_str)
    except Exception:
        # ถ้าแปลงไม่สำเร็จ ให้ return dict เปล่าแทน None
        return {}


def analyze_plant_health(image_path: str) -> Dict[str, Any]:
    """
    วิเคราะห์สุขภาพพืช (รวมทั้งโรคและแมลง)
    
    Args:
        image_path: path ของรูปภาพ
        
    Returns:
        Dict ที่มีผลการวิเคราะห์
    """
    service = get_kimi_service()
    
    prompt = """
คุณเป็นผู้เชี่ยวชาญวินิจฉัยโรคพืช/แมลงจาก “ภาพเดี่ยว” ที่เน้นความแม่นยำสูงสุด
- เลือก "เพียง 1" คำตอบจากรายการด้านล่าง หรือ "No disease or pest found" ถ้าไม่มั่นใจ
- ตอบเป็นภาษาอังกฤษ เฉพาะชื่อคลาสเท่านั้น ห้ามคำอื่น

[Allowed Diseases]
Anthracnose
Cercospora Leaf Spot
Downy Mildew
Leaf Blight
Leaf Spot Disease
Powdery Mildew
Rust Disease
White Rust Disease

[Allowed Pests]
Bemisia tabaci
Common Cutworm
Diamondback Moth
Flea Beetle
Leaf Miner
Leafhopper
Red Pumpkin Beetle
Thrips

STRICT RULES (สำคัญมาก - ต้องทำตาม):
1) **ตรวจหาตัวแมลง/หนอนก่อนเสมอ (กฎข้อ 1)**: 
   - ดูใต้ใบและพื้นดินรอบๆ พืชให้ละเอียดก่อน - แมลงและหนอนมักซ่อน
   - หา **ตัวหนอน** สีเขียว/น้ำตาล/เทา ตัวอ้วนมน (Common Cutworm)
   - หาจุดเล็กๆ สีขาว/เหลือง/ดำที่อาจเป็นแมลงหรือตัวอ่อน
   - ถ้าเห็นตัวแมลง/หนอนชัดเจน ให้เลือกจาก [Allowed Pests] ทันที อย่าตอบ Healthy
   - **ห้ามตอบ Healthy ถ้าสงสัยว่าอาจมีแมลง** - ให้เลือกแมลงที่ใกล้เคียงที่สุด

1a) **กฎสำคัญสำหรับ Common Cutworm**:
   - ถ้าเห็น **หนอนขนาดใหญ่ (3-5 ซม.)** สีเขียว/น้ำตาล ตัวอ้วนมน อยู่บนหรือใกล้พืช → นี่คือ Common Cutworm
   - ถ้าเห็นรอยกัดขอบใบ **"ชิ้นใหญ่ ฉีกขาด ไม่เป็นระเบียบ"** + อาจมีหนอนอยู่ใกล้ๆ → Common Cutworm
   - อย่าสับสนกับแมลงตัวเล็กๆ (Leafhopper, Thrips) - หนอนกระทู้มีตัวใหญ่กว่ามาก

2) **วิเคราะห์ละเอียดทุกซอกมุม**: อย่าตัดสินใจเร็ว ต้องซูมดูทุกบริเวณของใบ - ขอบใบ, กลางใบ, ปลายใบ, เส้นใบ, พื้นดินรอบๆ และพื้นผิวทั้งหมด
3) **เปรียบเทียบสองด้านใบเสมอ**: ถ้าเห็นเฉพาะด้านเดียว ให้พิจารณาว่าอาจมีอาการซ่อนอยู่อีกด้าน - อย่าตัดสินว่า Healthy ถ้าเห็นผิวใบผิดปกติแม้เล็กน้อย
4) **สงสัยให้เลือกโรค/แมลงที่เป็นไปได้**: ถ้าพบอาการคล้ายโรคหรือเห็นจุดผิดปกติ ให้เลือกจากรายการที่ใกล้เคียงที่สุด ไม่ใช่ตอบ Healthy
5) ใช้เฉพาะสิ่งที่ "เห็นได้จริงในภาพ" เท่านั้น (shape/สี/พื้นผิว/ความนูน-บุ๋ม/ตำแหน่งด้านบน-ล่างใบ/รูปแบบการกระจาย/ผงเชื้อ/ทางเดินกินใบ/คราบน้ำหวาน/มูล ฯลฯ)
6) ห้ามเดาจากบริบทภายนอก (ฤดูกาล/สภาพอากาศ/ชนิดพืช ถ้าไม่เห็นใบลักษณะเฉพาะ)
7) ถ้าไม่ชัดเจน ให้ตอบ: No disease or pest found
8) ถ้าลังเลระหว่างหลายชนิด ให้ใช้ "Hard Negatives & Tie-breakers" ด้านล่าง; ถ้ายังไม่มั่นใจ → No disease or pest found
9) ห้ามใช้ตัวหนังสือป้ายกำกับ/ลายน้ำ/คำบรรยายในภาพ/เครื่องมือวัดนอกภาพ ในการตัดสิน
10) ภาพย้อนแสง/เบลอ/โอเวอร์/อันเดอร์ ให้พิจารณาเฉพาะส่วนที่เห็นรายละเอียดผิวใบได้จริง

OBSERVATION PROTOCOL (ลำดับการสังเกต - สำคัญมาก):
A) **ตรวจหาตัวแมลง/หนอนบนใบเป็นอันดับแรก**: 
   - ซูมดูบริเวณใบทุกส่วน โดยเฉพาะ **ใต้ใบ**, **เส้นกลางใบ**, และ **พื้นดินรอบๆ พืช**
   - **ค้นหาตัวหนอน (caterpillar)**: สีเขียว/น้ำตาล/เทา ตัวอ้วนมน ขนาด 3-5 ซม. (Common Cutworm)
   - มองหาจุดเล็กๆ สีขาว/เหลือง/ดำ ที่อาจเป็นแมลงหรือตัวอ่อน (~1-3 มม.)
   - **ถ้าเห็นตัวหนอนชัดเจน** → นี่คือ Common Cutworm ทันที (ไม่ใช่ Leafhopper)
   - ถ้าเจอตัวแมลง ให้ระบุชนิดจาก [Allowed Pests] ทันที

B) มองรวม: รูปแบบกระจายของอาการ (กระจายทั่วใบ, เป็นหย่อม, ตามขอบใบ, ตามเส้นใบ, เฉพาะใต้ใบ ฯลฯ)
C) ซูมดูพื้นผิว: ผง/ฟิล์ม/แป้ง, ตุ่มนูน, ผิวเงิน, คราบเหนียว, มูลดำ, เส้นทางในเนื้อใบ
D) ขอบแผล: คม/ฟุ้ง, มีฮาโลหรือไม่, วงแหวนซ้อน
E) ความนูน-บุ๋ม: กลางแผลบุ๋ม? ตุ่มนูน? ผงหนาแห้งบนผิว?
F) สองด้านใบ: ด้านบน vs ด้านล่างใบ (มีอะไรเฉพาะด้านใดด้านหนึ่งไหม)

SIZE/UNIT GUIDE (อ้างอิงเชิงสัมพัทธ์ต่อความกว้างใบ):
- จุดเล็ก: เส้นผ่านศูนย์กลาง ~1–3% ของความกว้างใบ
- จุดกลาง: ~3–8%
- ปื้นใหญ่/ไหม้ลาม: >10–15%
- ผง/แป้งหนา: ปิดรายละเอียดเส้นใบชั้นตื้น
- เส้นทางกินใบ (leaf mine): กว้าง 0.5–3 มม. (ขึ้นกับชนิดพืช) ลักษณะงูเลื้อยในเนื้อใบ

==================== CLASS DIAGNOSTIC ATLAS ====================

[DISEASES]

• Anthracnose
  Macro: แผลรูปวงรี/กลมหยดน้ำ สีเข้ม (น้ำตาลเข้ม–ดำ) ขอบคมเข้ม ชัดเจน; มักมีวงแหวนซ้อนจาง ๆ; กลางแผล “บุ๋ม” เล็กน้อย
  Micro/Texture: อาจเห็นจุดดำละเอียด (acervuli) เกาะรวมกันบนแผล
  Distribution: จุดขนาดกลาง–ใหญ่ กระจายห่าง ๆ มากกว่ากระจายทั่วแผ่นใบแบบละเอียดยิบ
  Hard negatives: ไม่มีผงแป้งคลุมผิว (ตัด Powdery); ไม่เป็นเหลี่ยมตามเส้นใบ (ตัด Downy)
  Choose this over Cercospora เมื่อ: “ขอบคมเข้ม + กลางบุ๋ม + วงแหวนซ้อน” ชัดกว่า และแผลใหญ่กว่าเฉลี่ย

• Cercospora Leaf Spot
  Macro: จุดเล็ก–กลาง “กลางซีด-โปร่ง” ขอบเข้มบาง ๆ (ฮาโล), คล้ายเป้า/target; หลายจุดยิบ ๆ กระจายสม่ำเสมอ
  Micro/Texture: ผิวแผลเรียบ ไม่มีผง ไม่มีตุ่มนูนเดี่ยวชัด
  Distribution: จำนวนมากทั่วใบ โดยเฉพาะแผ่นใบกลาง
  Hard negatives: ไม่มีผงใต้ใบ (ตัด Downy); ไม่บุ๋มกลางแผลอย่างชัด (ตัด Anthracnose)
  Tie-break: ถ้า “วงแหวนชัด + กลางบุ๋ม” → Anthracnose; ถ้า “ฮาโลบาง+กลางซีด” หลายจุด → Cercospora

• Downy Mildew (สำคัญ: ต้องดูสองด้านใบ)
  Macro ด้านบน: ปื้นเหลืองซีด "เป็นเหลี่ยมตามเส้นใบ" เหมือน mosaic ขอบเขตชัดเจนตามแนวเส้นเลือดใบ
  Macro ด้านล่าง (สำคัญที่สุด): มี "ผง/ฟิล์ม/ขนสีเทา-ม่วง-ขาว" ชื้นเล็กน้อย อยู่ตรงข้ามกับจุดเหลืองด้านบน
  Micro/Texture: ผงใต้ใบละเอียด เกาะแน่นเป็นฟิล์มบาง ไม่ฟูแห้งแบบแป้ง (Powdery)
  Distribution: เริ่มตามช่องระหว่างเส้นใบ กระจายเป็นมุมมน/เหลี่ยมตามแนวเส้นเลือด
  Early stage: ด้านบนอาจมีแค่จุดเหลืองจาง ๆ กระจาย ยังไม่ชัดเจน ต้องพลิกดูด้านล่างให้ดี
  Hard negatives: ผงขาวฟูอยู่ "ด้านบนใบ" → Powdery (ไม่ใช่ Downy); จุดเหลืองไม่เป็นเหลี่ยม → อาจเป็นไวรัสหรืออาหารไม่เพียงพอ
  Tie-break: "บนเหลืองเป็นเหลี่ยม + ล่างมีฟิล์มเทา/ม่วง" = Downy (100%); "บนผงขาวฟู" = Powdery
• Leaf Blight
  Macro: ปื้นเน่าตายสีน้ำตาลไหม้ “ลามกว้าง” ขอบฟุ้งไม่คม; มักเริ่มจากขอบใบแล้วกินเข้าใน; มีหลายโซนเนื้อเยื่อตายต่อเนื่อง
  Micro/Texture: แห้งกรอบ ฉีกขาดง่ายบริเวณรอยต่อสุข-ป่วย
  Distribution: ปื้นใหญ่ 10–50% ของผืนใบ ไม่ใช่จุดเล็ก ๆ
  Hard negatives: ไม่มีผง/ตุ่มจำเพาะ; ถ้าเป็นแต่ “จุด ๆ” ให้ไปที่ Leaf Spot/Cercospora
  Tie-break: แผล “ใหญ่ลาม” = Blight; แผล “จุดเล็กกระจาย” = Leaf Spot group

• Leaf Spot Disease
  Macro: จุดกลม/รี ขนาดเล็ก–กลาง สีเทา-น้ำตาล ขอบอาจเข้มเล็กน้อย แต่ไม่คมจัด; ไม่บุ๋มเด่น; ไม่มีผง
  Micro/Texture: เรียบ เนื้อเยื่อรอบแผลยังเห็นสีเขียวแทรก
  Distribution: กระจายทั่วใบแบบสุ่ม
  Hard negatives: ไม่มีฮาโลกลางซีดคม (อ่อนกว่า Cercospora); ไม่มีวงแหวน+บุ๋ม (ตัด Anthracnose)
  ใช้เมื่อ: เป็น “spot ทั่วไป” ที่ไม่เข้าเกณฑ์จำเพาะของโรคอื่น

• Powdery Mildew
  Macro: ผง/แป้ง “สีขาว” ฟู แห้ง อยู่ “บนผิว” ใบ/ก้าน/ยอด เห็นชัดด้านบนใบ; มักปกคลุมจนลายเส้นใบตื้นหาย
  Micro/Texture: ขูดออกได้ ผิวด้าน ใยฟู
  Distribution: แผ่เป็นหย่อม ๆ บนผิวด้านบน มากกว่าด้านล่าง
  Hard negatives: ถ้าผงอยู่ “ใต้ใบ” สีเทา/ม่วง + บนใบเป็นเหลี่ยม → Downy
  Tie-break: ผงฟูขาวบน = Powdery; ฟิล์มใต้ใบ + mosaic เหลี่ยมบน = Downy

• Rust Disease
  Macro: “ตุ่มนูน” สีส้ม-น้ำตาล-สนิม (pustules) ขนาดจิ๋ว–เล็ก เมื่อขูดมีผงสนิมติดนิ้ว
  Micro/Texture: นูนเดี่ยว ๆ ชัด ไม่ใช่แป้งฟูปกคลุม
  Distribution: มักมากที่ “ด้านล่างใบ”
  Hard negatives: ถ้าเป็น “ตุ่มขาวครีม” → White Rust ไม่ใช่สนิม
  Tie-break: สีสนิมส้ม = Rust; นูนสีขาวครีม = White Rust

• White Rust Disease
  Macro: ตุ่มนูน/พอง “สีขาว-ครีม” ใต้ใบ (blister-like) ตรงกันกับปื้นซีดบนใบด้านบน
  Micro/Texture: นูนเรียบ ไม่เป็นผงแห้ง
  Distribution: เป็นหย่อมใต้ใบชัดเจน
  Hard negatives: สีและผิวไม่ใช่ “สนิมส้ม”; ไม่ใช่ “แป้งขาวฟู” บนผิว
  Tie-break: นูนขาวใต้ใบ = White Rust (ไม่ใช่ผง, ไม่ใช่สนิม)

[PESTS]

• Bemisia tabaci (Whitefly/แมลงหวี่ขาว)
  **สำคัญ**: ต้องดู "ใต้ใบ" ให้ละเอียด
  Direct sign: ตัวแมลงเล็ก **"ปีกคู่สีขาว/ขาวขุ่น"** เหมือนผงปุย ขนาด ~1-3 มม. เกาะกลุ่ม **"ใต้ใบ"**; 
  - ตัวเต็มวัย: มีปีก 2 คู่ สีขาวใส/ขาวขุ่น บิน/กระพือปีกเมื่อรบกวน
  - ตัวอ่อน (nymph): แบนราบสีเหลืองอ่อน/เขียวอ่อน เกาะนิ่ง ไม่ขยับ
  Indirect signs (สำคัญมาก): 
  - คราบน้ำหวานเหนียว (honeydew): ผิวใบด้านบนมันเงาเหมือนมีน้ำมัน
  - เขม่าดำ (sooty mold): จุดดำๆ บนผิวใบจากเชื้อราที่เกิดจากน้ำหวาน
  Distribution: ใต้ใบเป็นหลัก (ตัวแมลงไม่ชอบแสง), เส้นกลางใบ, รวมตัวเป็นกลุ่ม
  Look for: ใบด้านบนมีคราบดำ/มันเงา ให้พลิกดูใต้ใบทันที
  Hard negatives: ถ้าไม่มีปีกขาว + มีผิวเงินริ้ว + มูลดำกระจาย → Thrips
  Tie-break: เห็นปีกขาวชัด + คราบเหนียว/ราดำ = Bemisia (แน่นอน)

• Common Cutworm (หนอนกระทู้ผัก)
  **ลักษณะเฉพาะ**: หนอนสีเขียว/น้ำตาล/เทา ขนาด 3-5 ซม. ตัวอ้วนมน อยู่บน/ใกล้พืช
  Damage signs (สำคัญมาก):
  - รอยกัดขอบใบ **"ชิ้นใหญ่ ไม่เป็นระเบียบ"** ขาดหายไปเป็นช่วงๆ คล้ายถูกฉีก
  - ใบเป็นรูใหญ่ ขอบฉีกขาด ไม่เรียบ
  - อาจเห็นหนอนอยู่ใกล้ๆ รอยกัด (ซ่อนใต้ใบ/ดินในตอนกลางวัน)
  - มูลเม็ดดำเล็กๆ กระจายใกล้รอยกัด
  - บางครั้งโคนต้นถูกตัด (cut = หั่น/ตัด) - หนอนกัดรอบคอต้น
  Key differences:
  - ไม่ใช่รูกลมเล็กจำนวนมาก (Flea Beetle = รูเล็กๆ ถี่ๆ)
  - ไม่ใช่รูโปร่งแสง (Diamondback Moth = กินเนื้อใบชั้นบนเหลือผิวบาง)
  Tie-break: ชิ้นกัดใหญ่/ฉีกขาด/ไม่เป็นระเบียบ + เห็นหนอน = Common Cutworm

• Diamondback Moth
  Damage: “windowpane feeding” — กินเฉพาะเนื้อใบชั้นบน เหลือผิวบางโปร่งแสง หรือทะลุเป็นรูเหลี่ยมเล็ก ๆ เป็นกลุ่ม
  Host cue (ใช้ได้เฉพาะถ้า “เห็นรูปใบชัด”): พืชตระกูลกะหล่ำ (ใบหนา เส้นใบตาข่ายชัด)
  Hard negatives: ถ้าเป็น “เส้นทางในเนื้อใบ” ต่อเนื่องคดเคี้ยว → Leaf Miner
  Tie-break: โปร่งแสงเป็นปื้น/รูยุบลึกตื้น ๆ หลายจุด = Diamondback Moth

• Flea Beetle (ด้วงหมัดผัก)
  **ขนาดตัว**: เล็กมาก ~2-3 มม. (เล็กกว่าด้วงเต่าแตงแดงมาก)
  **ลักษณะตัว**: ทรงรีปีกแข็ง สีดำ/น้ำตาลเงา/โลหะ ขาเรียวยาว กระโดดได้เมื่อรบกวน
  **Damage**: 
  - “shot-holing” — รูพรุน **“กลมเล็ก 1-3 มม. ขนาดใกล้เคียงกัน”** จำนวนมากคล้ายถูกยิงลูกปราย
  - รูกลมสม่ำเสมอ ไม่ฉีกขาด
  Pattern: รูเล็กถี่ๆ ทั่วใบ โดยเฉพาะใบอ่อน
  **สำคัญ**: ตัวเล็กมาก สีดำ/น้ำตาลเงา ไม่ใช่สีส้มแดง
  Hard negatives: 
  - ถ้าตัวใหญ่ 5-8 มม. สีส้มแดง → Red Pumpkin Beetle (ไม่ใช่ Flea Beetle)
  - ถ้ารูใหญ่ไม่สม่ำเสมอ ฉีกขาด → Cutworm
  Tie-break: ตัวเล็ก+สีดำ/น้ำตาลเงา+รูกลมเล็กสม่ำเสมอ = Flea Beetle

• Leaf Miner
  Damage: “เส้นทางคดเคี้ยวในเนื้อใบ (serpentine mines)” สีซีด/ขาว กว้าง 0.5–3 มม.; ปลายทางอาจเห็นจุดดำ (หัว/มูล)
  Texture: ผิวใบชั้นนอกยังอยู่ ไม่ทะลุรู
  Hard negatives: ถ้าเป็นรูทะลุ/โปร่งแสงเป็นปื้น → Diamondback Moth
  Tie-break: มี “เส้นทาง” ชัด = Leaf Miner

• Leafhopper
  Direct sign: แมลงทรงลิ่มเล็ก ๆ (~2-3 มม.) สีเขียว/น้ำตาล/เหลือง ไม่ใช่สีส้มแดง; เดินเฉียงหรือดีดตัวหนีเมื่อรบกวน
  Symptom: "hopperburn" — สีซีด/เหลืองเป็นแถบตามเส้นใบ ขอบใบไหม้แห้งงอ; ไม่มีรูขาดทะลุชัดเจน
  Hard negatives: ไม่มีผงเชื้อ; ไม่ใช่ผิวเงินเงาพร้อมมูลดำ (ตัด Thrips); ถ้าเห็นตัวแมลงสีส้มแดงทรงรีขนาดใหญ่ → Red Pumpkin Beetle

• Red Pumpkin Beetle (ด้วงเต่าแตงแดง)
  **ขนาดตัว**: ใหญ่ ~5-8 มม. (ใหญ่กว่าด้วงหมัดผักมาก)
  **ลักษณะตัว**: ด้วงปีกแข็ง **"สีส้มแดงสด/แดงมันเงา"** ทรงรี/วงรี เกาะอยู่บนใบ
  **Damage**: 
  - รูฉีก "กลาง–ใหญ่ ไม่เป็นระเบียบ" ไม่สม่ำเสมอ
  - รูมักเป็นรูปครึ่งวงกลมหรือวงกลมใหญ่
  - มักพบบนพืชวงศ์แตง (แตงกวา แตงโม ฟักทอง)
  **สำคัญ**: ตัวใหญ่ สีส้มแดงสด ไม่ใช่สีดำ/น้ำตาลเล็ก
  Hard negatives: 
  - ถ้าตัวเล็ก 2-3 มม. สีดำ/น้ำตาลเงา → Flea Beetle (ไม่ใช่ Red Pumpkin Beetle)
  - ถ้าเป็นรูเล็กถี่สม่ำเสมอ → Flea Beetle
  Tie-break: ตัวใหญ่+สีส้มแดง+รูฉีกใหญ่ = Red Pumpkin Beetle
• Thrips
  Direct sign: ตัวแมลง **"ไม่มีปีกขาว"** ทรงเรียวยาวมาก สีเหลือง/น้ำตาล/ดำ ขนาด ~1-2 มม. (เล็กกว่า Bemisia)
  Symptom: "ผิวเงินเงา (silvering)" เป็นปื้นยาว/ริ้ว + "จุดดำเล็ก ๆ" (มูล) กระจาย; ผิวถูกขูดเป็นเส้นละเอียด
  Location: มักเริ่มที่ส่วนอ่อน/ยอดอ่อน ด้านบนใบชัด
  Hard negatives: ไม่มีผงแป้ง; **ไม่มีปีกขาว**; ถ้าเห็นปีกขาว + คราบเหนียว/ราดำ → Bemisia
  Tie-break: ไม่เห็นปีกขาว + ผิวเงินริ้ว + มูลดำจิ๋ว = Thrips; เห็นปีกขาวชัด + คราบเหนียว = Bemisia
==================== HARD EXCLUSIONS & TIE-BREAKERS ====================

1) ผง “ขาวฟูบนผิวด้านบน” → Powdery Mildew (ไม่ใช่ Downy)
2) ปื้นเหลือง “เป็นเหลี่ยมตามเส้นใบบน” + ฟิล์มเทา/ม่วง “ใต้ใบ” → Downy Mildew
3) ตุ่ม “สีสนิมส้ม” นูน ถูมีผง → Rust Disease ; ตุ่ม “ขาวครีม” ใต้ใบ → White Rust
4) วงแหวนซ้อน + กลางบุ๋ม + ขอบคมเข้ม → Anthracnose ; จุดเล็กกลางซีดขอบเข้มบาง ๆ จำนวนมาก → Cercospora
5) ปื้นไหม้ลามใหญ่/ขอบฟุ้ง → Leaf Blight ; จุดกระจายทั่วไป → Leaf Spot Disease
6) เส้นทางคดในเนื้อใบ (ไม่ทะลุ) → Leaf Miner ; โปร่งแสง/รูหน้าต่างหลายจุด → Diamondback Moth
7) รูพรุนเล็กถี่สม่ำเสมอ → Flea Beetle ; รอยกัดชิ้นใหญ่ฉีก/โคนต้นขาด → Common Cutworm
8) ผิวเงิน + มูลดำจิ๋ว → Thrips ; คราบเหนียวมันวาว + เขม่าดำ + ปีกขาวใต้ใบ → Bemisia tabaci
9) ถ้าหลักฐานสำคัญ “ไม่ปรากฏชัด” (เช่น ไม่เห็นด้านล่างใบ/ไม่เห็นผิวเงิน/ไม่เห็นเส้นทางเหมืองใบ) → No disease or pest found
10) **รู vs จุดโรค**: รูขาดเป็นรูโปร่ง (ทะลุถึงด้านหลัง) + ขอบฉีกไม่เป็นระเบียบ = แมลงกัดกิน (Flea Beetle/Red Pumpkin Beetle/Common Cutworm) ; จุดสีเปลี่ยนแต่ไม่ทะลุ + ขอบเรียบ = โรคใบจุด
11) **Leafhopper vs Red Pumpkin Beetle**: เห็นตัวแมลงสีส้มแดงสด/แดงมันเงา ทรงรี ขนาดใหญ่ (~5-8 มม.) เกาะนิ่ง ๆ = Red Pumpkin Beetle ; เห็นแมลงทรงลิ่มเล็ก ๆ (~2-3 มม.) สีเขียว/น้ำตาล ดีดตัวหนี = Leafhopper
12) **Bemisia tabaci vs Thrips**: เห็นปีกขาวคู่ชัด + คราบเหนียว/ราดำ = Bemisia ; ไม่เห็นปีกขาว + ผิวเงินริ้ว + มูลดำจิ๋ว = Thrips

QUALITY CHECK (ก่อนตัดสิน):
- ตรวจสอบทุกซอกมุมของใบในรูป อย่าดูแค่ส่วนเดียว
- ถ้าเห็นอาการผิดปกติใด ๆ (จุด ปื้น สีซีด ผง ฟิล์ม) อย่าตอบ Healthy ให้เลือกโรคที่ใกล้เคียงที่สุด
- เห็น “สัญญาณชี้ขาด” อย่างน้อย 1–2 รายการของคลาสนั้น ๆ บนพื้นที่โฟกัสชัด (ไม่เบลอ/ไม่หลุดโฟกัส)
- ถ้าสัญญาณขัดแย้งกัน (เช่น ผงขาวบน + ฟิล์มม่วงใต้ใบ ไม่ชัดว่าชนิดใดเด่น) → No disease or pest found
- หลีกเลี่ยงการทึกทักจาก “รูปทรงใบ = ชนิดพืช” เว้นแต่เห็นลักษณะใบจำเพาะชัดมากจริง ๆ

OUTPUT FORMAT (จำกัดอย่างเคร่งครัด):
- พิมพ์ “ชื่อคลาสเพียว ๆ” จากรายการที่กำหนด หรือ “No disease or pest found”
- ห้ามเพิ่มคำอธิบาย/สัญลักษณ์/ความมั่นใจ/บรรทัดอื่นใด
""".strip()
    try:
        result = service.analyze_image(image_path, prompt, temperature=0.2)
        
        if result["success"]:
            content = result["content"].strip()
            analysis = _extract_json(content)
            
            # ถ้าไม่สามารถแปลงเป็น JSON ได้ (หรือได้ dict ว่าง) 
            # ให้ตรวจสอบว่าเป็นการตอบกลับแบบ plain text หรือไม่
            if not analysis or not isinstance(analysis, dict) or len(analysis) == 0:
                # Kimi ตอบกลับมาเป็นชื่อคลาสเพียวๆ ให้แปลงเป็นรูปแบบที่ถูกต้อง
                class_name = content.strip()
                
                # แมปชื่อคลาสเป็น category
                disease_names = [
                    "Anthracnose", "Cercospora Leaf Spot", "Downy Mildew", 
                    "Leaf Blight", "Leaf Spot Disease", "Powdery Mildew",
                    "Rust Disease", "White Rust Disease"
                ]
                pest_names = [
                    "Bemisia tabaci", "Common Cutworm", "Diamondback Moth",
                    "Flea Beetle", "Leaf Miner", "Leafhopper",
                    "Red Pumpkin Beetle", "Thrips"
                ]
                
                # แมปชื่อคลาสเป็น ID (จาก DISEASE_CLASSES และ PEST_CLASSES)
                CLASS_ID_MAPPING = {
                    # Diseases
                    "Anthracnose": 33,
                    "Cercospora Leaf Spot": 31,
                    "Downy Mildew": 30,
                    "Leaf Blight": 32,
                    "Leaf Spot Disease": 29,
                    "Powdery Mildew": 35,
                    "Rust Disease": 34,
                    "White Rust Disease": 36,
                    # Pests
                    "Bemisia tabaci": 42,
                    "Common Cutworm": 41,
                    "Diamondback Moth": 40,
                    "Flea Beetle": 39,
                    "Leaf Miner": 43,
                    "Leafhopper": 46,
                    "Red Pumpkin Beetle": 38,
                    "Thrips": 45
                }
                
                if class_name == "No disease or pest found" or not class_name:
                    analysis = {
                        "is_plant": True,
                        "is_detected": False,
                        "is_healthy": True,
                        "category": "healthy",
                        "target_name_th": "พืชสุขภาพดี",
                        "target_name_en": "Healthy",
                        "confidence": "high",
                        "description": "ไม่พบโรคหรือศัตรูพืชในภาพ"
                    }
                elif class_name in disease_names:
                    analysis = {
                        "is_plant": True,
                        "is_detected": True,
                        "is_healthy": False,
                        "category": "disease",
                        "target_name_en": class_name,
                        "target_name_th": DISEASE_NAME_MAPPING.get(class_name, class_name),
                        "confidence": "high",
                        "detected_class_id": CLASS_ID_MAPPING.get(class_name)
                    }
                elif class_name in pest_names:
                    analysis = {
                        "is_plant": True,
                        "is_detected": True,
                        "is_healthy": False,
                        "category": "pest",
                        "target_name_en": class_name,
                        "target_name_th": PEST_NAME_MAPPING.get(class_name, class_name),
                        "confidence": "high",
                        "detected_class_id": CLASS_ID_MAPPING.get(class_name)
                    }
                else:
                    # กรณีอื่นๆ ให้ถือว่าไม่แน่ใจ
                    analysis = {
                        "is_plant": True,
                        "is_detected": False,
                        "is_healthy": True,
                        "category": "healthy",
                        "target_name_th": "พืชสุขภาพดี",
                        "target_name_en": "Healthy",
                        "confidence": "medium"
                    }
            
            return {
                "success": True,
                "analysis": analysis,
                "raw_response": result["content"]
            }
        else:
            return result
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def analyze_plant_disease(image_path: str) -> Dict[str, Any]:
    """รักษาฟังก์ชันเดิมไว้เพื่อ compatibility แต่ใช้ logic ใหม่"""
    return analyze_plant_health(image_path)


def analyze_plant_pest(image_path: str) -> Dict[str, Any]:
    """รักษาฟังก์ชันเดิมไว้เพื่อ compatibility แต่ใช้ logic ใหม่"""
    return analyze_plant_health(image_path)


def chat_with_assistant(message: str, context: Optional[str] = None) -> Dict[str, Any]:
    """สนทนากับผู้ช่วย AI เกี่ยวกับการเกษตร"""
    service = get_kimi_service()
    
    system_prompt = """คุณเป็นผู้ช่วยผู้เชี่ยวชาญด้านการเกษตรและการปลูกพืชสวนครัวที่รอบรู้และเป็นกันเอง
ให้คำแนะนำที่เป็นประโยชน์ ถูกต้อง ตามหลักวิชาการ และเข้าใจง่าย ตอบเป็นภาษาไทย
คุณจะเน้นข้อมูลเรื่องโรคพืช แมลงศัตรูพืช และการใช้ระบบ CCTV ช่วยในการดูแลสวน"""
    
    if context:
        full_prompt = f"{system_prompt}\n\nบริบทปัจจุบัน: {context}\n\nคำถาม: {message}"
    else:
        full_prompt = f"{system_prompt}\n\nคำถาม: {message}"
    
    return service.analyze_text(full_prompt)
