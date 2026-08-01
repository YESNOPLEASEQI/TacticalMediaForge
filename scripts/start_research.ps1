param(
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot "data\logs"
$stdoutLog = Join-Path $logDirectory "research-compose.out.log"
$stderrLog = Join-Path $logDirectory "research-compose.err.log"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

# Run Compose synchronously so Windows PowerShell records the native exit code
# in $LASTEXITCODE. Start-Process can leave Process.ExitCode as $null when its
# output is redirected, even after WaitForExit(), producing "code .".
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    & docker.exe compose --profile research up -d --force-recreate searxng crawl4ai `
        1> $stdoutLog 2> $stderrLog
    $composeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($composeExitCode -ne 0) {
    Write-Host "[ERROR] Docker Compose exited with code $composeExitCode."
    if (Test-Path $stderrLog) { Get-Content $stderrLog -Tail 80 }
    exit $composeExitCode
}

function Invoke-CurlProbe {
    param([string[]]$Arguments)

    # A service that is still booting normally makes curl write to stderr.
    # Windows PowerShell can promote that stderr record to a terminating
    # NativeCommandError when the script-wide preference is "Stop", which
    # would bypass the readiness retry loop entirely.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & curl.exe @Arguments 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Test-ResearchServices {
    $searxArguments = @("-fsS", "--max-time", "2", "http://127.0.0.1:8080/healthz")
    if (-not (Invoke-CurlProbe -Arguments $searxArguments)) {
        return $false
    }

    $crawlArguments = @(
        "-fsS",
        "--max-time", "2",
        "-H", "Authorization: Bearer $env:CRAWL4AI_API_TOKEN",
        "http://127.0.0.1:12135/health"
    )
    return (Invoke-CurlProbe -Arguments $crawlArguments)
}

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-ResearchServices) {
        Write-Host "Research services are ready."
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Host "[ERROR] Research services did not become ready within $TimeoutSeconds seconds."
if (Test-Path $stdoutLog) { Get-Content $stdoutLog -Tail 40 }
if (Test-Path $stderrLog) { Get-Content $stderrLog -Tail 80 }
exit 1
