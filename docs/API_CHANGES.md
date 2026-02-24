# API Changes Report
## รายงานการเพิ่ม API จากต้นฉบับ

**วันที่**: 2026-02-23  
**ต้นฉบับ**: `C:\Users\ADMINS\Downloads\main.py` (5,294 บรรทัด)  
**โปรเจกต์ปัจจุบัน**: `D:\pang\project\backend_fastapi`

---

## สรุป

แยก API ที่ขาดไปจากต้นฉบับเป็น **5 ไฟล์ route แยกตามหมวดหมู่**:

| ไฟล์ | จำนวน Endpoints | หมวดหมู่ |
|------|----------------|----------|
| `routes/validation.py` | 2 | ตรวจสอบข้อมูลซ้ำ |
| `routes/upload.py` | 1 | อัปโหลดไฟล์ |
| `routes/admin_stats.py` | 3 | สถิติสำหรับ Admin |
| `routes/cctv_stream.py` | 2 | สตรีมและสถานะกล้อง |
| `routes/language.py` | 1 | ตั้งค่าภาษา |
| **รวม** | **9** | |

---

## โครงสร้างไฟล์ที่เพิ่ม

```
routes/
├── __init__.py              # [UPDATED] เพิ่ม import ไฟล์ใหม่
├── validation.py            # [NEW] ตรวจสอบชื่อซ้ำ
├── upload.py                # [NEW] อัปโหลดรูปภาพ CKEditor
├── admin_stats.py           # [NEW] สถิติ Admin
├── cctv_stream.py           # [NEW] สตรีมกล้องวงจรปิด
└── language.py              # [NEW] ตั้งค่าภาษา
```

---

## 1. Validation Routes (`routes/validation.py`)

### 1.1 GET /api/check-vegetable-name
ตรวจสอบว่าชื่อผัก (ภาษาไทย) มีอยู่ในระบบแล้วหรือไม่

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| thai_name | string | ✅ | ชื่อผักภาษาไทย |

**Response:**
```json
{
  "exists": true,
  "thai_name": "ผักบุ้ง",
  "message": "ชื่อผักนี้มีอยู่ในระบบแล้ว"
}
```

### 1.2 GET /api/check-diseasepest-name
ตรวจสอบว่าชื่อโรคหรือศัตรูพืชมีอยู่ในระบบแล้วหรือไม่

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| thai_name | string | ✅ | ชื่อโรค/ศัตรูพืช |
| type | string | ❌ | '1'=โรค, '2'=ศัตรูพืช |

**Response:**
```json
{
  "exists": false,
  "thai_name": "โรคใบจุด",
  "type": "1",
  "type_name": "โรคพืช",
  "message": "ชื่อโรคพืชนี้สามารถใช้ได้"
}
```

---

## 2. Upload Routes (`routes/upload.py`)

### 2.1 POST /api/upload-image
อัปโหลดรูปภาพสำหรับ CKEditor (Rich Text Editor)

**Features:**
- รองรับไฟล์: JPG, JPEG, PNG, GIF, BMP, WebP
- ขนาดสูงสุด: 5MB
- ปรับขนาดรูปภาพอัตโนมัติ (max 450x450)
- บันทึกใน `static/images/ckeditor/`

**Request:**
```
Content-Type: multipart/form-data
Body: upload=<file>
```

**Response:**
```json
{
  "url": "/static/images/ckeditor/abc123.jpg",
  "uploaded": true,
  "filename": "abc123.jpg"
}
```

---

## 3. Admin Stats Routes (`routes/admin_stats.py`)

### 3.1 GET /api/admin/top-daily-detections
สถิติ 3 อันดับแรกที่ตรวจพบมากที่สุดประจำวัน แยกตามโรคและแมลง

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| date | string | ❌ | วันที่ YYYY-MM-DD (default: วันนี้) |

**Response:**
```json
{
  "date": "2026-02-23",
  "top_diseases": [
    {"id": 1, "name": "โรคใบจุด", "count": 15},
    {"id": 2, "name": "โรคราน้ำค้าง", "count": 8},
    {"id": 3, "name": "โรคเหี่ยว", "count": 5}
  ],
  "top_pests": [
    {"id": 10, "name": "หนอนใยผัก", "count": 12},
    {"id": 11, "name": "เพลี้ย", "count": 7},
    {"id": 12, "name": "แมลงวัน", "count": 3}
  ]
}
```

### 3.2 GET /api/admin/detection-stats
สถิติการตรวจพบสำหรับ Admin (รองรับกราฟ)

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| year | int | ✅ | ปี (รองรับทั้ง พ.ศ. และ ค.ศ.) |
| month | int | ❌ | เดือน 1-12 (optional) |
| disease_type | string | ❌ | '1'=โรค, '2'=ศัตรูพืช |

**Response:**
```json
{
  "total_detections": 150,
  "top_items": [
    {"name": "โรคใบจุด", "count": 45},
    {"name": "หนอนใยผัก", "count": 30}
  ],
  "chart_data": {
    "title": "สถิติรายเดือน ปี 2568",
    "labels": ["ม.ค.", "ก.พ.", "มี.ค.", ...],
    "datasets": [
      {"label": "โรคพืช", "data": [10, 15, 8, ...]},
      {"label": "แมลงศัตรูพืช", "data": [5, 8, 12, ...]}
    ]
  }
}
```

### 3.3 GET /api/admin/available-months
ดึงข้อมูลเดือนที่มีการตรวจพบข้อมูล สำหรับปีที่ระบุ

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| year | int | ✅ | ปี (รองรับทั้ง พ.ศ. และ ค.ศ.) |

**Response:**
```json
[
  {"value": 1, "name": "มกราคม"},
  {"value": 3, "name": "มีนาคม"},
  {"value": 5, "name": "พฤษภาคม"}
]
```

---

## 4. CCTV Stream Routes (`routes/cctv_stream.py`)

### 4.1 GET /api/cctv/status/{cctv_id}
ตรวจสอบสถานะกล้อง CCTV (online/offline)

**Features:**
- รองรับ RTSP (port 554)
- รองรับ HTTP/HTTPS
- รองรับ TCP probe
- Timeout 1 วินาที

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| cctv_id | string | ✅ | MongoDB ObjectId |

**Response:**
```json
{
  "status": "online",
  "protocol": "rtsp"
}
```

### 4.2 GET /api/cctv/stream/{cctv_id}
สตรีมวิดีโอจากกล้องแบบ MJPEG (Server-Sent Events)

**Features:**
- Real-time streaming
- Auto reconnect (ทุก 5 วินาที)
- Error frame display
- Support FFmpeg backend

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| cctv_id | string | ✅ | MongoDB ObjectId |

**Response:**
```
Content-Type: multipart/x-mixed-replace; boundary=frame

--frame
Content-Type: image/jpeg
<binary data>
--frame
...
```

---

## 5. Language Routes (`routes/language.py`)

### 5.1 POST /set-lang/{lang}
ตั้งค่าภาษาสำหรับระบบ (i18n)

**Parameters:**
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|----------|
| lang | string | ✅ | "th" หรือ "en" |

**Response:**
```json
{
  "ok": true,
  "lang": "th"
}
```

**Cookie:**
- ตั้งค่า cookie `lang` อายุ 1 ปี

---

## การอัปเดต routes/__init__.py

```python
# [NEW] Routes ที่เพิ่มมาจากต้นฉบับ
from .validation import router as validation_router
from .upload import router as upload_router
from .admin_stats import router as admin_stats_router
from .cctv_stream import router as cctv_stream_router
from .language import router as language_router

all_routers = [
    ...
    contact_router,
    # [NEW] Routes ที่เพิ่มมา
    validation_router,
    upload_router,
    admin_stats_router,
    cctv_stream_router,
    language_router,
]
```

---

## รายชื่อไฟล์ทั้งหมดที่มีการเปลี่ยนแปลง

### ไฟล์ที่สร้างใหม่ (5 ไฟล์)
1. `routes/validation.py` - Validation APIs
2. `routes/upload.py` - Upload APIs
3. `routes/admin_stats.py` - Admin Stats APIs
4. `routes/cctv_stream.py` - CCTV Stream APIs
5. `routes/language.py` - Language API

### ไฟล์ที่อัปเดต (1 ไฟล์)
1. `routes/__init__.py` - เพิ่ม import และรวม router ใหม่

### ไฟล์ที่ลบ (1 ไฟล์)
- ~~`routes/missing_apis.py`~~ (ถูกแทนที่ด้วยไฟล์แยก)

---

## ทดสอบ API

### ตัวอย่าง cURL

```bash
# Validation APIs
curl "http://localhost:8888/api/check-vegetable-name?thai_name=ผักบุ้ง"
curl "http://localhost:8888/api/check-diseasepest-name?thai_name=โรคใบจุด&type=1"

# Upload API
curl -X POST "http://localhost:8888/api/upload-image" \
  -F "upload=@/path/to/image.jpg"

# Admin Stats APIs
curl "http://localhost:8888/api/admin/top-daily-detections?date=2026-02-23"
curl "http://localhost:8888/api/admin/detection-stats?year=2026&month=2"
curl "http://localhost:8888/api/admin/available-months?year=2026"

# CCTV APIs
curl "http://localhost:8888/api/cctv/status/{cctv_id}"
curl "http://localhost:8888/api/cctv/stream/{cctv_id}"

# Language API
curl -X POST "http://localhost:8888/set-lang/th"
```

---

## Dependencies

ไฟล์ใหม่ใช้ dependencies ที่มีอยู่แล้วในโปรเจกต์:
- `fastapi` - Framework หลัก
- `bson` - สำหรับ MongoDB ObjectId
- `Pillow` - สำหรับ resize รูปภาพ (optional)
- `opencv-python` - สำหรับ CCTV streaming
- `numpy` - สำหรับสร้าง error frames

---

## หมายเหตุ

1. **แยกไฟล์ตามหมวดหมู่** - แต่ละไฟล์มีหน้าที่ชัดเจน ไม่ซับซ้อน
2. **ไม่แก้ไขไฟล์เดิม** - ยกเว้น `__init__.py` ที่ต้องเพิ่ม import
3. **Backward Compatible** - API ทั้งหมดออกแบบให้เข้ากันได้กับโค้ดเดิม
4. **MongoDB Async** - ใช้ Motor async driver เหมือนกับโปรเจกต์ปัจจุบัน
5. **Error Handling** - มี try-except ครอบทุก endpoint
