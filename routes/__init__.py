"""
API Routes Package
รวมทุก router ของแอปพลิเคชัน
"""

from fastapi import APIRouter

from .health import router as health_router
from .auth import router as auth_router
from .vegetables import router as vegetables_router
from .nutrition import router as nutrition_router
from .diseases_pest import router as diseases_pest_router
from .locations import router as locations_router
from .users import router as users_router
from .plots import router as plots_router
from .cctv import router as cctv_router
from .planting import router as planting_router
from .detection import router as detection_router
from .telegram import router as telegram_router
from .ai_detection import router as ai_detection_router
from .dashboard import router as dashboard_router
from .admin_database import router as admin_database_router
from .contact import router as contact_router

# [NEW] Routes ที่เพิ่มมาจากต้นฉบับ
from .validation import router as validation_router
from .upload import router as upload_router
from .admin_stats import router as admin_stats_router
from .cctv_stream import router as cctv_stream_router
from .language import router as language_router

# รวมทุก router ไว้ในลิสต์เพื่อง่ายต่อการ include ใน main.py
all_routers = [
    health_router,
    auth_router,
    ai_detection_router,
    vegetables_router,
    nutrition_router,
    diseases_pest_router,
    locations_router,
    users_router,
    plots_router,
    cctv_router,
    planting_router,
    detection_router,
    telegram_router,
    dashboard_router,
    admin_database_router,
    contact_router,
    # [NEW] Routes ที่เพิ่มมา
    validation_router,
    upload_router,
    admin_stats_router,
    cctv_stream_router,
    language_router,
]

__all__ = ["all_routers"]
