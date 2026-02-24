"""
Telegram Bot Handler
จัดการคำสั่งและข้อความจาก Telegram Bot
"""

import os
import random
import string
import logging
import requests
from datetime import datetime, timedelta
from database import get_collection

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def generate_verification_code(length=6):
    """สร้างรหัสยืนยันแบบสุ่ม"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def send_message(chat_id: str, text: str, parse_mode="Markdown"):
    """ส่งข้อความไปยัง Telegram
    
    Args:
        chat_id: Telegram chat ID
        text: ข้อความที่จะส่ง
        parse_mode: "Markdown" หรือ "HTML" (default: Markdown สำหรับลิงก์ที่กดได้)
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN ไม่ได้ตั้งค่าใน .env")
        return False
    
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            logger.debug(f"✉️  ส่งข้อความถึง chat_id={chat_id} สำเร็จ")
            return True
        else:
            logger.warning(f"⚠️  ส่งข้อความล้มเหลว chat_id={chat_id}: {result.get('description')}")
            # ถ้า Markdown ไม่สำเร็จ ลองส่งแบบไม่มี parse_mode
            if parse_mode != "":
                logger.info(f"🔄 Retry ส่งข้อความแบบ plain text ถึง chat_id={chat_id}")
                payload["parse_mode"] = ""
                response = requests.post(url, json=payload, timeout=10)
                result = response.json()
                if result.get("ok"):
                    logger.debug(f"✉️  Retry สำเร็จ chat_id={chat_id}")
                else:
                    logger.error(f"❌ Retry ล้มเหลว chat_id={chat_id}: {result.get('description')}")
                return result.get("ok", False)
            return False
    except Exception as e:
        logger.exception(f"❌ Exception ขณะส่งข้อความถึง chat_id={chat_id}: {e}")
        return False


async def handle_start(chat_id: str, user_info: dict):
    """จัดการคำสั่ง /start"""
    first_name = user_info.get("first_name", "")
    username = user_info.get("username", "")
    
    # สร้างรหัสยืนยันใหม่
    verification_code = generate_verification_code()
    
    # บันทึกรหัสลงฐานข้อมูลชั่วคราว (รอให้ผู้ใช้ยืนยันบนเว็บ)
    temp_codes_collection = get_collection("telegram_temp_codes")
    
    await temp_codes_collection.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
                "verification_code": verification_code,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=10),
                "verified": False
            }
        },
        upsert=True
    )
    
    # ส่งข้อความตอบกลับ (ใช้ Markdown)
    message = f"""👋 สวัสดี *{first_name}*!

ยินดีต้อนรับสู่ *Vegetable Project Bot* 🌱

รหัสยืนยันของคุณคือ:
`{verification_code}`

⏰ รหัสนี้จะหมดอายุใน 10 นาที

กรุณานำรหัสนี้ไปกรอกในหน้าเว็บเพื่อเชื่อมต่อบัญชีของคุณ

👉 @vegetableproject_chatbot"""
    
    send_message(chat_id, message)


async def handle_help(chat_id: str):
    """จัดการคำสั่ง /help"""
    message = f"""*📖 คำสั่งที่ใช้ได้*

/start - ขอรหัสยืนยันการเชื่อมต่อ
/help - แสดงคำสั่งทั้งหมด
/status - ตรวจสอบสถานะการเชื่อมต่อ
/test - ทดสอบการแจ้งเตือน

*💡 วิธีใช้งาน*
1\. พิมพ์ /start เพื่อรับรหัสยืนยัน
2\. นำรหัสไปกรอกในหน้าเว็บ Vegetable Project
3\. รอรับการแจ้งเตือนจากระบบ

*🆘 ต้องการความช่วยเหลือ?*
ติดต่อผู้ดูแลระบบ"""
    
    send_message(chat_id, message)


async def handle_status(chat_id: str):
    """จัดการคำสั่ง /status"""
    # ตรวจสอบว่า chat_id นี้เชื่อมต่อกับผู้ใช้คนไหน
    telegram_collection = get_collection("telegram_connections")
    connection = await telegram_collection.find_one({
        "chat_id": chat_id,
        "status": "active"
    })
    
    if connection:
        user_id = connection.get("user_id")
        connected_at = connection.get("connected_at")
        
        message = f"""*✅ สถานะการเชื่อมต่อ*

สถานะ: *เชื่อมต่อแล้ว*
User ID: `{user_id}`
เชื่อมต่อเมื่อ: {connected_at.strftime('%Y-%m-%d %H:%M') if connected_at else 'N/A'}

คุณจะได้รับการแจ้งเตือนเมื่อ:
• ตรวจพบโรคพืช
• ตรวจพบศัตรูพืช
• มีการแจ้งเตือนจากระบบ"""
    else:
        message = f"""*❌ สถานะการเชื่อมต่อ*

สถานะ: *ยังไม่ได้เชื่อมต่อ*

กรุณาพิมพ์ /start เพื่อขอรหัสยืนยัน
และนำรหัสไปกรอกในหน้าเว็บ Vegetable Project"""
    
    send_message(chat_id, message)


