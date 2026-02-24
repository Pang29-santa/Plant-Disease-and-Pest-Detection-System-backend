#Requires -Version 5.1
<#
.SYNOPSIS
    Stop Vegetable Project Development Environment
.DESCRIPTION
    หยุด Backend, ngrok, และเคลียร์ทรัพยากรทั้งหมด
#>

Write-Host "============================================" -ForegroundColor Red
Write-Host "    🛑 Stopping Development Environment" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""

# [1/3] หยุด ngrok
Write-Host "[1/3] 🌐 กำลังหยุด ngrok..." -ForegroundColor Yellow
docker stop ngrok_telegram 2>&1 | Out-Null
docker rm ngrok_telegram 2>&1 | Out-Null
Write-Host "      ✅ ngrok หยุดแล้ว" -ForegroundColor Green

# [2/3] หยุด Backend (Python)
Write-Host "[2/3] 🚀 กำลังหยุด Backend..." -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*main.py*"
}
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "      ✅ Backend หยุดแล้ว" -ForegroundColor Green
} else {
    Write-Host "      ℹ️ ไม่พบกระบวนการ Backend" -ForegroundColor Gray
}

# [3/3] ลบ webhook
Write-Host "[3/3] 🔧 กำลังลบ Telegram Webhook..." -ForegroundColor Yellow
$envFile = "D:\pang\project\backend_fastapi\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]*)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    
    if ($env:TELEGRAM_BOT_TOKEN) {
        try {
            Invoke-RestMethod -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/deleteWebhook" -Method Post -TimeoutSec 5 | Out-Null
            Write-Host "      ✅ Webhook ลบแล้ว" -ForegroundColor Green
        } catch {
            Write-Host "      ⚠️ ไม่สามารถลบ webhook ได้" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "✅ หยุดระบบทั้งหมดเรียบร้อย" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
