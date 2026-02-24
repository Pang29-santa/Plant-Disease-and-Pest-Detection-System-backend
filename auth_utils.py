"""
Authentication Utilities
JWT Token และ Password Hashing
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
# Monkeypatch bcrypt to fix passlib 1.7.4 compatibility with bcrypt >= 4.0.0
# passlib relies on bcrypt.__about__ which was removed in bcrypt 4.0.0
try:
    if not hasattr(bcrypt, '__about__'):
        class About:
            __version__ = bcrypt.__version__
        bcrypt.__about__ = About()
except Exception:
    pass

from passlib.context import CryptContext
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()

# ============================================
# JWT Configuration (จาก .env)
# ============================================
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY ต้องถูกตั้งค่าใน .env ไฟล์")

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ============================================
# Password Hashing
# ============================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer security
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """ตรวจสอบรหัสผ่าน"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """เข้ารหัสรหัสผ่านด้วย bcrypt"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """สร้าง JWT Access Token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """สร้าง JWT Refresh Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """ถอดรหัส JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None



async def get_current_user(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(security_optional)
) -> Dict[str, Any]:
    """
    Dependency สำหรับตรวจสอบ JWT Token และคืนค่าข้อมูลผู้ใช้
    ถ้ามี token จริง ใช้ข้อมูลจาก token
    ถ้าไม่มี token ใช้ bypass user (ปลดล็อก API)
    """
    # ถ้ามี token จริงๆ ให้ใช้ข้อมูลจาก token
    if token and token.credentials:
        try:
            payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                # สร้าง dict ข้อมูล user จาก payload
                return {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "fullname": payload.get("fullname"),
                    "role": payload.get("role", "user"),
                }
        except JWTError:
            pass  # Token ไม่ valid ให้ fallback ไป bypass
    
    # ไม่มี token หรือ token ไม่ valid - ใช้ bypass user (ปลดล็อก API)
    return {
        "user_id": "bypass_user",
        "email": "bypass@example.com",
        "fullname": "Bypass User",
        "role": "admin",
    }


async def get_current_user_optional(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(security_optional)
) -> Optional[Dict[str, Any]]:
    """
    Dependency สำหรับตรวจสอบ JWT Token (optional)
    ถ้ามี token จริง ใช้ข้อมูลจาก token
    ถ้าไม่มี token แต่เปิด BYPASS_AUTH ให้ใช้ bypass user
    ถ้าไม่มี token และไม่เปิด BYPASS_AUTH return None
    """
    # โหลดค่า BYPASS_AUTH
    bypass_auth = os.getenv("BYPASS_AUTH", "false").lower() == "true"
    
    if token and token.credentials:
        try:
            payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                return {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "fullname": payload.get("fullname"),
                    "role": payload.get("role", "user"),
                }
        except JWTError:
            pass
    
    # ถ้าเปิด BYPASS_AUTH ให้ return bypass user
    if bypass_auth:
        return {
            "user_id": "bypass_user",
            "email": "bypass@example.com",
            "fullname": "Bypass User",
            "role": "admin",
        }
    
    return None


async def get_current_admin(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(security_optional)
) -> Dict[str, Any]:
    """
    Dependency สำหรับตรวจสอบว่าเป็น Admin
    ถ้ามี token จริง ใช้ข้อมูลจาก token
    ถ้าไม่มี token ใช้ bypass admin (ปลดล็อก API)
    """
    # ถ้ามี token จริงๆ ให้ใช้ข้อมูลจาก token
    if token and token.credentials:
        try:
            payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                user_data = {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "fullname": payload.get("fullname"),
                    "role": payload.get("role", "user"),
                }
                # ถ้าเป็น admin จริงๆ ให้ return ข้อมูลจริง
                if user_data.get("role") == "admin":
                    return user_data
        except JWTError:
            pass
    
    # ไม่มี token หรือไม่ใช่ admin - ใช้ bypass admin (ปลดล็อก API)
    return {
        "user_id": "bypass_admin",
        "email": "admin@example.com",
        "fullname": "Bypass Admin",
        "role": "admin",
    }


async def verify_token_optional(
    request: Request,
    token: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)
) -> Optional[Dict[str, Any]]:
    """
    Dependency สำหรับตรวจสอบ token แบบไม่บังคับ
    ถ้ามี token จริง ใช้ข้อมูลจาก token
    ถ้าไม่มี token ใช้ bypass user (ปลดล็อก API)
    """
    # ถ้ามี token จริงๆ ให้ใช้ข้อมูลจาก token
    if token and token.credentials:
        try:
            payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                return {
                    "user_id": user_id,
                    "email": payload.get("email"),
                    "fullname": payload.get("fullname"),
                    "role": payload.get("role", "user"),
                }
        except JWTError:
            pass
    
    # ไม่มี token - ใช้ bypass user (ปลดล็อก API)
    return {
        "user_id": "bypass_user",
        "email": "bypass@example.com",
        "fullname": "Bypass User",
        "role": "admin",
    }
