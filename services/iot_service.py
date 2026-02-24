import os
import requests
import asyncio
from typing import Optional

# โหลดค่าจาก Environment Variables
ARDUINO_IP = os.getenv("ARDUINO_IP", "192.168.1.100")  # IP ของ Arduino/ESP
DEFAULT_SPRAY_DURATION = int(os.getenv("DEFAULT_SPRAY_DURATION", "5"))

def trigger_sprayer(duration: Optional[int] = None):
    """
    ส่งคำสั่งไปยัง Arduino เพื่อเปิดเครื่องพ่นน้ำ
    ส่งคำสั่งในรูปแบบ: http://{host}/sprayer?duration={seconds}
    """
    if duration is None:
        duration = DEFAULT_SPRAY_DURATION
        
    async def _send():
        try:
            url = f"http://{ARDUINO_IP}/sprayer?duration={duration}"
            print(f"🚀 [IOT] Sending spray command to: {url}")
            
            # ใช้ timeout สั้นๆ เพื่อไม่ให้กระทบประสิทธิภาพของระบบหลัก
            r = requests.get(url, timeout=3)
            
            if r.status_code == 200:
                print(f"✅ [IOT] Sprayer triggered successfully on {ARDUINO_IP}")
                return True
            else:
                print(f"❌ [IOT] Arduino responded with status: {r.status_code}")
                return False
        except Exception as e:
            print(f"⚠️ [IOT] Failed to connect to Arduino: {e}")
            return False

    # ส่งแบบ Background Task (ไม่รอผล เพื่อให้ AI ตอบหน้าเว็บได้เร็ว)
    asyncio.create_task(_send())
    return True
