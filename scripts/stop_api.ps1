param(
    [int]$Port = 8000
)

$listener = Get-NetTCPConnection `
    -State Listen `
    -LocalPort $Port `
    -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $listener) {
    exit 0
}

$listenerPid = [int]$listener.OwningProcess
$targetPid = $listenerPid
$current = Get-CimInstance Win32_Process `
    -Filter "ProcessId=$listenerPid" `
    -ErrorAction SilentlyContinue

# `uv run python ...` creates a process chain on Windows. Killing only the
# listening Python child can fail or leave its uv parent alive, so terminate
# the uv subtree that owns the listener.
while ($current) {
    if ($current.Name -ieq "uv.exe") {
        $targetPid = [int]$current.ProcessId
        break
    }
    if (-not $current.ParentProcessId) {
        break
    }
    $current = Get-CimInstance Win32_Process `
        -Filter "ProcessId=$($current.ParentProcessId)" `
        -ErrorAction SilentlyContinue
}

Write-Host "Stopping backend process tree $targetPid (listener $listenerPid)..."
$taskkillOutput = & taskkill.exe /PID $targetPid /T /F 2>&1
if ($LASTEXITCODE -ne 0) {
    $taskkillOutput | Write-Error
    Write-Error (
        "Backend could not be stopped. If its window title starts with " +
        "'Administrator:', close that window manually and retry."
    )
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
