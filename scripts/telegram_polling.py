"""
Telegram Bot Polling Mode (ไม่ต้องใช้ ngrok)
ใช้สำหรับ development แทน webhook
"""

import os
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Import handlers จาก telegram_bot
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_bot import process_update, delete_webhook


async def poll_updates():
    """รับข้อความจาก Telegram แบบ polling"""
    if not BOT_TOKEN:
        print("❌ ไม่พบ TELEGRAM_BOT_TOKEN")
        return
    
    # ลบ webhook ก่อนเพื่อใช้ polling
    print("🗑️ กำลังลบ webhook ปัจจุบัน...")
    await delete_webhook()
    
    print("🤖 Bot เริ่มทำงานแบบ Polling...")
    print("   กด Ctrl+C เพื่อหยุด")
    
    offset = 0
    
    while True:
        try:
            url = f"{TELEGRAM_API_URL}/getUpdates"
            params = {
                "offset": offset,
                "limit": 100,
                "timeout": 30
            }
            
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if not data.get("ok"):
                print(f"❌ API Error: {data}")
                await asyncio.sleep(5)
                continue
            
            updates = data.get("result", [])
            
            for update in updates:
                # อัปเดต offset
                update_id = update.get("update_id")
                if update_id:
                    offset = update_id + 1
                
                # ประมวลผล update
                await process_update(update)
            
            # หน่วงเล็กน้อยถ้าไม่มีข้อความ
            if not updates:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n👋 หยุด polling")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Telegram Bot - Polling Mode")
    print("=" * 50)
    print("ไม่ต้องใช้ ngrok - เหมาะสำหรับ development\n")
    
    try:
        asyncio.run(poll_updates())
    except KeyboardInterrupt:
        print("\n👋 ปิดโปรแกรม")
