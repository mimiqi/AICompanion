<#
.SYNOPSIS
    一键启动 AICompanion 全部资源 (GPT-SoVITS API + OLV 主服务 + 可选 Mail Daemon)。

.DESCRIPTION
    按依赖顺序拉起整个桌宠链路:
      1) 预检 9880 / 12393 端口,被占则报错(或 -ForceKill 强杀)
      2) 新窗口启动 GPT-SoVITS api_v2.py (用整合包内置 runtime\python.exe)
      3) 轮询 9880 端口直到就绪 (而不是固定 sleep)
      4) 新窗口启动 OLV run_server.py (修好 uv PATH)
      5) 轮询 12393 端口直到就绪 (faster-whisper 首次会下载模型,可能慢)
      6) 可选:邮件守护 (默认跳过,需要 mail_config.json + 显式不带 -SkipMailDaemon)
      7) 可选:浏览器自动打开 :12393

    每个服务在独立 PowerShell 窗口运行,方便单独看日志。

.PARAMETER SovitsPath
    GPT-SoVITS 整合包根目录。默认指向当前安装路径。
    传入空字符串或 -SkipSovits 则跳过 SoVITS 启动。

.PARAMETER UvPath
    uv.exe 所在目录,用于在 OLV 新窗口里修 PATH。默认 C:\Users\mimiqi\.local\bin。

.PARAMETER SkipSovits
    跳过 SoVITS API 启动 (此时 OLV 应配合改 tts_model 为 edge_tts)。

.PARAMETER SkipMailDaemon
    跳过邮件守护 (默认就跳,因为 mail_config.json 通常未配置)。

.PARAMETER ForceKill
    端口被占时强杀占用进程后再启;默认行为是报错退出。

.PARAMETER NoBrowser
    跳过自动打开浏览器。

.PARAMETER SovitsTimeout
    等待 SoVITS 监听 9880 的最长秒数。默认 60。

.PARAMETER OlvTimeout
    等待 OLV 监听 12393 的最长秒数 (faster-whisper 首次下载模型时可能更久)。默认 90。

.EXAMPLE
    .\start-all.ps1
    无参数,启全部默认值,自动开浏览器

.EXAMPLE
    .\start-all.ps1 -ForceKill
    端口被占时直接强杀重启

.EXAMPLE
    .\start-all.ps1 -SkipSovits -NoBrowser
    只启 OLV (配合 conf.yaml tts_model='edge_tts'),不开浏览器
#>