async def handle_test(chat_id: str):
    """จัดการคำสั่ง /test"""
    message = f"""*🧪 ทดสอบการแจ้งเตือน*

นี่คือข้อความทดสอบจาก Vegetable Project Bot

หากคุณเห็นข้อความนี้ แสดงว่าการแจ้งเตือนทำงานปกติ ✅

_เวลา: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_"""
    
    send_message(chat_id, message)


async def handle_unknown(chat_id: str, text: str):
    """จัดการข้อความที่ไม่รู้จัก"""
    message = f"""*❓ ไม่เข้าใจคำสั่ง*

ข้อความ "{text}" ไม่ใช่คำสั่งที่รองรับ

พิมพ์ /help เพื่อดูคำสั่งทั้งหมด"""
    
    send_message(chat_id, message)


async def process_update(update: dict):
    """
    ประมวลผล update ที่ได้รับจาก Telegram
    """
    update_id = update.get("update_id", "?")
    logger.info(f"📨 รับ Telegram update_id={update_id}")

    if "message" not in update:
        logger.debug(f"⏭️  update_id={update_id} ไม่มี message field — ข้ามไป")
        return
    
    message = update["message"]
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    
    # ข้อมูลผู้ใช้
    from_user = message.get("from", {})
    user_info = {
        "first_name": from_user.get("first_name", ""),
        "last_name": from_user.get("last_name", ""),
        "username": from_user.get("username", "")
    }
    username_display = user_info["username"] or user_info["first_name"] or "unknown"
    
    # รับข้อความ
    text = message.get("text", "").strip()
    logger.info(f"💬 ข้อความจาก @{username_display} (chat_id={chat_id}): '{text}'")
    
    if not text:
        logger.debug(f"⏭️  chat_id={chat_id} ส่ง update ที่ไม่มีข้อความ — ข้ามไป")
        return
    
    # จัดการคำสั่ง
    if text.startswith("/"):
        command = text.split()[0].lower()
        logger.info(f"⚙️  คำสั่ง '{command}' จาก chat_id={chat_id}")
        
        if command == "/start":
            await handle_start(chat_id, user_info)
        elif command == "/help":
            await handle_help(chat_id)
        elif command == "/status":
            await handle_status(chat_id)
        elif command == "/test":
            await handle_test(chat_id)
        else:
            logger.warning(f"❓ ไม่รู้จักคำสั่ง '{command}' จาก chat_id={chat_id}")
            await handle_unknown(chat_id, text)
    else:
        # ถ้าไม่ใช่คำสั่ง ให้ตอบกลับทั่วไป
        logger.debug(f"💬 plain text จาก chat_id={chat_id} — ส่ง handle_unknown")
        await handle_unknown(chat_id, text)


async def set_webhook(webhook_url: str):
    """
    ตั้งค่า webhook สำหรับ Telegram Bot
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ ไม่สามารถตั้ง webhook: TELEGRAM_BOT_TOKEN ไม่ได้ตั้งค่า")
        return False
    
    logger.info(f"📡 กำลังตั้งค่า Telegram webhook → {webhook_url}")
    try:
        url = f"{TELEGRAM_API_URL}/setWebhook"
        payload = {
            "url": webhook_url,
            "allowed_updates": ["message"]
        }
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            logger.info(f"✅ ตั้งค่า Telegram webhook สำเร็จ: {webhook_url}")
            return True
        else:
            logger.error(f"❌ ตั้งค่า webhook ล้มเหลว: {result.get('description')} | URL={webhook_url}")
            return False
    except Exception as e:
        logger.exception(f"❌ Exception ขณะตั้งค่า webhook: {e}")
        return False


async def delete_webhook():
    """
    ลบ webhook ของ Telegram Bot
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ ไม่สามารถลบ webhook: TELEGRAM_BOT_TOKEN ไม่ได้ตั้งค่า")
        return False
    
    logger.info("🗑️  กำลังลบ Telegram webhook...")
    try:
        url = f"{TELEGRAM_API_URL}/deleteWebhook"
        response = requests.post(url, timeout=10)
        result = response.json()
        ok = result.get("ok", False)
        if ok:
            logger.info("✅ ลบ Telegram webhook สำเร็จ")
        else:
            logger.warning(f"⚠️  ลบ webhook ไม่สำเร็จ: {result}")
        return ok
    except Exception as e:
        logger.exception(f"❌ Exception ขณะลบ webhook: {e}")
        return False


async def get_webhook_info():
    """
    ดูข้อมูล webhook ปัจจุบัน
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️  ไม่สามารถดู webhook info: TELEGRAM_BOT_TOKEN ไม่ได้ตั้งค่า")
        return None
    
    logger.info("🔍 กำลังตรวจสอบ Telegram webhook info...")
    try:
        url = f"{TELEGRAM_API_URL}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        result = response.json()
        if result.get("ok"):
            info = result.get("result", {})
            current_url = info.get("url", "(ไม่มี)")
            pending = info.get("pending_update_count", 0)
            last_error = info.get("last_error_message", None)
            logger.info(f"📋 Webhook URL: {current_url} | Pending: {pending}")
            if last_error:
                logger.warning(f"⚠️  Webhook last error: {last_error}")
            return info
        logger.error(f"❌ getWebhookInfo ล้มเหลว: {result}")
        return None
    except Exception as e:
        logger.exception(f"❌ Exception ขณะดึง webhook info: {e}")
        return None
