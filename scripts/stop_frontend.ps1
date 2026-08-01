param(
    [int]$Port = 5173
)

$listener = Get-NetTCPConnection `
    -State Listen `
    -LocalPort $Port `
    -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $listener) {
    exit 0
}

$listenerPid = [int]$listener.OwningProcess
$listenerProcess = Get-CimInstance Win32_Process `
    -Filter "ProcessId=$listenerPid" `
    -ErrorAction SilentlyContinue
$frontendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\frontend")).Path

if (
    -not $listenerProcess `
    -or $listenerProcess.Name -ine "node.exe" `
    -or $listenerProcess.CommandLine -notlike "*vite*" `
    -or $listenerProcess.CommandLine -notlike "*$frontendRoot*"
) {
    Write-Error (
        "Port $Port is occupied by a process that is not this project's Vite server. " +
        "Refusing to stop PID $listenerPid."
    )
    exit 1
}

$targetPid = $listenerPid
$current = $listenerProcess
while ($current -and $current.ParentProcessId) {
    $parent = Get-CimInstance Win32_Process `
        -Filter "ProcessId=$($current.ParentProcessId)" `
        -ErrorAction SilentlyContinue
    if (-not $parent) {
        break
    }
    if (
        $parent.Name -ieq "cmd.exe" `
        -and $parent.CommandLine -like "*npm run dev*" `
        -and $parent.CommandLine -like "*frontend*"
    ) {
        $targetPid = [int]$parent.ProcessId
        break
    }
    $current = $parent
}

Write-Host "Stopping frontend process tree $targetPid (listener $listenerPid)..."
$taskkillOutput = & taskkill.exe /PID $targetPid /T /F 2>&1
if ($LASTEXITCODE -ne 0) {
    $taskkillOutput | Write-Error
    Write-Error "Frontend could not be stopped. Close its terminal window manually and retry."
    exit 1
}

for ($attempt = 0; $attempt -lt 50; $attempt++) {
    if (-not (Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue)) {
        exit 0
    }
    Start-Sleep -Milliseconds 200
}

Write-Error "Port $Port is still occupied after stopping process tree $targetPid."
exit 1
