# 🤖 Plant Disease Detection API

Backend API สำหรับวิเคราะห์โรคพืชและศัตรูพืชด้วย Machine Learning (TensorFlow MobileNetV2)

## 📋 ภาพรวมระบบ

ระบบนี้เป็น FastAPI Backend ที่รับรูปภาพจากผู้ใช้ แล้วใช้โมเดล AI (MobileNetV2) วิเคราะห์ว่าเป็นพืชที่มีโรค/ศัตรูพืชหรือไม่ พร้อมบอกชนิดและความน่าจะเป็น

### ✨ ฟีเจอร์หลัก
- 🔍 **AI Detection** - วิเคราะห์รูปภาพด้วย MobileNetV2 (16 classes)
- 📊 **Top-3 Predictions** - แสดงผลลัพธ์ที่เป็นไปได้ 3 อันดับ
- ✅ **Auto Healthy Check** - ถ้าความมั่นใจต่ำกว่า threshold ถือว่าพืชสุขภาพดี
- 🔐 **JWT Auth** - ระบบล็อกอินด้วย JWT
- 🌐 **i18n Support** - รองรับหลายภาษา (ไทย/อังกฤษ)
- 🤖 **Telegram Bot** - แจ้งเตือนผ่าน Telegram
- 📈 **Dashboard** - สถิติการใช้งานและรายงาน

---

## 📁 โครงสร้างโปรเจกต์

```
backend_fastapi/
│
├── 📄 ไฟล์หลัก (Core Files)
│   ├── main.py                    # Entry point FastAPI
│   ├── models.py                  # Pydantic Models / DB Schema
│   ├── database.py                # MongoDB Connection
│   ├── auth_utils.py             # JWT Authentication utilities
│   ├── ai_diagnosis_ensemble.py  # AI Ensemble logic
│   ├── telegram_bot.py           # Telegram bot handler
│   ├── logging_config.py         # Logging configuration
│   ├── sequence_utils.py         # Sequence/ID generators
│   ├── .env                      # Environment variables
│   ├── requirements.txt          # Python dependencies
│   ├── Dockerfile                # Docker config
│   └── docker-compose.yml        # Docker compose
│
├── 📁 models/                     # 🤖 ML Models
│   ├── model_round3.h5           # TensorFlow model (MobileNetV2)
│   └── class_names_round3.json   # 16 class names mapping
│
├── 📁 routes/                     # 🛣️ API Routes
│   ├── ai_detection.py           # /api/ai/* - AI endpoints
│   ├── auth.py                   # /api/auth/* - Login/Register
│   ├── users.py                  # /api/users/* - User management
│   ├── vegetables.py             # /api/vegetables/* - Crop data
│   ├── diseases_pest.py          # /api/diseases/* - Disease info
│   ├── plots.py                  # /api/plots/* - Farm plots
│   ├── dashboard.py              # /api/dashboard/* - Statistics
│   └── ...                       # Other routes
│
├── 📁 services/                   # ⚙️ Business Logic
│   ├── tf_model_service.py       # TensorFlow model service
│   ├── kimi_ai.py               # Kimi AI integration
│   └── ...
│
├── 📁 utils/                      # 🛠️ Utilities
│   └── file_handler.py          # Image upload handler
│
├── 📁 static/                     # 🖼️ Static Files
│   └── img/                     # Uploaded images
│
├── 📁 logs/                       # 📝 Log Files
│   └── *.log                    # Application logs
│
├── 📁 docs/                       # 📚 Documentation
│   ├── API_CHANGES.md           # API changelog
│   ├── ARCHITECTURE.md          # System architecture
│   ├── DEV_SETUP.md            # Developer setup guide
│   └── ...
│
├── 📁 scripts/                    # 🔧 Scripts
│   ├── start_dev.bat           # Start dev server (Windows)
│   ├── start_dev.ps1           # Start dev server (PowerShell)
│   ├── stop_dev.ps1            # Stop dev server
│   ├── setup_ngrok_service.ps1 # Setup ngrok tunnel
│   └── telegram_polling.py     # Telegram bot polling
│
├── 📁 tests/                      # 🧪 Test Files
│   └── test_model.py           # Model testing script
│
├── 📁 fine_tuned_v2/              # 💾 Old Models (backup)
│   └── ...                     # Previous model versions
│
└── 📁 .venv/                      # 🐍 Python Virtual Environment
```

---

## 🚀 การเริ่มต้นใช้งาน

### 1. ติดตั้ง Dependencies
```bash
cd backend_fastapi
pip install -r requirements.txt
```

### 2. ตั้งค่า ML Model (⚠️ สำคัญ!)

**โมเดลไม่ได้อยู่ใน GitHub (ขนาดใหญ่ 27MB)** ต้องดาวน์โหลดมาใส่เอง:

#### วิธีที่ 1: ดาวน์โหลดจากลิงก์ (ถ้ามี)
```bash
# สร้างโฟลเดอร์ models
mkdir models

# ดาวน์โหลดโมเดล (แทน YOUR_DOWNLOAD_LINK ด้วยลิงก์จริง)
curl -L "YOUR_DOWNLOAD_LINK" -o models/model_round3.h5

# ดาวน์โหลด class names
curl -L "YOUR_DOWNLOAD_LINK" -o models/class_names_round3.json
```

