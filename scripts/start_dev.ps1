#Requires -Version 5.1
<#
.SYNOPSIS
    Start Vegetable Project Development Environment
.DESCRIPTION
    รัน Backend, ngrok, และตั้งค่า Telegram Webhook อัตโนมัติ
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Green
Write-Host "    🌱 Vegetable Project - Development Mode" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# ไปที่โฟลเดอร์โปรเจค
$ProjectPath = "D:\pang\project\backend_fastapi"
Set-Location -Path $ProjectPath

# โหลด environment variables
$envFile = Join-Path $ProjectPath ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]*)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# ============================================
# [1/4] รัน Backend Server
# ============================================
Write-Host "[1/4] 🚀 กำลังรัน Backend Server..." -ForegroundColor Cyan

$backendJob = Start-Job -ScriptBlock {
    param($path)
    Set-Location $path
    & .venv\Scripts\python.exe main.py
} -ArgumentList $ProjectPath

# รอให้ backend เริ่มต้น
Start-Sleep -Seconds 5

# ตรวจสอบว่า backend ทำงาน
$backendReady = $false
$retryCount = 0
while (-not $backendReady -and $retryCount -lt 10) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8888/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "      ✅ Backend พร้อมใช้งาน" -ForegroundColor Green
        }
    } catch {
        $retryCount++
        Start-Sleep -Seconds 1
    }
}

if (-not $backendReady) {
    Write-Host "      ⚠️ Backend อาจยังไม่พร้อม แต่จะดำเนินการต่อ..." -ForegroundColor Yellow
}

# ============================================
# [2/4] รัน ngrok
# ============================================
Write-Host "[2/4] 🌐 กำลังรัน ngrok..." -ForegroundColor Cyan

$ngrokExe = "$env:LOCALAPPDATA\ngrok\ngrok.exe"
if (-not (Test-Path $ngrokExe)) {
    # fallback: หา ngrok จาก PATH
    $ngrokExe = (Get-Command ngrok -ErrorAction SilentlyContinue).Source
}

if (-not $ngrokExe) {
    Write-Host "      ❌ ไม่พบ ngrok.exe กรุณาติดตั้ง ngrok ก่อน" -ForegroundColor Red
    exit 1
}

# หยุด ngrok เก่าถ้ามี
$existingNgrok = Get-Process -Name "ngrok" -ErrorAction SilentlyContinue
if ($existingNgrok) {
    Write-Host "      🗑️ หยุด ngrok เก่า..." -ForegroundColor Yellow
    $existingNgrok | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# รัน ngrok native exe (background, minimized)
Write-Host "      🚀 รัน ngrok: $ngrokExe" -ForegroundColor Gray
Start-Process -FilePath $ngrokExe `
    -ArgumentList "http 8888 --domain=unvengeful-leeanne-interpressure.ngrok-free.dev" `
    -WindowStyle Minimized

# รอให้ ngrok เริ่มต้น
Start-Sleep -Seconds 6


# ============================================
# [3/4] ดึง ngrok URL
# ============================================
Write-Host "[3/4] 🔍 กำลังดึง ngrok URL..." -ForegroundColor Cyan

$ngrokUrl = $null
$retryCount = 0
while (-not $ngrokUrl -and $retryCount -lt 15) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:4040/api/tunnels" -TimeoutSec 5 -ErrorAction Stop
        $tunnels = $response.Content | ConvertFrom-Json
        
        foreach ($tunnel in $tunnels.tunnels) {
            if ($tunnel.proto -eq "https") {
                $ngrokUrl = $tunnel.public_url
                break
            }
        }
        
        if (-not $ngrokUrl -and $tunnels.tunnels.Count -gt 0) {
            $ngrokUrl = $tunnels.tunnels[0].public_url
        }
    } catch {
        $retryCount++
        Start-Sleep -Seconds 1
    }
}

if ($ngrokUrl) {
    Write-Host "      ✅ ngrok URL: $ngrokUrl" -ForegroundColor Green
} else {
    Write-Host "      ❌ ไม่สามารถดึง ngrok URL ได้" -ForegroundColor Red
    exit 1
}

# ============================================
# [4/4] ตั้งค่า Telegram Webhook
# ============================================
Write-Host "[4/4] 🔧 กำลังตั้งค่า Telegram Webhook..." -ForegroundColor Cyan

$webhookUrl = "$ngrokUrl/webhook/telegram"
$telegramApiUrl = "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN"

try {
    # ลบ webhook เก่า
    Invoke-RestMethod -Uri "$telegramApiUrl/deleteWebhook" -Method Post -TimeoutSec 10 | Out-Null
    
    # ตั้งค่า webhook ใหม่
    $payload = @{
        url = $webhookUrl
        allowed_updates = @("message")
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "$telegramApiUrl/setWebhook" -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 10
    
    if ($response.ok) {
        Write-Host "      ✅ Webhook ตั้งค่าสำเร็จ!" -ForegroundColor Green
    } else {
        Write-Host "      ❌ ไม่สามารถตั้งค่า webhook ได้: $($response.description)" -ForegroundColor Red
    }
} catch {
    Write-Host "      ❌ Error: $_" -ForegroundColor Red
}

# แสดงข้อมูลสรุป
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "✅ ระบบพร้อมใช้งาน!" -ForegroundColor Green
Write-Host ""
Write-Host "📱 Frontend:    http://localhost:5173" -ForegroundColor Yellow
Write-Host "🔌 Backend:     http://localhost:8888" -ForegroundColor Yellow
Write-Host "🌐 ngrok:       $ngrokUrl" -ForegroundColor Yellow
Write-Host "📊 ngrok Dashboard: http://localhost:4040" -ForegroundColor Yellow
Write-Host "🤖 Bot Webhook: $webhookUrl" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "💡 คำสั่งที่ใช้ได้:" -ForegroundColor Cyan
Write-Host "   - ตรวจสอบ webhook: docker logs ngrok_telegram"
Write-Host "   - หยุดทั้งหมด:     docker stop ngrok_telegram"
Write-Host ""
Write-Host "กด Enter เพื่อปิดหน้าต่างนี้ (Backend จะยังทำงานในพื้นหลัง)..." -ForegroundColor Gray
Read-Host

# แสดง log backend
Receive-Job -Job $backendJob -Keep | Select-Object -Last 20
