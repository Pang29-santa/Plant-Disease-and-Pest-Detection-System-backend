"""
Contact Form API - ส่งอีเมลติดต่อไปหา Admin ผ่าน Gmail API (OAuth)
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contact", tags=["Contact"])


class ContactForm(BaseModel):
    """โมเดลสำหรับฟอร์มติดต่อ"""
    name: str
    email: EmailStr
    subject: str
    message: str
    phone: Optional[str] = None


class ContactResponse(BaseModel):
    """โมเดลสำหรับ response"""
    success: bool
    message: str


@router.post("/send", response_model=ContactResponse)
async def send_contact_email(form: ContactForm, request: Request, background_tasks: BackgroundTasks):
    """
    ส่งอีเมลติดต่อไปหา admin ผ่าน Gmail API (Background Task)
    """
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "651413010@crru.ac.th")
        client_ip = request.client.host if request.client else 'Unknown'
        
        # สร้างเนื้อหาอีเมล
        phone_section = ""
        if form.phone:
            phone_section = f'<div class="field"><span class="field-label">เบอร์โทร:</span><div class="field-value">{form.phone}</div></div>'
        
        email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .field {{ margin-bottom: 20px; }}
        .field-label {{ font-weight: bold; color: #667eea; display: block; margin-bottom: 5px; }}
        .field-value {{ background: white; padding: 12px; border-radius: 5px; border-left: 4px solid #667eea; }}
        .message-box {{ background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #764ba2; }}
        .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>มีข้อความติดต่อใหม่</h1>
            <p>Vegetable & Agriculture System</p>
        </div>
        <div class="content">
            <div class="field">
                <span class="field-label">ชื่อผู้ติดต่อ:</span>
                <div class="field-value">{form.name}</div>
            </div>
            <div class="field">
                <span class="field-label">อีเมลผู้ส่ง:</span>
                <div class="field-value">{form.email}</div>
            </div>
            {phone_section}
            <div class="field">
                <span class="field-label">หัวข้อ:</span>
                <div class="field-value">{form.subject}</div>
            </div>
            <div class="field">
                <span class="field-label">ข้อความ:</span>
                <div class="message-box">{form.message}</div>
            </div>
        </div>
        <div class="footer">
            <p>ส่งมาจาก IP: {client_ip}</p>
            <p>&copy; Vegetable & Agriculture System</p>
        </div>
    </div>
</body>
</html>"""
        
        email_text = f"""มีข้อความติดต่อใหม่

ชื่อ: {form.name}
อีเมล: {form.email}
{f"เบอร์โทร: {form.phone}" if form.phone else ""}
หัวข้อ: {form.subject}

ข้อความ:
{form.message}

---
IP: {client_ip}
"""
        
        # ใช้ BackgroundTasks เพื่อส่งอีเมล
        background_tasks.add_task(
            EmailService.send_email,
            to_email=admin_email,
            subject=f"[ระบบตรวจจับโรคและศัตรูพืชในผัก] {form.subject}",
            html_content=email_html,
            text_content=email_text,
            reply_to=form.email,
            sender_name=f"{form.name} (ติดต่อผู้ดูแลระบบ)",
            sender_email=admin_email
        )
        
        logger.info(f"Queued email from {form.email} to {admin_email}")
        
        return ContactResponse(
            success=True,
            message="ส่งข้อความสำเร็จ เราจะติดต่อกลับโดยเร็วที่สุด"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to queue email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการส่งข้อความ: {str(e)}")


@router.get("/health")
async def check_email_health():
    """ตรวจสอบสถานะ Gmail API"""
    try:
        # ทดสอบสร้าง service
        service = EmailService.get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        
        return {
            "status": "ok",
            "message": "Gmail API ready",
            "configured": True,
            "email": profile.get("emailAddress", "unknown")
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "configured": False
        }
