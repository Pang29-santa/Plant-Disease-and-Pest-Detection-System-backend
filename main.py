"""
Vegetable & Agriculture API
FastAPI Backend for MongoDB
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from database import connect_db, close_db
from routes import all_routers
from services.scheduler import start_harvest_scheduler
from logging_config import setup_logging
from utils.exceptions import AppException
import logging

# โหลดค่าจาก .env
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# ============================================
# CORS Configuration (จาก .env)
# ============================================
def get_cors_origins():
    """ดึงค่า CORS origins จาก .env"""
    origins = os.getenv("CORS_ORIGINS", "*")
    if origins == "*":
        return ["*"]
    return [origin.strip() for origin in origins.split(",")]


def get_cors_methods():
    """ดึงค่า CORS methods จาก .env"""
    methods = os.getenv("CORS_ALLOW_METHODS", "*")
    if methods == "*":
        return ["*"]
    return [method.strip() for method in methods.split(",")]


def get_cors_headers():
    """ดึงค่า CORS headers จาก .env"""
    headers = os.getenv("CORS_ALLOW_HEADERS", "*")
    if headers == "*":
        return ["*"]
    return [header.strip() for header in headers.split(",")]


# ============== Lifespan ==============
NGROK_DOMAIN = "unvengeful-leeanne-interpressure.ngrok-free.dev"


def _get_ngrok_url():
    """ดึง ngrok URL ถ้ารันอยู่ (sync)"""
    import requests as req
    try:
        resp = req.get("http://localhost:4040/api/tunnels", timeout=3)
        for t in resp.json().get("tunnels", []):
            if t.get("proto") == "https":
                return t["public_url"]
        tunnels = resp.json().get("tunnels", [])
        if tunnels:
            return tunnels[0]["public_url"]
    except Exception:
        pass
    return None


def _start_ngrok_if_not_running():
    """เปิด ngrok อัตโนมัติถ้ายังไม่ได้รัน"""
    import subprocess
    import time

    # ตรวจว่ารันอยู่แล้วไหม
    url = _get_ngrok_url()
    if url:
        logger.info(f"✅ ngrok รันอยู่แล้ว: {url}")
        return url

    # หา ngrok.exe
    ngrok_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python310", "Scripts", "ngrok.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ngrok", "ngrok.exe"),
        "ngrok",  # จาก PATH
    ]
    ngrok_exe = None
    for p in ngrok_paths:
        if os.path.isfile(p) or p == "ngrok":
            ngrok_exe = p
            break

    if not ngrok_exe:
        logger.warning("⚠️  ไม่พบ ngrok.exe — ข้ามการเปิด ngrok")
        return None

    logger.info(f"🚀 เปิด ngrok อัตโนมัติ: {ngrok_exe}")
    try:
        subprocess.Popen(
            [ngrok_exe, "http", "8888", f"--domain={NGROK_DOMAIN}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        # รอให้ ngrok พร้อม (สูงสุด 10 วิ)
        for _ in range(10):
            time.sleep(1)
            url = _get_ngrok_url()
            if url:
                logger.info(f"✅ ngrok เปิดสำเร็จ: {url}")
                return url
        logger.warning("⚠️  ngrok เปิดแล้วแต่ยังไม่มี tunnel — ตรวจสอบที่ http://localhost:4040")
    except FileNotFoundError:
        logger.warning(f"⚠️  ไม่พบ '{ngrok_exe}' — ติดตั้ง ngrok ก่อน")
    except Exception as e:
        logger.warning(f"⚠️  เปิด ngrok ไม่สำเร็จ: {e}")
    return None



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Re-apply logging หลัง uvicorn init (uvicorn จะ override handlers ที่ตั้งไว้ก่อน)
    setup_logging()
    logger.info("🚀 Starting up application...")
    await connect_db()
    start_harvest_scheduler()


    # ── Startup Diagnostics ──────────────────────────────────────
    logger.info("🔎 กำลังตรวจสอบ / เปิด ngrok & Telegram webhook...")
    ngrok_url = _start_ngrok_if_not_running()

    # ตรวจสอบ Telegram webhook info
    from telegram_bot import get_webhook_info
    webhook_info = await get_webhook_info()
    if webhook_info:
        wh_url = webhook_info.get("url", "(ไม่มี)")
        pending = webhook_info.get("pending_update_count", 0)
        last_err = webhook_info.get("last_error_message")
        if wh_url:
            logger.info(f"✅ Telegram webhook ปัจจุบัน: {wh_url} | pending={pending}")
            if last_err:
                logger.warning(f"⚠️  Telegram webhook error ล่าสุด: {last_err}")
        else:
            logger.warning("⚠️  Telegram webhook ยังไม่ได้ตั้งค่า (URL ว่าง)")
            if ngrok_url:
                logger.info(f"💡 ตั้ง webhook ได้ที่: GET /webhook/telegram/setup?host={ngrok_url}")
    else:
        logger.warning("⚠️  ไม่สามารถดึง Telegram webhook info ได้ (TELEGRAM_BOT_TOKEN อาจไม่ได้ตั้งค่า)")
    # ─────────────────────────────────────────────────────────────

    logger.info("✅ Application ready!")
    yield
    await close_db()
    logger.info("❌ Application shutdown!")


# ============== FastAPI App ==============
app = FastAPI(
    title="Vegetable & Agriculture API",
    description="API สำหรับจัดการข้อมูลผัก โรคพืช การปลูก และการเก็บเกี่ยว",
    version="1.0.0",
    lifespan=lifespan
)

# ============== CORS Configuration (ต้องลงทะเบียนก่อน middleware อื่น) ==============
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true",
    allow_methods=get_cors_methods(),
    allow_headers=get_cors_headers(),
)

# ============== Exception Handlers ==============
def cors_response(request: Request, content: dict, status_code: int):
    """สร้าง JSON response พร้อม CORS headers"""
    origin = request.headers.get("origin", "")
    allowed_origins = get_cors_origins()
    
    # ตรวจสอบว่า origin อยู่ใน allowed list หรือเป็น *
    if "*" in allowed_origins or origin in allowed_origins:
        pass
    else:
        origin = allowed_origins[0] if allowed_origins else "*"
    
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Access-Control-Allow-Origin": origin if origin else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handler สำหรับ Custom Exceptions ของเรา"""
    return cors_response(
        request,
        {
            "ok": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        },
        exc.status_code
    )

