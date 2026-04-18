<#
.SYNOPSIS
    启动 AICompanion 全部进程的编排脚本

.DESCRIPTION
    按正确依赖顺序启动:
      1) GPT-SoVITS-V2 API (可选; 如未训练好可跳过, OLV 会回退到 edge_tts)
      2) Open-LLM-VTuber 主服务
      3) 邮件守护进程 (可选; 仅当 mail_config.json 已配置)

    每个进程在新的 PowerShell 窗口中运行, 方便单独查看日志.

.PARAMETER SovitsPath
    GPT-SoVITS 项目根目录路径. 留空则跳过 SoVITS 启动.

.PARAMETER SkipMailDaemon
    跳过邮件守护进程启动.

.EXAMPLE
    .\start-all.ps1 -SovitsPath "D:\GPT-SoVITS-v2"

.EXAMPLE
    .\start-all.ps1 -SkipMailDaemon
#>

[CmdletBinding()]
param(
    [string]$SovitsPath = "",
    [switch]$SkipMailDaemon
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OlvDir = Join-Path $ProjectRoot "Open-LLM-VTuber"
$MailConfig = Join-Path $ProjectRoot "mcp_servers\mail_server\mail_config.json"

function Start-In-NewWindow {
    param(
        [string]$Title,
        [string]$WorkingDir,
        [string]$Command
    )
    $cmd = "Set-Host -DisplayName ('{0}') ; Set-Location '{1}' ; Write-Host '== {0} ==' -ForegroundColor Cyan ; {2}" -f $Title, $WorkingDir, $Command
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd | Out-Null
    Write-Host ("  [OK] " + $Title + " launched in new window") -ForegroundColor Green
}

Write-Host "====================================="
Write-Host " AICompanion - Start All Services"
Write-Host "====================================="
Write-Host ("Project root: " + $ProjectRoot)
Write-Host ""

# ---- 1) GPT-SoVITS API ----
if ($SovitsPath -and (Test-Path $SovitsPath)) {
    Write-Host "[1/3] Starting GPT-SoVITS-V2 API..." -ForegroundColor Yellow
    $apiScript = Join-Path $SovitsPath "api_v2.py"
    if (Test-Path $apiScript) {
        Start-In-NewWindow -Title "GPT-SoVITS API" -WorkingDir $SovitsPath -Command "python api_v2.py"
        Write-Host "  Waiting 10s for SoVITS to start listening on :9880..." -ForegroundColor Gray
        Start-Sleep -Seconds 10
    } else {
        Write-Warning ("  api_v2.py not found at " + $apiScript + ". Skipping SoVITS.")
    }
} else {
    Write-Host "[1/3] Skipping GPT-SoVITS (no -SovitsPath given)." -ForegroundColor DarkGray
    Write-Host "      OLV will use whatever tts_model is set in conf.yaml" -ForegroundColor DarkGray
}

# ---- 2) OLV main server ----
Write-Host "[2/3] Starting Open-LLM-VTuber main server..." -ForegroundColor Yellow
Start-In-NewWindow -Title "OLV Server" -WorkingDir $OlvDir -Command "uv run run_server.py"
Write-Host "  Waiting 8s for OLV to bind on :12393..." -ForegroundColor Gray
Start-Sleep -Seconds 8

# ---- 3) Mail daemon (optional) ----
if ($SkipMailDaemon) {
    Write-Host "[3/3] Skipping mail daemon (-SkipMailDaemon)." -ForegroundColor DarkGray
} elseif (-not (Test-Path $MailConfig)) {
    Write-Host "[3/3] Skipping mail daemon (mail_config.json not found)." -ForegroundColor DarkGray
    Write-Host "      Copy mail_config.example.json to mail_config.json to enable." -ForegroundColor DarkGray
} else {
    Write-Host "[3/3] Starting mail daemon..." -ForegroundColor Yellow
    Start-In-NewWindow -Title "Mail Daemon" -WorkingDir $ProjectRoot -Command "python -m mcp_servers.mail_server.daemon"
}

Write-Host ""
Write-Host "All services launched." -ForegroundColor Green
Write-Host "Open http://localhost:12393 in browser, or run the Electron client." -ForegroundColor Cyan
