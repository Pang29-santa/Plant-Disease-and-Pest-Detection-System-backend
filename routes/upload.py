"""
Upload Routes
=============
API สำหรับอัปโหลดไฟล์ (รูปภาพ, เอกสาร)

APIs:
- POST /api/upload-image - อัปโหลดรูปภาพสำหรับ CKEditor
"""

import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(tags=["Upload"])


@router.post("/api/upload-image")
async def upload_image_for_ckeditor(
    upload: UploadFile = File(...)
):
    """
    อัปโหลดรูปภาพสำหรับ CKEditor (Rich Text Editor)
    
    - รองรับไฟล์: JPG, JPEG, PNG, GIF, BMP, WebP
    - ขนาดสูงสุด: 5MB
    - ปรับขนาดรูปภาพอัตโนมัติ (resize เป็น max 450x450)
    
    Returns:
        url: URL ของรูปภาพที่อัปโหลด
        uploaded: true ถ้าอัปโหลดสำเร็จ
    """
    try:
        # ตรวจสอบประเภทไฟล์
        allowed_types = [
            "image/jpeg", "image/png", "image/gif", 
            "image/bmp", "image/webp", "image/jpg"
        ]
        
        if upload.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"ประเภทไฟล์ไม่ถูกต้อง (รองรับ: JPG, PNG, GIF, BMP, WebP)"
            )
        
        # ตรวจสอบขนาดไฟล์ (max 5MB)
        contents = await upload.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail="ไฟล์มีขนาดใหญ่เกินไป (สูงสุด 5MB)"
            )
        
        # สร้างโฟลเดอร์สำหรับเก็บรูป
        upload_dir = Path("static/images/ckeditor")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # สร้างชื่อไฟล์ใหม่
        file_extension = upload.filename.split(".")[-1].lower()
        if file_extension not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
            file_extension = 'jpg'
        
        new_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = upload_dir / new_filename
        
        # บันทึกไฟล์
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        # ลองปรับขนาดรูปภาพ (ถ้ามี Pillow)
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                # Resize ถ้ารูปใหญ่เกิน 450x450
                img.thumbnail((450, 450))
                img.save(file_path, quality=85, optimize=True)
        except Exception as e:
            # ถ้าไม่สามารถ resize ได้ ให้ใช้รูปเดิม
            print(f"[WARN] Could not resize image: {e}")
        
        # สร้าง URL
        image_url = f"/static/images/ckeditor/{new_filename}"
        
        return {
            "url": image_url,
            "uploaded": True,
            "filename": new_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}")
