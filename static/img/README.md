# Image Storage Structure

โฟลเดอร์เก็บรูปภาพทั้งหมดของระบบ

## Folder Structure

```
static/img/
├── cctv/               # รูปภาพจากกล้อง CCTV
├── detections/         # รูปภาพผลการตรวจจับโรค/ศัตรูพืช
├── diseases/           # รูปภาพโรคพืช (diseases_pest type=1)
├── diseases_pests/     # รูปภาพโรคและศัตรูพืช (รวม)
├── harvests/           # รูปภาพการเก็บเกี่ยว
├── pests/              # รูปภาพแมลงศัตรูพืช (diseases_pest type=2)
├── plots/              # รูปภาพแปลงผัก
├── temp/               # ไฟล์ชั่วคราว
├── uploads/            # ไฟล์อัปโหลดก่อนประมวลผล
├── users/              # รูปโปรไฟล์ผู้ใช้
└── vegetables/         # รูปภาพผัก
```

## Naming Convention

### Vegetables
Format: `{vegetable_id}_{timestamp}.{ext}`
Example: `001_1707654321.jpg`

### Diseases
Format: `disease_{ID}_{timestamp}.{ext}`
Example: `disease_001_1707654321.jpg`

### Pests
Format: `pest_{ID}_{timestamp}.{ext}`
Example: `pest_001_1707654321.jpg`

### Plots
Format: `plot_{plot_id}_{timestamp}.{ext}`
Example: `plot_001_1707654321.jpg`

### Users
Format: `user_{user_id}_{timestamp}.{ext}`
Example: `user_001_1707654321.jpg`

### Detections
Format: `detection_{detection_id}_{timestamp}.{ext}`
Example: `detection_001_1707654321.jpg`

### CCTV
Format: `cctv_{cctv_id}_{timestamp}.{ext}`
Example: `cctv_001_1707654321.jpg`

## Supported Formats

- JPG / JPEG
- PNG
- WebP

## Max File Size

- 10 MB per file
