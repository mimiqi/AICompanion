<#
.SYNOPSIS
    停止所有由 start-all.ps1 启动的进程

.DESCRIPTION
    终止匹配以下命令行的 python.exe / pythonw.exe 进程:
      - run_server.py                  (OLV 主进程,uv run 启动)
      - api_v2.py                      (GPT-SoVITS,通常由 runtime\python.exe 启动)
      - mcp_servers.mail_server.daemon (邮件守护)

    备注:
    - GPT-SoVITS 整合包用 .\runtime\python.exe api_v2.py 启动,
      但子进程名仍为 python.exe,所以下方按 cmdline 模式匹配照样命中。
    - OLV 启动的 MCP 子进程 (time / todo) 会随主进程一起退出。
    - 不会触碰其他 python 进程 (如 SoVITS WebUI、Jupyter 等),只杀命中模式的。
#>

[CmdletBinding()]
param()

$patterns = @(
    'run_server\.py',
    'api_v2\.py',
    'mcp_servers\.mail_server\.daemon'
)

$killed = 0
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    ForEach-Object {
        $cmdline = $_.CommandLine
        if (-not $cmdline) { return }
        foreach ($pat in $patterns) {
            if ($cmdline -match $pat) {
                Write-Host ("Stopping pid " + $_.ProcessId + " - " + $cmdline.Substring(0, [Math]::Min(100, $cmdline.Length))) -ForegroundColor Yellow
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                $killed++
                break
            }
        }
    }

Write-Host ""
Write-Host ("Done. " + $killed + " process(es) stopped.") -ForegroundColor Green
