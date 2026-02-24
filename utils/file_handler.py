"""
File Handler Utilities
จัดการไฟล์รูปภาพในระบบ
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import UploadFile, HTTPException

# Base image directory
BASE_IMG_DIR = Path("static/images")

# Allowed image extensions
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB



def get_image_dir(image_type: str) -> Path:
    """
    ดึง path ของโฟลเดอร์รูปภาพตามประเภท
    
    Args:
        image_type: ประเภทรูปภาพ (vegetables, diseases, pests, plots, users, detections, cctv, harvests)
    
    Returns:
        Path object
    """
    # Special case for vegetable gallery (static/img/vegetables)
    if image_type == 'vegetable_gallery':
        # ใช้ Path แบบ absolute หรือ relative to root โปรเจกต์
        # ถ้าต้องการ D:\pang\project\backend_fastapi\static\img\vegetables
        # ให้ใช้ Path("static/img/vegetables") เพราะ BASE_IMG_DIR = static/images
        return Path("static/img/vegetables")
        
    type_mapping = {
        'vegetable': 'vegetables',
        'vegetables': 'vegetables',
        'disease': 'diseases',
        'diseases': 'diseases',
        'pest': 'pests',
        'pests': 'pests',
        'diseases_pest': 'diseases_pests',
        'plot': 'plots',
        'plots': 'plots',
        'user': 'users',
        'users': 'users',
        'detection': 'detections',
        'detections': 'detections',
        'cctv': 'cctv',
        'harvest': 'harvests',
        'harvests': 'harvests',
        'upload': 'uploads',
        'uploads': 'uploads',
        'temp': 'temp',
    }
    
    folder_name = type_mapping.get(image_type.lower(), 'uploads')
    return BASE_IMG_DIR / folder_name


def validate_image_file(file: UploadFile) -> bool:
    """
    ตรวจสอบไฟล์รูปภาพ
    
    Args:
        file: UploadFile object
    
    Returns:
        True if valid, raises HTTPException if invalid
    """
    # Check extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check content type
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="File must be an image"
        )
    
    return True



def generate_filename(
    entity_type: str,
    entity_id: str,
    original_filename: str,
    index: Optional[int] = None
) -> str:
    """
    สร้างชื่อไฟล์ใหม่ตาม convention
    
    Args:
        entity_type: ประเภท (vegetable, disease, pest, plot, user, detection, cctv)
        entity_id: ID ของ entity
        original_filename: ชื่อไฟล์เดิม
        index: ลำดับของรูปภาพ (สำหรับการตั้งชื่อแบบ ID_index)
    
    Returns:
        ชื่อไฟล์ใหม่
    """
    ext = Path(original_filename).suffix.lower()
    
    # กรณีระบุ index ให้ใช้รูปแบบ ID_index.ext
    if index is not None:
        return f"{entity_id}_{index}{ext}"
    
    # กรณีเดิม (Fallback)
    timestamp = int(datetime.now().timestamp())
    
    prefix_mapping = {
        'vegetable': 'veg',
        'disease': 'disease',
        'pest': 'pest',
        'plot': 'plot',
        'user': 'user',
        'detection': 'detection',
        'cctv': 'cctv',
        'harvest': 'harvest',
    }
    
    prefix = prefix_mapping.get(entity_type.lower(), 'img')
    # เพิ่ม random suffix กันซ้ำกรณี timestamp ชนกัน (fallback)
    import random
    rand = random.randint(100, 999)
    return f"{prefix}_{entity_id}_{timestamp}_{rand}{ext}"



async def save_image(
    file: UploadFile,
    image_type: str,
    entity_id: str,
    filename: Optional[str] = None,
    index: Optional[int] = None
) -> str:
    """
    บันทึกไฟล์รูปภาพ
    
    Args:
        file: UploadFile object
        image_type: ประเภทรูปภาพ
        entity_id: ID ของ entity
        filename: ชื่อไฟล์ที่ต้องการ (optional)
        index: ลำดับของรูปภาพ (optional, passed to generate_filename)
        
    Returns:
        path ของไฟล์ที่บันทึก (relative to root)
    """
    # Validate file
    validate_image_file(file)
    
    # Get directory
    img_dir = get_image_dir(image_type)
    img_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        filename = generate_filename(image_type, entity_id, file.filename, index=index)
    
    # Save file
    file_path = img_dir / filename
    
    try:
        contents = await file.read()
        
        # Check file size
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {MAX_FILE_SIZE / (1024*1024)} MB"
            )
        
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # Return path relative to root
        # Check if img_dir starts with "static/" to return cleaner path
        path_str = str(file_path).replace("\\", "/")
        if path_str.startswith("static/"):
            return path_str
        return f"static/{path_str}" if not path_str.startswith("static") else path_str
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")



def delete_image(image_path: str) -> bool:
    """
    ลบไฟล์รูปภาพ
    
    Args:
        image_path: path ของรูปภาพ (relative to static/)
    
    Returns:
        True if deleted, False if not found
    """
    try:
        # รองรับหลายรูปแบบ path
        possible_paths = []
        
        # แบบที่ 1: path เริ่มต้นด้วย img/ -> static/img/...
        if image_path.startswith('img/'):
            possible_paths.append(BASE_IMG_DIR / image_path.replace('img/', ''))
        
        # แบบที่ 2: path เริ่มต้นด้วย static/images/ -> static/images/...
        elif image_path.startswith('static/images/'):
            possible_paths.append(Path("static/images") / image_path.replace('static/images/', ''))
        
        # แบบที่ 3: path เริ่มต้นด้วย static/img/ -> static/img/...
        elif image_path.startswith('static/img/'):
            possible_paths.append(Path("static/img") / image_path.replace('static/img/', ''))
        
        # แบบที่ 4: path ไม่มี prefix -> ลองหาใน img/ และ images/
        else:
            possible_paths.append(BASE_IMG_DIR / image_path)
            possible_paths.append(Path("static/images") / image_path)
        
        # ลบไฟล์จากทุก path ที่เป็นไปได้ (จริงๆ จะมีอยู่ที่เดียว)
        deleted = False
        for full_path in possible_paths:
            if full_path.exists():
                full_path.unlink()
                deleted = True
                break
        
        return deleted
    except Exception:
        return False


def get_image_url(image_path: str) -> str:
    """
    ดึง URL ของรูปภาพ
    
    Args:
        image_path: path ของรูปภาพ
    
    Returns:
        URL สำหรับเข้าถึงรูปภาพ
    """
    if not image_path:
        return ""
    
    # If already starts with /static/, return as is
    if image_path.startswith('/static/'):
        return image_path
    
    # If starts with static/ (without leading slash), add leading slash
    if image_path.startswith('static/'):
        return f"/{image_path}"
    
    # Add /static/ prefix
    return f"/static/{image_path}"


def move_temp_image(temp_filename: str, target_type: str, entity_id: str) -> str:
    """
    ย้ายไฟล์จาก temp ไปยังโฟลเดอร์ปลายทาง
    
    Args:
        temp_filename: ชื่อไฟล์ในโฟลเดอร์ temp
        target_type: ประเภทปลายทาง
        entity_id: ID ของ entity
    
    Returns:
        path ใหม่
    """
    temp_dir = get_image_dir('temp')
    target_dir = get_image_dir(target_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    temp_path = temp_dir / temp_filename
    
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="Temp file not found")
    
    # Generate new filename
    ext = Path(temp_filename).suffix
    timestamp = int(datetime.now().timestamp())
    new_filename = f"{target_type}_{entity_id}_{timestamp}{ext}"
    
    target_path = target_dir / new_filename
    
    try:
        shutil.move(str(temp_path), str(target_path))
        return f"img/{target_type.lower()}s/{new_filename}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move image: {str(e)}")


def cleanup_old_images(days: int = 7):
    """
    ลบไฟล์เก่าในโฟลเดอร์ temp และ uploads
    
    Args:
        days: จำนวนวันที่เก็บไว้
    """
    from datetime import timedelta
    
    cutoff_time = datetime.now() - timedelta(days=days)
    
    for folder_name in ['temp', 'uploads']:
        folder = get_image_dir(folder_name)
        if not folder.exists():
            continue
        
        for file_path in folder.iterdir():
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                    except Exception:
                        pass


# ============== Multiple Images Handler ==============

MAX_IMAGES_PER_ENTITY = 5  # จำกัดจำนวนรูปภาพสูงสุดต่อ entity


async def save_multiple_images(
    files: List[UploadFile],
    image_type: str,
    entity_id: str,
    existing_paths: List[str] = None,
    start_index: int = 1
) -> List[str]:
    """
    บันทึกหลายไฟล์รูปภาพ (สูงสุด 5 รูป)
    
    Args:
        files: List ของ UploadFile
        image_type: ประเภทรูปภาพ (vegetables, diseases, pests, etc.)
        entity_id: ID ของ entity
        existing_paths: List ของ path รูปภาพที่มีอยู่แล้ว (สำหรับ update)
        start_index: ลำดับเริ่มต้นสำหรับการตั้งชื่อไฟล์ (Default: 1)
    
    Returns:
        List ของ path รูปภาพที่บันทึก (รวมกับ existing_paths ถ้ามี)
    """
    if existing_paths is None:
        existing_paths = []
    
    # ตรวจสอบจำนวนรูปภาพรวม
    total_count = len(existing_paths) + len(files)
    if total_count > MAX_IMAGES_PER_ENTITY:
        raise HTTPException(
            status_code=400,
            detail=f"จำนวนรูปภาพรวมต้องไม่เกิน {MAX_IMAGES_PER_ENTITY} รูป (มีอยู่ {len(existing_paths)} รูป, กำลังเพิ่ม {len(files)} รูป)"
        )
    
    if not files:
        return existing_paths
    
    saved_paths = existing_paths.copy()
    current_index = start_index
    
    for file in files:
        if file is None:
            continue
            
        try:
            # ใช้ index ในการตั้งชื่อไฟล์
            path = await save_image(file, image_type, entity_id, index=current_index)
            saved_paths.append(path)
            current_index += 1
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save image {file.filename}: {str(e)}")
    
    return saved_paths


def delete_multiple_images(image_paths: List[str]) -> Dict[str, bool]:
    """
    ลบหลายไฟล์รูปภาพ
    
    Args:
        image_paths: List ของ path รูปภาพที่ต้องการลบ
    
    Returns:
        Dict ที่มี key เป็น path และ value เป็น boolean (True=ลบสำเร็จ, False=ไม่พบไฟล์)
    """
    results = {}
    for path in image_paths:
        results[path] = delete_image(path)
    return results


def validate_multiple_images(files: List[UploadFile]) -> bool:
    """
    ตรวจสอบไฟล์รูปภาพหลายไฟล์
    
    Args:
        files: List ของ UploadFile
    
    Returns:
        True if all valid, raises HTTPException if invalid
    """
    if len(files) > MAX_IMAGES_PER_ENTITY:
        raise HTTPException(
            status_code=400,
            detail=f"สามารถอัปโหลดได้สูงสุด {MAX_IMAGES_PER_ENTITY} รูปภาพ"
        )
    
    for file in files:
        if file and file.filename:
            validate_image_file(file)
    
    return True
