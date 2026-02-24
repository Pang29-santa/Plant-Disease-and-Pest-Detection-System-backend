"""
CCTV Stream Routes
==================
API สำหรับสตรีมวิดีโอและตรวจสอบสถานะกล้อง CCTV

APIs:
- GET /api/cctv/stream/{cctv_id} - สตรีมวิดีโอแบบ MJPEG
- GET /api/cctv/status/{cctv_id} - ตรวจสอบสถานะกล้อง
"""

import os
import socket
import json
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from bson import ObjectId
import asyncio

from database import get_collection

router = APIRouter(tags=["CCTV Stream"])


def _probe_tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    """ตรวจสอบการเชื่อมต่อ TCP"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _http_head(url: str, timeout: float = 1.0) -> bool:
    """ตรวจสอบ HTTP HEAD request"""
    try:
        import requests
        r = requests.head(url, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


@router.get("/api/cctv/status/{cctv_id}")
async def get_camera_status(cctv_id: str):
    """
    ตรวจสอบสถานะกล้อง CCTV (online/offline)
    
    Args:
        cctv_id: ID ของกล้อง (MongoDB ObjectId)
        
    Returns:
        status: "online" หรือ "offline"
    """
    collection = get_collection("cctv")
    
    if not ObjectId.is_valid(cctv_id):
        raise HTTPException(status_code=400, detail="Invalid CCTV ID format")
    
    cctv = await collection.find_one({"_id": ObjectId(cctv_id)})
    if not cctv:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    
    ip = (cctv.get("ip_address") or "").strip()
    if not ip:
        return {"status": "offline", "reason": "no_ip_configured"}
    
    low = ip.lower()
    
    # RTSP
    if low.startswith("rtsp://"):
        u = urlparse(ip)
        host = u.hostname or ""
        port = u.port or 554
        ok = _probe_tcp(host, port, timeout=1.0)
        return {"status": "online" if ok else "offline", "protocol": "rtsp"}
    
    # HTTP/HTTPS
    if low.startswith(("http://", "https://")):
        ok = _http_head(ip, timeout=1.0)
        return {"status": "online" if ok else "offline", "protocol": "http"}
    
    # host:port
    if ":" in ip:
        host, port = ip.split(":", 1)
        try:
            port = int(port)
        except:
            port = 80
        ok = _probe_tcp(host, port, timeout=1.0)
        return {"status": "online" if ok else "offline", "protocol": "tcp"}
    
    # host only
    ok = _probe_tcp(ip, 80, timeout=1.0)
    return {"status": "online" if ok else "offline", "protocol": "tcp"}


@router.get("/api/cctv/stream/{cctv_id}")
async def get_camera_stream(cctv_id: str):
    """
    สตรีมวิดีโอจากกล้อง CCTV แบบ MJPEG
    
    Args:
        cctv_id: ID ของกล้อง (MongoDB ObjectId)
        
    Returns:
        MJPEG Stream
    """
    collection = get_collection("cctv")
    
    if not ObjectId.is_valid(cctv_id):
        raise HTTPException(status_code=400, detail="Invalid CCTV ID format")
    
    cctv = await collection.find_one({"_id": ObjectId(cctv_id)})
    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")
    
    # ดึงข้อมูลการเชื่อมต่อ
    ip_address = cctv.get("ip_address", "")
    details = cctv.get("details", {})
    
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except:
            details = {}
    
    username = details.get("username", "")
    password = details.get("password", "")
    
    # สร้าง URL สำหรับเชื่อมต่อ (Logic อ้างอิงจากโค้ดเดิม)
    def _inject_auth(url: str, username: str, password: str) -> str:
        if not username: return url
        parsed = urlparse(url)
        auth = f"{username}:{password}@" if password else f"{username}@"
        netloc = f"{auth}{parsed.hostname}"
        if parsed.port: netloc += f":{parsed.port}"
        from urllib.parse import urlunparse
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    src = (ip_address or "").strip()
    low = src.lower()
    
    if low.startswith("rtsp://"):
        parsed = urlparse(src)
        camera_url = _inject_auth(src, username, password) if username and not parsed.username else src
    elif low.startswith(("http://", "https://")):
        parsed = urlparse(src)
        camera_url = _inject_auth(src, username, password) if username and not parsed.username else src
    else:
        # กรณีระบุแค่ host[:port]
        auth = f"{username}:{password}@" if username else ""
        camera_url = f"http://{auth}{src}/video"

    
    async def stream_generator():
        """สร้าง MJPEG stream"""
        import cv2
        
        # ตั้งค่า OpenCV
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        
        cap = None
        reconnect_delay = 5.0
        frame_delay = 0.033  # ~30 fps
        
        while True:
            try:
                cap = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)
                
                if not cap.isOpened():
                    # ส่งเฟรม error
                    error_frame = create_error_frame("Connecting to camera...")
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
                    await asyncio.sleep(reconnect_delay)
                    continue
                
                while True:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    
                    # เข้ารหัส JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if not ret:
                        continue
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    
                    await asyncio.sleep(frame_delay)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Stream error: {e}")
                error_frame = create_error_frame(f"Connection Lost\nReconnecting...")
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
                await asyncio.sleep(reconnect_delay)
            finally:
                if cap:
                    cap.release()
    
    return StreamingResponse(
        stream_generator(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )


def create_error_frame(text: str):
    """สร้างเฟรมภาพสำหรับแสดงข้อความ error"""
    import cv2
    import numpy as np
    
    frame = np.zeros((480, 640, 3), dtype="uint8")
    lines = text.split('\n')
    y_pos = 230
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (50, y_pos + i * 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    ret, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()