[CmdletBinding()]
param(
    [string]$SovitsPath = "D:\GPT-SoVITS\GPT-SoVITS-v2pro-2025\GPT-SoVITS-v2pro-20250604",
    [string]$UvPath = "C:\Users\mimiqi\.local\bin",
    [switch]$SkipSovits,
    [switch]$SkipMailDaemon,
    [switch]$ForceKill,
    [switch]$NoBrowser,
    [int]$SovitsTimeout = 60,
    [int]$OlvTimeout = 90
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OlvDir = Join-Path $ProjectRoot "Open-LLM-VTuber"
$MailConfig = Join-Path $ProjectRoot "mcp_servers\mail_server\mail_config.json"

# ---------- helper functions ----------

function Test-Port {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSec = 60, [string]$Name = "service")
    $start = Get-Date
    while (((Get-Date) - $start).TotalSeconds -lt $TimeoutSec) {
        if (Test-Port -Port $Port) {
            $elapsed = [int]((Get-Date) - $start).TotalSeconds
            Write-Host ("  [READY] {0} listening on :{1} (took {2}s)" -f $Name, $Port, $elapsed) -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Warning ("  [TIMEOUT] {0} did not bind :{1} within {2}s" -f $Name, $Port, $TimeoutSec)
    return $false
}

function Clear-Port {
    param([int]$Port, [bool]$Force)
    if (-not (Test-Port -Port $Port)) { return $true }

    if (-not $Force) {
        Write-Error ("Port {0} already in use. Pass -ForceKill or run .\stop-all.ps1 first." -f $Port)
        return $false
    }

    $procIds = (Get-NetTCPConnection -LocalPort $Port -State Listen).OwningProcess | Select-Object -Unique
    foreach ($p in $procIds) {
        try {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            $name = if ($proc) { $proc.ProcessName } else { "<unknown>" }
            Write-Host ("  Killing pid {0} ({1}) holding :{2}" -f $p, $name, $Port) -ForegroundColor Yellow
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warning ("  Failed to kill pid {0}: {1}" -f $p, $_.Exception.Message)
        }
    }
    Start-Sleep -Seconds 1
    return -not (Test-Port -Port $Port)
}

function Start-In-NewWindow {
    param(
        [string]$Title,
        [string]$WorkingDir,
        [string]$Command
    )
    # 把多行 Command 拼成一行 (用分号分隔),避免 here-string 在透传时被转义吃掉
    $oneLine = ($Command -split "`r?`n" | Where-Object { $_.Trim() -ne "" }) -join " ; "
    $launch = "Set-Location '{0}' ; Write-Host '== {1} ==' -ForegroundColor Cyan ; {2}" -f $WorkingDir, $Title, $oneLine
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $launch | Out-Null
    Write-Host ("  [LAUNCHED] {0} (new window)" -f $Title) -ForegroundColor Green
}

# ---------- main flow ----------

Write-Host "============================================================"
Write-Host " AICompanion - Start All Services"
Write-Host "============================================================"
Write-Host ("Project root : {0}" -f $ProjectRoot)
Write-Host ("OLV dir      : {0}" -f $OlvDir)
Write-Host ("SoVITS path  : {0}" -f $(if ($SkipSovits) { "(skipped)" } else { $SovitsPath }))
Write-Host ("ForceKill    : {0}" -f $ForceKill)
Write-Host ""

# ---- Step 1: GPT-SoVITS API ----

if ($SkipSovits) {
    Write-Host "[1/3] Skipping GPT-SoVITS (-SkipSovits)." -ForegroundColor DarkGray
    Write-Host "      OLV will use whatever tts_model is set in conf.yaml" -ForegroundColor DarkGray
} elseif (-not (Test-Path $SovitsPath)) {
    Write-Warning ("[1/3] SovitsPath '{0}' not found. Skipping SoVITS." -f $SovitsPath)
} else {
    Write-Host "[1/3] Starting GPT-SoVITS-V2 API..." -ForegroundColor Yellow

    if (-not (Clear-Port -Port 9880 -Force $ForceKill)) { exit 1 }

    $apiScript = Join-Path $SovitsPath "api_v2.py"
    if (-not (Test-Path $apiScript)) {
        Write-Error ("  api_v2.py not found at {0}" -f $apiScript)
        exit 1
    }

    $pyExe = Join-Path $SovitsPath "runtime\python.exe"
    if (-not (Test-Path $pyExe)) {
        Write-Warning ("  runtime\python.exe not found, falling back to system 'python' (deps may be missing)")
        $pyExe = "python"
    }

    $svCmd = "& '{0}' api_v2.py" -f $pyExe
    Start-In-NewWindow -Title "GPT-SoVITS API" -WorkingDir $SovitsPath -Command $svCmd

    Write-Host ("  Waiting for SoVITS to bind :9880 (timeout {0}s)..." -f $SovitsTimeout) -ForegroundColor Gray
    if (-not (Wait-Port -Port 9880 -TimeoutSec $SovitsTimeout -Name "SoVITS")) {
        Write-Error "  SoVITS failed to start. Check the SoVITS API window for errors."
        exit 1
    }
}

# ---- Step 2: OLV main server ----

Write-Host "[2/3] Starting Open-LLM-VTuber main server..." -ForegroundColor Yellow

if (-not (Clear-Port -Port 12393 -Force $ForceKill)) { exit 1 }

# 单行命令:先修 PATH 再启 uv;用单引号防 PowerShell 过早展开 $env:Path
$olvCmd = "`$env:Path = '{0};' + `$env:Path ; uv run run_server.py" -f $UvPath
Start-In-NewWindow -Title "OLV Server" -WorkingDir $OlvDir -Command $olvCmd

Write-Host ("  Waiting for OLV to bind :12393 (timeout {0}s, faster-whisper first run can be slow)..." -f $OlvTimeout) -ForegroundColor Gray
$olvReady = Wait-Port -Port 12393 -TimeoutSec $OlvTimeout -Name "OLV"
if (-not $olvReady) {
    Write-Error "  OLV failed to start within timeout. Check the OLV Server window for errors."
    exit 1
}

# ---- Step 3: Mail daemon (optional) ----

if ($SkipMailDaemon) {
    Write-Host "[3/3] Skipping mail daemon (-SkipMailDaemon)." -ForegroundColor DarkGray
} elseif (-not (Test-Path $MailConfig)) {
    Write-Host "[3/3] Skipping mail daemon (mail_config.json not found)." -ForegroundColor DarkGray
    Write-Host "      Copy mail_config.example.json to mail_config.json to enable." -ForegroundColor DarkGray
} else {
    Write-Host "[3/3] Starting mail daemon..." -ForegroundColor Yellow
    Start-In-NewWindow -Title "Mail Daemon" -WorkingDir $ProjectRoot -Command "python -m mcp_servers.mail_server.daemon"
}

# ---- Step 4: open browser (optional) ----

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " All services launched." -ForegroundColor Green
Write-Host " - SoVITS API : http://127.0.0.1:9880   ($(if ($SkipSovits) { 'SKIPPED' } else { 'RUNNING' }))" -ForegroundColor Cyan
Write-Host " - OLV server : http://localhost:12393  (RUNNING)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

if (-not $NoBrowser -and $olvReady) {
    Write-Host "Opening browser..." -ForegroundColor Cyan
    Start-Process "http://localhost:12393"
}

Write-Host "To stop all services later: .\scripts\stop-all.ps1" -ForegroundColor DarkGray
