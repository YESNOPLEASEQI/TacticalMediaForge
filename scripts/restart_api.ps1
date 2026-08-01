param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$stopScript = Join-Path $PSScriptRoot "stop_api.ps1"
$runScript = Join-Path $PSScriptRoot "run_api.ps1"

& $stopScript -Port $Port

$deadline = [DateTime]::UtcNow.AddSeconds(20)
while ([DateTime]::UtcNow -lt $deadline) {
    $listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue
    if (-not $listener) { break }
    Start-Sleep -Milliseconds 250
}

if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "Could not stop the existing API on port $Port"
}

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $runScript,
        "-ListenAddress", "127.0.0.1",
        "-Port", $Port
    ) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden
