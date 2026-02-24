# 🌱 Vegetable Project — Backend Architecture & Flow

> **Stack:** Python · FastAPI · MongoDB Atlas · ngrok · Telegram Bot  
> **Port:** `8888` | **Updated:** 2026-02-20

---

## 📦 โครงสร้างโปรเจค

```
backend_fastapi/
├── main.py                     ← Entry point — FastAPI app, CORS, Webhook, Lifespan
├── database.py                 ← MongoDB connection (Motor async)
├── models.py                   ← Pydantic data models (schemas)
├── auth_utils.py               ← JWT + password hashing
├── logging_config.py           ← Logging ทุก module (แยกไฟล์รายวัน)
├── sequence_utils.py           ← Auto-increment user_id (counters collection)
├── telegram_bot.py             ← Bot logic: commands, send_message, process_update
├── telegram_polling.py         ← Polling mode (ทางเลือกสำหรับ dev โดยไม่ใช้ ngrok)
│
├── routes/                     ← API Endpoints (FastAPI Routers)
│   ├── __init__.py             ← รวม all_routers ทั้งหมด
│   ├── health.py               ← GET /api/health
│   ├── auth.py                 ← POST /api/auth/login, register, refresh
│   ├── users.py                ← CRUD /api/users
│   ├── vegetables.py           ← CRUD /api/vegetables
│   ├── nutrition.py            ← CRUD /api/nutrition
│   ├── diseases_pest.py        ← CRUD /api/diseases, /api/pests
│   ├── locations.py            ← CRUD /api/locations
│   ├── plots.py                ← CRUD /api/plots (แปลงผัก)
│   ├── cctv.py                 ← /api/cctv (กล้องวงจรปิด)
│   ├── planting.py             ← CRUD /api/planting (บันทึกการเพาะปลูก)
│   ├── detection.py            ← /api/detection (ผลการตรวจจับ, ประวัติ)
│   ├── ai_detection.py         ← POST /api/ai/detect (AI วิเคราะห์รูปภาพ)
│   ├── dashboard.py            ← GET /api/dashboard (สรุปสถิติ)
│   ├── telegram.py             ← /api/telegram/... (จัดการ Telegram user)
│   ├── admin_database.py       ← /api/admin/db (ข้อมูล DB สำหรับ admin)
│   ├── contact.py              ← POST /api/contact (ส่งอีเมล Gmail API)
│   └── utils.py                ← Utility endpoints
│
├── services/                   ← Business Logic Layer
│   ├── kimi_ai.py              ← Kimi AI (Moonshot) — วิเคราะห์โรคพืชจากรูป
│   ├── openai_ai.py            ← OpenAI — ทางเลือก AI
│   └── email_service.py        ← Gmail API — ส่งอีเมล contact form
│
├── utils/                      ← Helpers & Utilities
│   ├── exceptions.py           ← AppException, DatabaseException, NotFoundException
│   └── file_handler.py         ← จัดการไฟล์อัปโหลด (รูปภาพ)
│
├── logs/                       ← Log files (แยกรายวัน)
│   ├── app.log                 ← วันปัจจุบัน (active)
│   └── app.log.YYYY-MM-DD     ← Archive ย้อนหลัง 30 วัน
│
├── static/                     ← Static files (รูปภาพที่อัปโหลด)
│
├── start_dev.bat               ← Dev startup script (Backend + ngrok + Webhook)
├── start_dev.ps1               ← Dev startup script (PowerShell version)
├── setup_ngrok_service.ps1     ← ติดตั้ง ngrok เป็น Windows Service (ต้อง Admin)
├── stop_dev.ps1                ← หยุด server และ ngrok
├── .env                        ← Environment variables (Secret — ไม่ commit)
├── .watchfilesignore           ← บอก uvicorn --reload ให้ ignore logs/ และ cache
└── requirements.txt            ← Python dependencies
```

---

## 🔄 Application Flow

### 1. Server Startup

```
start_dev.bat / uvicorn
        │
        ▼
main.py → lifespan()
        │
        ├─► connect_db()           MongoDB Atlas เชื่อมต่อ
        │
        ├─► _start_ngrok_if_not_running()
        │         ├─ ตรวจสอบ localhost:4040
        │         ├─ ถ้าไม่มี → เปิด ngrok.exe อัตโนมัติ
        │         └─ รอ tunnel พร้อม → คืน URL
        │
        └─► get_webhook_info()     ตรวจสอบ Telegram webhook
                  ├─ มี URL → แสดง status
                  └─ ไม่มี → แนะนำให้ call /webhook/telegram/setup
```

### 2. HTTP Request Flow

```
Client (Frontend / Postman)
        │
        ▼
CORS Middleware (ตรวจสอบ origin)
        │
        ▼
JWT Middleware (auth_utils.py)
        │  - ถ้ามี Bearer token → decode → ได้ user
        │  - ถ้าไม่มี token → bypass user (limited access)
        │
        ▼
Router (routes/*.py)
        │
        ├─► database.py → MongoDB Atlas (ผ่าน Motor async)
        │
        ├─► services/kimi_ai.py (สำหรับ AI detection)
        │
        └─► Response → Client
```

### 3. AI Detection Flow

```
POST /api/ai/detect
  + รูปภาพ (multipart form)
        │
        ▼
routes/ai_detection.py
        │
        ├─► utils/file_handler.py  (บันทึกรูปใน static/)
        │
        ├─► services/kimi_ai.py
        │       │
        │       ▼
        │   Kimi AI API (Moonshot)
        │   วิเคราะห์รูป → JSON ผล
        │   { is_plant, is_detected, category,
        │     detected_class_id, confidence, severity_level }
        │
        ├─► database.py            (บันทึกผลใน detection collection)
        │
        └─► Response → { result, disease/pest detail from DB }
```

### 4. Telegram Bot Flow

```
[Telegram Server]
        │  HTTPS POST (ทุกครั้งที่มีข้อความ)
        ▼
ngrok tunnel
        │  https://xxxx.ngrok-free.dev/webhook/telegram
        ▼
main.py → POST /webhook/telegram
        │
        ▼
telegram_bot.py → process_update()
        │
        ├─► /start    → ข้อความต้อนรับ + แนะนำคำสั่ง
        ├─► /help     → รายการคำสั่งทั้งหมด
        ├─► /status   → สถานะแปลงผักของผู้ใช้
        └─► /test     → ทดสอบการเชื่อมต่อ

[Notification]
AI Detection พบโรค/แมลง
        │
        ▼
telegram_bot.send_message()
        │  Telegram API
        ▼
แจ้งเตือนผู้ใช้ทาง Telegram (พร้อม inline button ลิงก์รายละเอียด)
```

---

## 🗄️ MongoDB Collections

| Collection | ข้อมูล | Route |
|------------|--------|-------|
| `users` | บัญชีผู้ใช้, Telegram chat_id | `/api/auth`, `/api/users` |
| `vegetables` | ข้อมูลผักทุกชนิด | `/api/vegetables` |
| `nutrition` | ข้อมูลโภชนาการ | `/api/nutrition` |
| `diseases` | โรคพืชทั้งหมด | `/api/diseases` |
| `pests` | แมลงศัตรูพืช | `/api/pests` |
| `locations` | สถานที่/แปลงผัก | `/api/locations` |
| `plots` | แปลงผักของผู้ใช้ | `/api/plots` |
| `planting` | บันทึกการเพาะปลูก | `/api/planting` |
| `detection` | ประวัติการ detect | `/api/detection` |
| `cctv` | กล้องวงจรปิด | `/api/cctv` |
| `counters` | Auto-increment ID | (internal) |

---

## 🔐 Authentication Flow

```
POST /api/auth/login
  { username, password }
        │
        ▼
auth_utils.py
  ├─ ตรวจสอบ username ใน users collection
  ├─ bcrypt verify password
  └─ สร้าง JWT token (exp: 24h)
        │
        ▼
Response: { access_token, token_type: "bearer" }

Client เก็บ token → ส่งใน Header ทุก request:
Authorization: Bearer <token>
```

---

## 🌐 ngrok & Webhook Setup

```
วิธีที่ 1 — อัตโนมัติ (แนะนำ):
  รัน start_dev.bat → ngrok + webhook ตั้งค่าอัตโนมัติ

วิธีที่ 2 — Backend Auto-start:
  uvicorn main:app → lifespan → _start_ngrok_if_not_running()
  → ngrok.exe เปิดเอง → webhook ยังต้อง setup ด้วย:
  GET /webhook/telegram/setup

วิธีที่ 3 — Windows Service (ถาวร, ต้อง Admin):
  .\setup_ngrok_service.ps1
  → ngrok รันเป็น Service, เปิดอัตโนมัติทุก startup

Domain: https://unvengeful-leeanne-interpressure.ngrok-free.dev
Dashboard: http://localhost:4040
```

---

## 🔧 Environment Variables (.env)

```env
# Database
MONGODB_URI=mongodb+srv://...
DATABASE_NAME=vegetable_db

# Security
SECRET_KEY=...
JWT_ALGORITHM=HS256

# Telegram
TELEGRAM_BOT_TOKEN=...

# AI
KIMI_API_KEY=...
KIMI_API_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-latest

# Email (Gmail API)
ADMIN_EMAIL=...

# App
DEBUG=false
CORS_ORIGINS=http://localhost:5173,...
```

---

## 📡 Key API Endpoints

| Method | Endpoint | คำอธิบาย |
|--------|----------|-----------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/register` | Register |
| `GET` | `/api/dashboard` | สรุปสถิติทั้งหมด |
| `POST` | `/api/ai/detect` | AI วิเคราะห์รูปโรค/แมลง |
| `GET` | `/api/detection/history` | ประวัติการตรวจจับ |
| `GET/POST` | `/api/planting` | จัดการบันทึกการปลูก |
| `GET` | `/api/telegram/status` | สถานะการเชื่อมต่อ Telegram |
| `GET` | `/webhook/telegram/setup` | ตั้ง Telegram webhook |
| `POST` | `/webhook/telegram` | รับข้อความจาก Telegram |
| `POST` | `/api/contact` | ส่งอีเมล contact |
| `GET` | `/docs` | Swagger UI |

---

## 📋 Logging

```
logs/
├── app.log               ← วันนี้ (เขียนอยู่)
└── app.log.2026-02-20   ← Archive (rotate ทุกเที่ยงคืน)

Format: YYYY-MM-DD HH:MM:SS | LEVEL | MODULE | MESSAGE
เก็บย้อนหลัง: 30 วัน (ลบอัตโนมัติ)
```

---

## 🚀 Quick Start

```bash
# Development (แนะนำ)
start_dev.bat

# หรือรัน uvicorn ตรงๆ
uvicorn main:app --host 0.0.0.0 --port 8888 --reload --reload-exclude "logs"

# ดู Swagger API
http://localhost:8888/docs
```
