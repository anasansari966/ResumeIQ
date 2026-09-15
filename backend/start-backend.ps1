# Start ResumeIQ API on 127.0.0.1. Frees the port first if something is still listening (e.g. stale uvicorn).
#
# Run from this folder (backend):
#   .\start-backend.ps1
# If port 8000 fails with WinError 10013 (common on Windows when the port sits in an excluded range),
# this script tries fallbacks and prints the URL to use for VITE_API_URL.
param(
    [int] $Port = 8765
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-CanBind([int] $ListenPort) {
    try {
        $l = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Parse("127.0.0.1"),
            $ListenPort
        )
        $l.Start()
        $l.Stop()
        return $true
    } catch {
        return $false
    }
}

$owningPid = $null
foreach ($line in (netstat -ano | Select-String ":$Port\s+.*LISTENING")) {
    $parts = ($line.Line -split '\s+', 0, "RemoveEmptyEntries")
    $owningPid = $parts[-1]
    break
}
if ($owningPid -and $owningPid -match '^\d+$') {
    Write-Host "Port $Port is in use by PID $owningPid — stopping it."
    taskkill /PID $owningPid /F | Out-Null
    Start-Sleep -Milliseconds 400
}

$candidates = @($Port) + @(8000, 8020, 8765, 9000) | ForEach-Object { [int]$_ } | Select-Object -Unique
$chosen = $null
foreach ($p in $candidates) {
    if (Test-CanBind $p) {
        $chosen = $p
        break
    }
}
if (-not $chosen) {
    Write-Host @"

No bindable port found among: $($candidates -join ', ').

Check Windows excluded ranges (often blocks 8000+):
  netsh interface ipv4 show excludedportrange protocol=tcp

Then either pick a port outside those ranges:
  .\start-backend.ps1 -Port 13000

Or run an elevated prompt and adjust Hyper-V / reserved ranges.
"@
    exit 1
}

if ($chosen -ne $Port) {
    Write-Warning "Port $Port is not usable (in use or blocked). Using $chosen instead."
    Write-Host "Set frontend VITE_API_URL=http://127.0.0.1:$chosen" -ForegroundColor Cyan
}

$Port = $chosen
Write-Host "Starting API at http://127.0.0.1:$Port (reload on)" -ForegroundColor Green

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