@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    """Handler สำหรับดักจับทุก Error ที่เราไม่ได้จัดการไว้ (Uncaught Errors)"""
    logger.error(f"🔥 Uncaught Error: {str(exc)}", exc_info=True)
    return cors_response(
        request,
        {
            "ok": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่ภายหลัง" if not os.getenv("DEBUG") else str(exc)
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR
    )

# ============== BYPASS AUTH MIDDLEWARE ==============
# ปลดล็อกทุก API ไม่ต้องใช้ token แต่ถ้ามี token จริงๆ ให้ใช้ข้อมูลจริง
@app.middleware("http")
async def bypass_auth_middleware(request: Request, call_next):
    """
    Middleware สำหรับปลดล็อก authentication
    - ถ้ามี Authorization header ที่ valid ใช้ข้อมูลจาก token
    - ถ้าไม่มี ใช้ bypass user (ปลดล็อก API)
    """
    from jose import jwt, JWTError
    
    auth_header = request.headers.get("Authorization")
    user_data = None
    is_authenticated = False
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("JWT_ALGORITHM", "HS256")])
            user_id = payload.get("sub")
            if user_id:
                user_data = {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "fullname": payload.get("fullname"),
                    "role": payload.get("role", "user"),
                }
                is_authenticated = True
        except JWTError:
            pass  # Token ไม่ valid ให้ fallback ไป bypass
    
    # ถ้าไม่มี token หรือ token ไม่ valid - ใช้ bypass user
    if not user_data:
        user_data = {
            "user_id": 1,  # ใช้ตัวเลขแทน string
            "email": "admin@vegetable.com",
            "fullname": "Admin User",
            "role": "admin",
        }
        is_authenticated = True  # ปลดล็อก API
    
    request.state.user = user_data
    request.state.is_authenticated = is_authenticated
    
    response = await call_next(request)
    return response

# ============== Static Files ==============
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============== Include Routers ==============
for router in all_routers:
    app.include_router(router)


# ============== Telegram Bot Webhook ==============
from telegram_bot import process_update, set_webhook, delete_webhook, get_webhook_info

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Webhook endpoint สำหรับรับข้อความจาก Telegram Bot
    Telegram จะส่ง update มาที่นี่เมื่อมีคนพิมพ์ข้อความถึง bot
    """
    try:
        update = await request.json()
        update_id = update.get("update_id", "?")
        logger.info(f"📩 Telegram webhook รับ update_id={update_id} จาก {request.client.host if request.client else 'unknown'}")
        await process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Error processing Telegram update: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@app.get("/webhook/telegram/setup")
async def setup_telegram_webhook(host: str = None):
    """
    ตั้งค่า webhook สำหรับ Telegram Bot
    ใช้เมื่อ deploy หรือเปลี่ยน URL
    
    Parameters:
    - host: domain ของเซิร์ฟเวอร์ (เช่น https://your-domain.com)
           ถ้าไม่ระบุจะใช้ localhost สำหรับ development
    """
    if not host:
        # สำหรับ development ใช้ ngrok หรือ localhost
        host = f"http://localhost:{os.getenv('PORT', 8888)}"
    
    webhook_url = f"{host}/webhook/telegram"
    success = await set_webhook(webhook_url)
    
    if success:
        return {
            "success": True,
            "message": "Webhook set successfully",
            "webhook_url": webhook_url
        }
    else:
        return {
            "success": False,
            "message": "Failed to set webhook",
            "webhook_url": webhook_url
        }


@app.get("/webhook/telegram/info")
async def telegram_webhook_info():
    """ดูข้อมูล webhook ปัจจุบันของ Telegram Bot"""
    info = await get_webhook_info()
    return info or {"error": "Failed to get webhook info"}


@app.post("/webhook/telegram/delete")
async def remove_telegram_webhook():
    """ลบ webhook ของ Telegram Bot (ใช้สำหรับ switch ไปใช้ polling)"""
    success = await delete_webhook()
    return {
        "success": success,
        "message": "Webhook deleted" if success else "Failed to delete webhook"
    }


# ============== MAIN ==============
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8888))
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        reload=True, 
        reload_excludes=["static/*", "static", "*.jpg", "*.png", "*.jpeg", "*.webp", "static/img/temp/*"]
    )
