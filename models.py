from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr, AfterValidator
from typing import Optional, List, Any, Union, Annotated
from datetime import datetime
from bson import ObjectId

# ฟังก์ชันสำหรับตรวจสอบความถูกต้องของ ObjectId
def validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId")
    return ObjectId(v)

# สร้าง Type สำหรับ ObjectId ที่รองรับ Pydantic v2
# ใช้ str แทน ObjectId เพื่อให้ serialize ได้ง่าย
PyObjectId = str

# ============== Auth Models ==============
class LoginRequest(BaseModel):
    """Model สำหรับ Login"""
    fullname: str = Field(..., description="ชื่อผู้ใช้หรือชื่อเต็ม")
    password: str = Field(..., min_length=6, description="รหัสผ่านอย่างน้อย 6 ตัวอักษร")

class LoginResponse(BaseModel):
    """Model สำหรับ Response ตอน Login"""
    success: bool
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None

class TokenRefreshRequest(BaseModel):
    """Model สำหรับ Refresh Token"""
    refresh_token: str

class TokenResponse(BaseModel):
    """Model สำหรับ Response Token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserRegister(BaseModel):
    """Model สำหรับ Register"""
    user_id: Optional[int] = None
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{9,15}$')
    fullname: str = Field(..., min_length=3)
    email: EmailStr
    password: str = Field(..., min_length=6)
    subdistricts_id: Optional[int] = None
    image_path: Optional[str] = None
    role: str = "user"
    status: str = "active"
    telegram_chat_id: Optional[str] = None
    telegram_connection_code: Optional[str] = None
    telegram_code_expires: Optional[datetime] = None
    telegram_connected_at: Optional[datetime] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class ChangePasswordRequest(BaseModel):
    """Model สำหรับเปลี่ยนรหัสผ่าน"""
    old_password: str
    new_password: str

# ============== Vegetable (ผัก) ==============
class VegetableBase(BaseModel):
    vegetable_id: Optional[int] = None
    thai_name: Optional[str] = None
    eng_name: Optional[str] = None
    sci_name: Optional[str] = None
    growth: Optional[int] = None
    planting_method: Optional[str] = None
    care: Optional[str] = None
    details: Optional[str] = None
    image_path: Optional[str] = None  # เก็บไว้เพื่อ backward compatibility
    image_paths: Optional[List[str]] = None  # รองรับหลายรูปภาพ (ไม่เกิน 5 รูป)
    planting_method_en: Optional[str] = None
    care_en: Optional[str] = None
    details_en: Optional[str] = None
    
    @field_validator('image_paths', mode='before')
    def limit_image_paths(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("สามารถอัปโหลดรูปภาพได้สูงสุด 5 รูป")
        return v

class Vegetable(VegetableBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Nutrition (โภชนาการ) ==============
class NutritionBase(BaseModel):
    nutrition_id: Optional[int] = None
    nutrition_name: Optional[str] = None
    nutrition_name_en: Optional[str] = None

class Nutrition(NutritionBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== NutritionVeg (ความสัมพันธ์ผัก-โภชนาการ) ==============
class NutritionVegBase(BaseModel):
    nutrition_id: Optional[int] = None
    nutrient_name: Optional[str] = None  # Added for flexibility
    vegetable_id: Optional[int] = None
    nutrition_qty: Optional[float] = None
    unit: Optional[str] = None

class NutritionVeg(NutritionVegBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Diseases & Pest (โรค/ศัตรูพืช) ==============
class DiseasesPestBase(BaseModel):
    ID: Optional[int] = None
    type: Optional[str] = None  # 1=โรค, 2=ศัตรูพืช
    thai_name: Optional[str] = None
    eng_name: Optional[str] = None
    cause: Optional[str] = None
    description: Optional[str] = None
    prevention: Optional[str] = None
    treatment: Optional[str] = None
    cause_en: Optional[str] = None
    description_en: Optional[str] = None
    prevention_en: Optional[str] = None
    treatment_en: Optional[str] = None
    image_path: Optional[str] = None  # เก็บไว้เพื่อ backward compatibility
    image_paths: Optional[List[str]] = None  # รองรับหลายรูปภาพ (ไม่เกิน 5 รูป)
    
    @field_validator('image_paths', mode='before')
    def limit_image_paths(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("สามารถอัปโหลดรูปภาพได้สูงสุด 5 รูป")
        return v

class DiseasesPest(DiseasesPestBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Province (จังหวัด) ==============
class ProvinceBase(BaseModel):
    id: Optional[int] = None
    name_in_thai: Optional[str] = None
    name_in_english: Optional[str] = None

class Province(ProvinceBase):
    class Config:
        populate_by_name = True

# ============== District (อำเภอ) ==============
class DistrictBase(BaseModel):
    id: Optional[int] = None
    province_id: Optional[int] = None
    name_in_thai: Optional[str] = None
    name_in_english: Optional[str] = None

class District(DistrictBase):
    class Config:
        populate_by_name = True

# ============== Subdistrict (ตำบล) ==============
class SubdistrictBase(BaseModel):
    id: Optional[int] = None
    district_id: Optional[int] = None
    name_in_thai: Optional[str] = None
    name_in_english: Optional[str] = None

class Subdistrict(SubdistrictBase):
    class Config:
        populate_by_name = True

# ============== User (ผู้ใช้) ==============
class UserBase(BaseModel):
    user_id: Optional[int] = None
    phone: Optional[str] = None
    fullname: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    subdistricts_id: Optional[int] = None
    role: Optional[str] = "user"  # user, admin
    image_path: Optional[str] = None
    status: Optional[str] = "active"  # active, inactive, suspended
    telegram_chat_id: Optional[str] = None
    telegram_connection_code: Optional[str] = None
    telegram_code_expires: Optional[datetime] = None
    telegram_connected_at: Optional[datetime] = None

    @field_validator('phone', 'telegram_connection_code', mode='before')
    def coerce_string(cls, v):
        if v is None:
            return None
        return str(v)

class User(UserBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Plot (แปลง) ==============
class PlotBase(BaseModel):
    plot_id: Optional[int] = None
    plot_name: Optional[str] = None
    size: Optional[float] = None
    unit: Optional[str] = None
    user_id: Optional[int] = None
    image_path: Optional[str] = None
    status: Optional[Union[str, int]] = None  # 0=ว่าง, 1=ปลูกแล้ว (รองรับทั้ง int/str)
    is_deleted: Optional[int] = None  # 0=ไม่ลบ, 1=ลบแล้ว

    @field_validator('status', mode='before')
    def coerce_status_to_str(cls, v):
        """DB เก็บ status เป็น int (0,1) → แปลงเป็น str เพื่อให้ consistent"""
        if v is None:
            return None
        return str(v)

class Plot(PlotBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )



# ============== CCTV (กล้องวงจรปิด) ==============
class CCTVBase(BaseModel):
    CCTV_id: Optional[int] = None
    ip_address: Optional[str] = None
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    device_ip: Optional[str] = None
    camera_name: Optional[str] = None
    details: Optional[str] = None
    user_id: Optional[Union[int, str]] = None
    plot_id: Optional[Union[int, str]] = None

class CCTV(CCTVBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== PlantingVeg (การปลูกผัก) ==============
class PlantingVegBase(BaseModel):
    planting_id: Optional[int] = None
    plot_id: Optional[int] = None
    planting_date: Optional[str] = None
    schedule_harvest: Optional[str] = None
    quantity: Optional[int] = None
    vegetable_id: Optional[int] = None
    status: Optional[int] = None  # 0=วางแผน, 1=กำลังปลูก, 2=เก็บเกี่ยวแล้ว
    harvesting_date: Optional[str] = None

class PlantingVeg(PlantingVegBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== HarvestRecord (บันทึกการเก็บเกี่ยว) ==============
class HarvestRecordBase(BaseModel):
    harvest_id: Optional[int] = None
    user_id: Optional[int] = None
    vegetable_id: Optional[int] = None
    planting_id: Optional[int] = None
    plot_id: Optional[int] = None
    quantity: Optional[float] = None
    income: Optional[int] = None
    cost: Optional[int] = None
    harvesting_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

class HarvestRecord(HarvestRecordBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Detection (การตรวจจับ) ==============
class DetectionBase(BaseModel):
    detection_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    plot_id: Optional[int] = None
    disease_pest_id: Optional[Union[int, str]] = None  # Reference to diseases_pest.ID
    vegetable_id: Optional[int] = None
    user_id: Optional[Union[int, str]] = None  # รองรับทั้ง int และ string
    image_path: Optional[str] = None
    confidence: Optional[float] = None  # AI confidence score (optional)
    notes: Optional[str] = None

class Detection(DetectionBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Telegram Connections ==============
class TelegramConnectionBase(BaseModel):
    connection_id: Optional[int] = None
    user_id: Optional[Union[int, str]] = None  # รองรับทั้ง int และ string (ObjectId)
    chat_id: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[Union[str, datetime]] = None  # รองรับทั้ง string และ datetime
    last_activity: Optional[Union[str, datetime]] = None
    connected_at: Optional[Union[str, datetime]] = None
    connection_code: Optional[str] = None

class TelegramConnection(TelegramConnectionBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== OTP ==============
class OTPBase(BaseModel):
    email: Optional[str] = None
    otp_code: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class OTP(OTPBase):
    id: Optional[str] = Field(None, alias="_id")
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# ============== Dashboard & Statistics ==============
class DashboardStats(BaseModel):
    total_users: int
    total_plots: int
    total_vegetables: int
    total_detections: int
    recent_detections: List[dict]
    disease_stats: List[dict]
