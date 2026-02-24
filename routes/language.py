"""
Language Routes
===============
API สำหรับจัดการภาษา (i18n)

APIs:
- POST /set-lang/{lang} - ตั้งค่าภาษา (th/en)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Language"])


@router.post("/set-lang/{lang}")
async def set_language(lang: str):
    """
    ตั้งค่าภาษาสำหรับระบบ
    
    Args:
        lang: "th" หรือ "en"
        
    Returns:
        success: true/false
        lang: ภาษาที่ตั้งค่า
    """
    if lang not in ("th", "en"):
        raise HTTPException(status_code=400, detail="invalid lang (use 'th' or 'en')")
    
    resp = JSONResponse({"ok": True, "lang": lang})
    resp.set_cookie("lang", lang, path="/", max_age=60*60*24*365)  # 1 year
    return resp
