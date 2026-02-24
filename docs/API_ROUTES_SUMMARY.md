# API Routes Summary

อัปเดตครั้งล่าสุด: 11 กุมภาพันธ์ 2026

## การแก้ไขที่สำคัญ

### 1. Models (models.py) - อัปเดตตาม SQL Schema

#### Detection Model
- **ก่อนแก้ไข**: ใช้ `CCTV_id`, `ID`, `confidence` (ไม่ตรงกับ SQL)
- **หลังแก้ไข**: ใช้ `detection_id`, `disease_pest_id`, `user_id`, `vegetable_id`, `plot_id`, `timestamp`, `image_path`, `notes`
- **เหตุผล**: ตรงกับ SQL schema ที่มี `detection_id`, `disease_pest_id`, `vegetable_id`, `user_id`, `plot_id`

#### CCTV Model
- **เพิ่ม**: `device_ip` field (ขาดหายไปใน model เดิม)

#### HarvestRecord Model
- **เพิ่ม**: `income`, `cost`, `notes`, `created_at`, `planting_id`, `plot_id`
- **เหตุผล**: ตรงกับ SQL schema ที่มีทุก field

#### Plot Model
- **แก้ไข**: `is_deleted` จาก `str` เป็น `int` (ตรงกับ database)

#### User Model
- **เพิ่ม**: `image_path`, `status`

---

## Routes ที่มีทั้งหมด (14 routers)

### 1. Health Routes (`/api/health`)
- `GET /` - Health check

### 2. Auth Routes (`/api/auth`)
- `POST /login` - Login
- `POST /register` - Register
- `POST /refresh` - Refresh token
- `POST /otp/request` - Request OTP
- `POST /otp/verify` - Verify OTP

### 3. AI Detection Routes (`/api/ai`)
- `POST /detect/disease` - Detect disease from image
- `POST /detect/pest` - Detect pest from image
- `POST /chat` - Chat with AI assistant
- `GET /detection-history` - Get AI detection history
- `POST /verify-detection/{detection_id}` - Verify/correct AI detection

### 4. Vegetable Routes (`/api/vegetable`)
- `GET /` - Get all vegetables
- `GET /search?q={query}` - Search vegetables
- `GET /{id}` - Get vegetable by MongoDB ID
- `GET /by-vegetable-id/{vegetable_id}` - Get vegetable by vegetable_id
- `POST /` - Create vegetable
- `PUT /{id}` - Update vegetable
- `DELETE /{id}` - Delete vegetable
- `GET /{id}/nutrition` - Get vegetable nutrition
- `GET /{id}/diseases` - Get diseases related to vegetable

### 5. Nutrition Routes (`/api/nutrition`)
- `GET /` - Get all nutrition types
- `GET /{id}` - Get nutrition by ID
- `GET /vegetable/{vegetable_id}` - Get nutrition for vegetable
- `POST /` - Create nutrition
- `PUT /{id}` - Update nutrition

### 6. Diseases & Pest Routes (`/api/diseases-pest`)
- `GET /` - Get all diseases/pests
- `GET /diseases` - Get diseases only (type=1)
- `GET /pests` - Get pests only (type=2)
- `GET /{id}` - Get by MongoDB ID
- `GET /by-disease-id/{disease_id}` - Get by disease ID
- `POST /` - Create disease/pest
- `PUT /{id}` - Update disease/pest
- `DELETE /{id}` - Delete disease/pest
- `GET /stats/by-type` - Get stats by type
- `GET /stats/top-detected` - Get top detected diseases

### 7. Location Routes (`/api`)
- `GET /provinces` - Get all provinces
- `GET /provinces/{id}` - Get province by ID
- `GET /provinces/{id}/districts` - Get districts in province
- `GET /districts/{id}` - Get district by ID
- `GET /districts/{id}/subdistricts` - Get subdistricts in district
- `GET /subdistricts/{id}` - Get subdistrict by ID

### 8. User Routes (`/api/users`)
- `GET /` - Get all users
- `GET /{id}` - Get user by MongoDB ID
- `GET /by-user-id/{user_id}` - Get user by user_id
- `GET /by-email/{email}` - Get user by email
- `POST /` - Create user
- `PUT /{id}` - Update user
- `DELETE /{id}` - Delete user
- `GET /{id}/plots` - Get user's plots
- `GET /{id}/cctv` - Get user's CCTV
- `PUT /{id}/password` - Change password

### 9. Plot Routes (`/api/plots`)
- `GET /` - Get all plots
- `GET /{id}` - Get plot by MongoDB ID
- `GET /by-plot-id/{plot_id}` - Get plot by plot_id
- `GET /user/{user_id}` - Get plots by user
- `POST /` - Create plot
- `PUT /{id}` - Update plot
- `DELETE /{id}` - Delete plot (soft/hard)
- `POST /{id}/restore` - Restore soft-deleted plot
- `GET /{id}/details` - Get plot with all related data
- `GET /stats/user/{user_id}` - Get plot statistics

### 10. CCTV Routes (`/api/cctv`)
- `GET /` - Get all CCTV
- `GET /{id}` - Get CCTV by ID
- `GET /user/{user_id}` - Get CCTV by user
- `GET /plot/{plot_id}` - Get CCTV by plot
- `POST /` - Create CCTV
- `PUT /{id}` - Update CCTV
- `DELETE /{id}` - Delete CCTV
- `POST /{id}/test-connection` - Test CCTV connection

### 11. Planting Routes (`/api`)

