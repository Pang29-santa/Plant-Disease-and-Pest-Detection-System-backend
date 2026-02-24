"""
Health Check Routes
"""

from datetime import datetime
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


import logging

logger = logging.getLogger(__name__)

@router.get("/")
async def root():
    """หน้าแรกของ API - ไม่ต้อง Login"""
    logger.info("Root endpoint accessed")
    return {
        "message": "Vegetable & Agriculture API",
        "docs": "/docs",
        "version": "1.0.0",
        "auth": "Use /api/auth/login to get token"
    }


@router.get("/health")
async def health_check():
    """ตรวจสอบสถานะระบบ - ไม่ต้อง Login"""
    logger.info("Health check requested")
    return {
        "status": "OK",
        "timestamp": datetime.utcnow(),
        "database": "Connected"
    }
