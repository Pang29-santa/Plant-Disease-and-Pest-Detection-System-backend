# 🌱 Vegetable Project - Development Setup Guide

## วิธีรันระบบสำหรับ Development

### ⚡ วิธีที่ 1: ใช้ PowerShell Script (แนะนำ)

#### 1. สร้าง Shortcut บน Desktop (ครั้งแรกเท่านั้น)
```powershell
cd D:\pang\project\backend_fastapi
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
```

จากนั้นจะมี Shortcut 2 อันบน Desktop:
- 🌱 **Start Vegetable Dev** - รันระบบทั้งหมด
- 🛑 **Stop Vegetable Dev** - หยุดระบบทั้งหมด

#### 2. รันระบบ
ดับเบิลคลิกที่ **"🌱 Start Vegetable Dev"** บน Desktop

หรือรันผ่าน PowerShell:
```powershell
.\start_dev.ps1
```

#### 3. หยุดระบบ
ดับเบิลคลิกที่ **"🛑 Stop Vegetable Dev"** บน Desktop

หรือรันผ่าน PowerShell:
```powershell
.\stop_dev.ps1
```

---

### ⚡ วิธีที่ 2: ใช้ Batch File

```batch
start_dev.bat
```

---

### 🔧 วิธีที่ 3: รันแยกส่วน (Manual)

#### Terminal 1: Backend
```powershell
cd D:\pang\project\backend_fastapi
.venv\Scripts\activate
python main.py
```

#### Terminal 2: ngrok
```powershell
docker run -d --name ngrok_telegram -e NGROK_AUTHTOKEN=39jmBBaosyOoxppkY72SUpB1z7V_7hauKc9jPy74oqZnYSDa8 -p 4040:4040 ngrok/ngrok:latest http host.docker.internal:8888
```

#### Terminal 3: ตั้งค่า Webhook
```powershell
cd D:\pang\project\backend_fastapi
.venv\Scripts\activate
python setup_ngrok_telegram.py
```

---

## 📁 ไฟล์ที่สร้างขึ้น

| ไฟล์ | ใช้สำหรับ |
|------|----------|
| `start_dev.ps1` | รันระบบทั้งหมดอัตโนมัติ |
| `stop_dev.ps1` | หยุดระบบทั้งหมด |
| `start_dev.bat` | รันระบบ (Batch version) |
| `create_shortcut.ps1` | สร้าง Shortcut บน Desktop |
| `setup_ngrok_telegram.py` | ตั้งค่า Telegram Webhook |
| `telegram_polling.py` | รัน Bot แบบ Polling (ไม่ต้องใช้ ngrok) |

---

## 🌐 URL ที่ใช้งานได้

| บริการ | URL |
|--------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8888 |
| ngrok Dashboard | http://localhost:4040 |
| API Documentation | http://localhost:8888/docs |

---

## 📝 หมายเหตุสำคัญ

### 🔴 ทุกครั้งที่ปิด/เปิดเครื่องใหม่
ต้อง **รัน `start_dev.ps1` ใหม่** เพราะ:
1. Docker container จะหยุดทำงาน
2. ngrok URL จะเปลี่ยน (free plan)
3. Telegram webhook ต้องตั้งค่าใหม่

### 🟡 ถ้าไม่ต้องการใช้ ngrok
ใช้ **Polling Mode** แทน:
```powershell
python telegram_polling.py
```
(ไม่ต้องใช้ ngrok แต่ต้องรัน script นี้แยก)

### 🟢 Docker Compose (ถ้าต้องการใช้)
```powershell
docker-compose up -d
```
แต่ต้องตั้งค่า webhook เองผ่าน `setup_ngrok_telegram.py`

---

## 🐛 แก้ไขปัญหา

### ngrok ไม่ทำงาน
```powershell
docker stop ngrok_telegram
docker rm ngrok_telegram
.\start_dev.ps1
```

### Backend ไม่ตอบสนอง
```powershell
.\stop_dev.ps1
.\start_dev.ps1
```

### Telegram Bot ไม่ตอบสนอง
ตรวจสอบ webhook:
```powershell
$env:TELEGRAM_BOT_TOKEN = "your_token"
Invoke-RestMethod -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

---

## 💡 Tips

- ใช้ **PowerShell 7** ถ้ามี (เร็วกว่า)
- ถ้าเจอ error `ExecutionPolicy` ให้รัน:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
- ดู log ทั้งหมดได้ที่: `logs/app.log`