#### Planting Vegetables (`/planting-veg`)
- `GET /planting-veg` - Get all plantings
- `GET /planting-veg/{id}` - Get by MongoDB ID
- `GET /planting-veg/by-planting-id/{planting_id}` - Get by planting_id
- `POST /planting-veg` - Create planting
- `PUT /planting-veg/{id}` - Update planting
- `DELETE /planting-veg/{id}` - Delete planting
- `POST /planting-veg/{id}/complete` - Complete planting (harvest)
- `GET /planting-veg/{id}/details` - Get planting with details

#### Harvest Records (`/harvest-records`)
- `GET /harvest-records` - Get all harvest records
- `GET /harvest-records/{id}` - Get by MongoDB ID
- `GET /harvest-records/by-harvest-id/{harvest_id}` - Get by harvest_id
- `POST /harvest-records` - Create harvest record
- `PUT /harvest-records/{id}` - Update harvest record
- `DELETE /harvest-records/{id}` - Delete harvest record
- `GET /harvest-records/stats/user/{user_id}` - Get harvest stats by vegetable
- `GET /harvest-records/summary/user/{user_id}` - Get harvest summary

### 12. Detection Routes (`/api/detection`)
- `GET /` - Get all detections
- `GET /{id}` - Get by MongoDB ID
- `GET /by-detection-id/{detection_id}` - Get by detection_id
- `GET /by-user/{user_id}` - Get by user
- `GET /by-plot/{plot_id}` - Get by plot
- `GET /by-vegetable/{vegetable_id}` - Get by vegetable
- `GET /by-disease/{disease_pest_id}` - Get by disease/pest
- `POST /` - Create detection
- `PUT /{id}` - Update detection
- `DELETE /{id}` - Delete detection
- `GET /stats/summary` - Get detection summary
- `GET /stats/by-user/{user_id}` - Get user detection stats
- `GET /stats/by-plot/{plot_id}` - Get plot detection stats
- `POST /batch` - Create multiple detections
- `GET /recent/{user_id}` - Get recent detections with details

### 13. Telegram Routes (`/api/telegram`)
- `GET /connection/{user_id}` - Get Telegram connection
- `POST /connect` - Connect Telegram
- `POST /disconnect/{user_id}` - Disconnect Telegram
- `POST /send-notification/{user_id}` - Send notification

### 14. Dashboard Routes (`/api/dashboard`)
- `GET /summary/{user_id}` - Get dashboard summary
- `GET /detection-trends/{user_id}` - Get detection trends
- `GET /crop-performance/{user_id}` - Get crop performance
- `GET /alerts/{user_id}` - Get dashboard alerts

---

## การแก้ไข Routes หลัก

### Detection Routes
- **เพิ่ม**: endpoints สำหรับค้นหาตาม user_id, plot_id, vegetable_id, disease_pest_id
- **เพิ่ม**: stats endpoints สำหรับดูสถิติการตรวจจับ
- **แก้ไข**: field names ให้ตรงกับ SQL schema

### Planting Routes
- **เพิ่ม**: harvest records endpoints ที่รองรับ income, cost, notes
- **เพิ่ม**: planting details endpoint ที่รวมข้อมูลที่เกี่ยวข้อง
- **เพิ่ม**: harvest summary endpoint

### Plot Routes
- **เพิ่ม**: plot details endpoint ที่รวม CCTV, planting, detection, harvest
- **เพิ่ม**: restore endpoint สำหรับกู้คืน soft-deleted plots

### Diseases & Pest Routes
- **เพิ่ม**: `/diseases` endpoint สำหรับดึงเฉพาะโรค
- **เพิ่ม**: `/pests` endpoint สำหรับดึงเฉพาะศัตรูพืช
- **เพิ่ม**: top-detected stats endpoint

### Dashboard Routes (ใหม่)
- **เพิ่ม**: summary endpoint สำหรับ dashboard
- **เพิ่ม**: detection trends endpoint
- **เพิ่ม**: crop performance endpoint
- **เพิ่ม**: alerts endpoint

---

## Database Collections (16 collections)

1. `users` - ข้อมูลผู้ใช้
2. `vegetable` - ข้อมูลผัก
3. `diseases_pest` - ข้อมูลโรคและศัตรูพืช
4. `nutrition` - ข้อมูลโภชนาการ
5. `nutrition_veg` - ความสัมพันธ์ผัก-โภชนาการ
6. `provinces` - ข้อมูลจังหวัด
7. `districts` - ข้อมูลอำเภอ
8. `subdistricts` - ข้อมูลตำบล
9. `plots` - ข้อมูลแปลง
10. `cctv` - ข้อมูลกล้อง CCTV
11. `planting_veg` - ข้อมูลการปลูก
12. `harvest_records` - บันทึกการเก็บเกี่ยว
13. `detection` - บันทึกการตรวจจับ
14. `telegram_connections` - การเชื่อมต่อ Telegram
15. `otp` - ข้อมูล OTP
16. `sqlite_sequence` - ข้อมูล sequence (จากการ import)

---

## การยืนยันความถูกต้อง

ทุก routes ได้รับการตรวจสอบว่า:
1. ✅ Field names ตรงกับ SQL schema
2. ✅ Endpoints ครบถ้วนตามความต้องการ
3. ✅ มี authentication (JWT) ทุก endpoint ยกเว้น public routes
4. ✅ มี error handling ที่เหมาะสม
5. ✅ รองรับทั้ง MongoDB ID และ custom ID (เช่น user_id, plot_id)
