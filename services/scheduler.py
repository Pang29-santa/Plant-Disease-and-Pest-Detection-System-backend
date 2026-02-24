import asyncio
import logging
from datetime import datetime, timedelta
from bson import ObjectId
from database import get_collection
from telegram_bot import send_message

logger = logging.getLogger(__name__)

async def check_harvest_tomorrow():
    """
    ตรวจสอบข้อมูลการปลูก หากถึงวันเก็บเกี่ยวในวันพรุ่งนี้ จะส่งแจ้งเตือนผ่าน Telegram
    """
    # รอ 10 วินาทีให้ระบบต่างๆ เปิดเสร็จก่อน
    await asyncio.sleep(10)
    
    while True:
        try:
            now = datetime.now()
            tomorrow = now + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")

            planting_collection = get_collection("planting_veg")
            plot_collection = get_collection("plots")
            user_collection = get_collection("users")

            # หากใช้ user_id เป็น int ตอนอ้างอิง
            # ตรวจสอบแปลงที่กำลังปลูกอยู่ (status = 1) และวันเก็บเกี่ยว = พรุ่งนี้ และยังไม่เคยแจ้งเตือน
            cursor = planting_collection.find({
                "status": 1,
                "harvest_date": tomorrow_str,
                "harvest_notified": {"$ne": True}
            })

            async for planting in cursor:
                planting_id = planting.get("_id")
                plot_object_id = planting.get("plot_object_id")
                veg_name = planting.get("vegetable_name", "ผัก")

                if not plot_object_id:
                    continue

                plot = await plot_collection.find_one({"_id": ObjectId(plot_object_id)})
                if not plot:
                    continue

                user_id = plot.get("user_id")
                plot_name = plot.get("plot_name", "ไม่ระบุชื่อ") or plot.get("name", "ไม่ระบุชื่อ")

                if not user_id:
                    continue

                # หาผู้ใช้
                # ลองหาทั้งแบบ int และ str
                user = await user_collection.find_one({
                    "$or": [{"user_id": user_id}, {"id": user_id}, {"_id": user_id}]
                })
                
                # Check if user exists and has telegram connected
                if user and user.get("telegram_chat_id"):
                    chat_id = user["telegram_chat_id"]
                    msg = (
                        f"🔔 <b>แจ้งเตือนการเก็บเกี่ยว!</b>\n\n"
                        f"🌱 แปลง: <b>{plot_name}</b>\n"
                        f"🥬 ถึงกำหนดเก็บเกี่ยว <b>{veg_name}</b> ในวันพรุ่งนี้ ({tomorrow_str})\n\n"
                        f"อย่าลืมไปจัดการและบันทึกข้อมูลการเก็บเกี่ยวในระบบนะครับ!"
                    )
                    success = send_message(chat_id, msg, parse_mode="HTML")
                    if success:
                        await planting_collection.update_one(
                            {"_id": planting_id},
                            {"$set": {"harvest_notified": True}}
                        )
                        logger.info(f"✅ แจ้งเตือน Telegram การเก็บเกี่ยวพรุ่งนี้ ส่งสำเร็จ (User ID: {user_id})")
                    else:
                        logger.warning(f"⚠️ ไม่สามารถส่งแจ้งเตือน Telegram (User ID: {user_id})")
                        
        except Exception as e:
            logger.error(f"❌ Error in harvest notification scheduler: {e}")
        
        # รันเช็คทุกๆ 1 ชั่วโมง
        await asyncio.sleep(3600)

_task = None

def start_harvest_scheduler():
    global _task
    if _task is None:
        logger.info("🕒 เริ่มระบบเช็คการเก็บเกี่ยวและแจ้งเตือนอัตโนมัติ")
        _task = asyncio.create_task(check_harvest_tomorrow())