#### วิธีที่ 2: คัดลอกจากเครื่องที่มีโมเดลอยู่แล้ว
```bash
# จากเครื่องที่มีโมเดล
scp models/model_round3.h5 user@new-server:/path/to/backend_fastapi/models/
scp models/class_names_round3.json user@new-server:/path/to/backend_fastapi/models/
```

#### วิธีที่ 3: เทรนโมเดลเอง
ดูวิธีเทรนโมเดลได้ที่: `D:\pang\project\trainmodel\scripts\train_model.py`

#### โครงสร้างที่ถูกต้อง
```
backend_fastapi/
└── models/
    ├── model_round3.h5           ← ต้องมี (27MB)
    └── class_names_round3.json   ← มีใน GitHub อยู่แล้ว
```

### 3. ตั้งค่า Environment Variables
สร้างไฟล์ `.env`:
```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
JWT_SECRET_KEY=your-secret-key
TELEGRAM_BOT_TOKEN=your-bot-token
```

### 4. รัน Server
```bash
# Windows
.\scripts\start_dev.bat

# หรือ PowerShell
.\scripts\start_dev.ps1
```

---

## 🔌 API Endpoints หลัก

### AI Detection
```
POST /api/ai/detect          # วิเคราะห์ด้วย Kimi AI
POST /api/ai/detect-tf       # วิเคราะห์ด้วย TensorFlow Model ⭐
GET  /api/ai/health          # ตรวจสอบสถานะ AI Services
```

### Authentication
```
POST /api/auth/login         # Login
POST /api/auth/register      # Register
POST /api/auth/refresh       # Refresh token
```

### Diseases & Pests
```
GET  /api/diseases           # รายการโรค/ศัตรูพืชทั้งหมด
GET  /api/diseases/{id}      # ข้อมูลเฉพาะโรค
```

---

## 🤖 AI Model Details

### Model Info
- **Architecture**: MobileNetV2
- **Input Size**: 160x160x3
- **Classes**: 16 classes (8 diseases + 8 pests)
- **Model File**: `models/model_round3.h5` (27MB)
- **Framework**: TensorFlow/Keras

### Class Names (16 Classes)
| # | ชื่อ (ไทย) | ชื่อ (อังกฤษ) | ประเภท |
|---|-----------|--------------|--------|
| 1 | โรคแอนแทรคโนส | Anthracnose | Disease |
| 2 | แมลงหวี่ขาว | Bemisia tabaci | Pest |
| 3 | โรคแผลวงกลมสีน้ำตาลไหม้ | Cercospora Leaf Spot | Disease |
| 4 | หนอนกระทู้ผัก | Common Cutworm | Pest |
| 5 | หนอนใยผัก | Diamondback Moth | Pest |
| 6 | โรคราน้ำค้าง | Downy Mildew | Disease |
| 7 | ด้วงหมัดผัก | Flea Beetle | Pest |
| 8 | โรคใบไหม้ | Leaf Blight | Disease |
| 9 | หนอนชอนใบ | Leaf Miner | Pest |
| 10 | โรคใบจุด | Leaf Spot Disease | Disease |
| 11 | เพลี้ยจักจั่น | Leafhopper | Pest |
| 12 | โรคราแป้ง | Powdery Mildew | Disease |
| 13 | ด้วงเต่าแตงแดง | Red Pumpkin Beetle | Pest |
| 14 | โรคราสนิม | Rust Disease | Disease |
| 15 | เพลี้ยไฟ | Thrips | Pest |
| 16 | โรคราสนิมขาว | White Rust Disease | Disease |

### Healthy Detection Logic
```python
if confidence < 0.5:
    result = "Healthy (พืชสุขภาพดี)"
else:
    result = predicted_disease_or_pest
```

---

## 📊 Database Schema (MongoDB)

### Collections
- `users` - ข้อมูลผู้ใช้
- `detections` - ประวัติการตรวจจับ
- `diseases_pest` - ข้อมูลโรค/ศัตรูพืช
- `plots` - ข้อมูลแปลงเกษตร
- `vegetables` - ข้อมูลพืชผัก

---

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up --build

# หรือ build อย่างเดียว
docker build -t plant-disease-api .
```

---

## 📝 Logs

- ไฟล์ log อยู่ใน `logs/` directory
- เก็บ log ย้อนหลัง 30 วัน
- Format: `YYYY-MM-DD.log`

---

## 🔧 Troubleshooting

### โมเดลโหลดไม่ได้
```bash
# ตรวจสอบว่าไฟล์อยู่ใน models/
ls models/
# ควรมี: model_round3.h5, class_names_round3.json
```

### MongoDB เชื่อมต่อไม่ได้
- ตรวจสอบ `MONGODB_URI` ใน `.env`
- ตรวจสอบ IP Whitelist ใน MongoDB Atlas

---

## 👥 ผู้พัฒนา

- **Backend**: FastAPI + MongoDB
- **AI/ML**: TensorFlow MobileNetV2
- **Model Training**: D:\pang\project\trainmodel\

---

## 📄 License

Private Project - All rights reserved
