# ============================================================
# Setup ngrok as Windows Service (ต้องรันในฐานะ Administrator)
# ============================================================

$ngrokExe = "$env:LOCALAPPDATA\ngrok\ngrok.exe"
$configPath = "$env:LOCALAPPDATA\ngrok\ngrok.yml"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ngrok Windows Service Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ตรวจสอบ Admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "`n❌ กรุณารัน PowerShell ในฐานะ Administrator!" -ForegroundColor Red
    Write-Host "   คลิกขวา PowerShell → Run as Administrator" -ForegroundColor Yellow
    Read-Host "กด Enter เพื่อปิด"
    exit 1
}

# อัพเดท ngrok.yml ให้มี tunnel config
Write-Host "`n📝 อัพเดท ngrok config..." -ForegroundColor Yellow
$configContent = @"
version: "3"
agent:
    authtoken: 39jmBBaosyOoxppkY72SUpB1z7V_7hauKc9jPy74oqZnYSDa8

tunnels:
  vegapp:
    proto: http
    addr: 8888
    domain: unvengeful-leeanne-interpressure.ngrok-free.dev
"@

Set-Content -Path $configPath -Value $configContent -Encoding UTF8
Write-Host "✅ Config อัพเดทแล้ว: $configPath" -ForegroundColor Green

# ถอนการติดตั้ง service เก่า (ถ้ามี)
Write-Host "`n🗑️  ลบ service เก่า (ถ้ามี)..." -ForegroundColor Yellow
& $ngrokExe service uninstall 2>&1 | Out-Null

# ติดตั้ง ngrok service ใหม่
Write-Host "⚙️  ติดตั้ง ngrok service..." -ForegroundColor Yellow
$result = & $ngrokExe service install --config="$configPath" 2>&1
Write-Host $result

# เริ่ม service
Write-Host "`n🚀 เริ่ม ngrok service..." -ForegroundColor Yellow
$result2 = & $ngrokExe service start 2>&1
Write-Host $result2

# ตรวจสอบ service
Start-Sleep -Seconds 3
$svc = Get-Service -Name "ngrok" -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "`n✅ ngrok service สถานะ: $($svc.Status)" -ForegroundColor Green
    Write-Host "   StartType: $($svc.StartType)" -ForegroundColor Cyan
    
    # ตั้งให้ start อัตโนมัติ
    Set-Service -Name "ngrok" -StartupType Automatic
    Write-Host "✅ ตั้ง Startup Type เป็น Automatic แล้ว" -ForegroundColor Green
} else {
    Write-Host "`n⚠️  ไม่พบ service 'ngrok'" -ForegroundColor Yellow
}

# ตรวจสอบ tunnel
Start-Sleep -Seconds 3
Write-Host "`n🌐 ตรวจสอบ tunnel..." -ForegroundColor Yellow
try {
    $tunnels = Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -TimeoutSec 5
    foreach ($t in $tunnels.tunnels) {
        Write-Host "   ✅ $($t.proto.ToUpper()): $($t.public_url)" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  ngrok API ยังไม่พร้อม รอสักครู่แล้วตรวจสอบที่ http://localhost:4040" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " เสร็จสิ้น! ngrok จะรันอัตโนมัติทุก startup" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Read-Host "`nกด Enter เพื่อปิด"
