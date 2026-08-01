@echo off
setlocal
set "FRONTEND_PORT=5273"

cd /d "%~dp0"

echo Starting MilitaryVideoGen stack...
echo Project: %CD%
echo.

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv is not available in PATH.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm is not available in PATH.
    pause
    exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Docker CLI is not available in PATH.
    echo Install or repair Docker Desktop, then run this script again.
    pause
    exit /b 1
)

if not exist "api\app.py" (
    echo [ERROR] api\app.py not found.
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo [ERROR] frontend\package.json not found.
    pause
    exit /b 1
)

echo Checking local configuration...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "from pathlib import Path; import yaml; value=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8')); raise SystemExit(0 if isinstance(value, dict) and value.get('research', {}).get('enabled') is True else 1)"
) else (
    uv run python -c "from pathlib import Path; import yaml; value=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8')); raise SystemExit(0 if isinstance(value, dict) and value.get('research', {}).get('enabled') is True else 1)"
)
if errorlevel 1 (
    echo [ERROR] config.yaml is invalid or research.enabled is not true.
    pause
    exit /b 1
)

set "CRAWL4AI_API_TOKEN="
set "SEARXNG_SECRET="
if exist ".env" (
    for /f "tokens=1,* delims==" %%A in (.env) do (
        if /i "%%A"=="CRAWL4AI_API_TOKEN" set "CRAWL4AI_API_TOKEN=%%B"
        if /i "%%A"=="SEARXNG_SECRET" set "SEARXNG_SECRET=%%B"
    )
)

rem Older launchers could concatenate repeated assignments onto the Crawl4AI
rem token. Treat that value as corrupt so the generator below rotates it and
rem rewrites the malformed line instead of preserving the corruption.
if defined CRAWL4AI_API_TOKEN (
    if not "%CRAWL4AI_API_TOKEN:SEARXNG_SECRET=%"=="%CRAWL4AI_API_TOKEN%" set "CRAWL4AI_API_TOKEN="
)

if not defined CRAWL4AI_API_TOKEN (
    echo Creating a local Crawl4AI token in .env...
    powershell -NoProfile -Command "$p='.env'; $bytes=New-Object byte[] 32; $rng=[Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($bytes); $rng.Dispose(); $token=[Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','').Replace('/',''); $lines=if(Test-Path -LiteralPath $p){@(Get-Content -LiteralPath $p)}else{@()}; if($lines -match '^CRAWL4AI_API_TOKEN='){$lines=@($lines | ForEach-Object {if($_ -match '^CRAWL4AI_API_TOKEN='){'CRAWL4AI_API_TOKEN='+$token}else{$_}})}else{$lines=@($lines)+('CRAWL4AI_API_TOKEN='+$token)}; Set-Content -LiteralPath $p -Value $lines -Encoding ASCII"
    if errorlevel 1 (
        echo [ERROR] Failed to create .env.
        pause
        exit /b 1
    )
    for /f "tokens=1,* delims==" %%A in (.env) do (
        if /i "%%A"=="CRAWL4AI_API_TOKEN" set "CRAWL4AI_API_TOKEN=%%B"
    )
)

if not defined SEARXNG_SECRET (
    echo Creating a local SearXNG secret in .env...
    powershell -NoProfile -Command "$p='.env'; $bytes=New-Object byte[] 32; $rng=[Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($bytes); $rng.Dispose(); $secret=[Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','').Replace('/',''); $lines=if(Test-Path -LiteralPath $p){@(Get-Content -LiteralPath $p)}else{@()}; if($lines -match '^SEARXNG_SECRET='){$lines=@($lines | ForEach-Object {if($_ -match '^SEARXNG_SECRET='){'SEARXNG_SECRET='+$secret}else{$_}})}else{$lines=@($lines)+('SEARXNG_SECRET='+$secret)}; Set-Content -LiteralPath $p -Value $lines -Encoding ASCII"
    if errorlevel 1 (
        echo [ERROR] Failed to create the SearXNG secret in .env.
        pause
        exit /b 1
    )
    for /f "tokens=1,* delims==" %%A in (.env) do (
        if /i "%%A"=="SEARXNG_SECRET" set "SEARXNG_SECRET=%%B"
    )
)

set "SEARXNG_BASE_URL=http://127.0.0.1:8080"
set "CRAWL4AI_BASE_URL=http://127.0.0.1:12135"

docker info >nul 2>nul
if errorlevel 1 (
    if not exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        echo [ERROR] Docker Desktop is not installed in the default location.
        pause
        exit /b 1
    )
    echo Starting Docker Desktop...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    call :wait_for_docker
    if errorlevel 1 (
        echo [ERROR] Docker Desktop did not become ready within 120 seconds.
        pause
        exit /b 1
    )
)

call :research_is_healthy
if errorlevel 1 (
    echo Starting SearXNG and Crawl4AI...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_research.ps1" -TimeoutSeconds 90
    if errorlevel 1 (
        echo [ERROR] Failed to start research containers.
        pause
        exit /b 1
    )

    echo Waiting for research services...
    call :wait_for_research
    if errorlevel 1 (
        echo [ERROR] Research services did not become healthy within 120 seconds.
        docker compose --profile research ps
        pause
        exit /b 1
    )
) else (
    echo Research services are already ready.
)

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
    popd
)

call :port_is_listening 8000
if not errorlevel 1 (
    echo Backend process detected; restarting it to load the current code...
    call :stop_backend
    if errorlevel 1 (
        echo [ERROR] The existing backend could not be stopped.
        echo Close the existing MilitaryVideoGen - API window, then run this script again.
        pause
        exit /b 1
    )
)
echo Opening backend window: http://127.0.0.1:8000
start "MilitaryVideoGen - API" powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0scripts\run_api.ps1" -ListenAddress 127.0.0.1 -Port 8000

echo Waiting for backend API...
call :wait_for_api
if errorlevel 1 (
    echo [ERROR] Backend API did not become healthy within 90 seconds.
    echo Check the MilitaryVideoGen - API window for the startup error.
    pause
    exit /b 1
)

call :port_is_listening %FRONTEND_PORT%
if not errorlevel 1 (
    echo Frontend process detected; restarting it to load the current code and Tailwind configuration...
    call :stop_frontend
    if errorlevel 1 (
        echo [ERROR] The existing frontend could not be stopped safely.
        echo Close the existing MilitaryVideoGen - Frontend window, then run this script again.
        pause
        exit /b 1
    )
)
echo Opening frontend window: http://127.0.0.1:%FRONTEND_PORT%
start "MilitaryVideoGen - Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

echo Waiting for frontend...
call :wait_for_frontend
if errorlevel 1 (
    echo [ERROR] Frontend did not become ready within 60 seconds.
    pause
    exit /b 1
)
start "" "http://127.0.0.1:%FRONTEND_PORT%/"

echo.
echo Started. Keep the two terminal windows open while using the app.
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%/
echo Backend:  http://127.0.0.1:8000/health
echo Research: http://127.0.0.1:8000/api/content/research/diagnostics
echo.
pause
exit /b 0

:wait_for_docker
for /l %%I in (1,1,60) do (
    docker info >nul 2>nul
    if not errorlevel 1 exit /b 0
    timeout /t 2 /nobreak >nul
)
exit /b 1

:wait_for_research
for /l %%I in (1,1,60) do (
    curl.exe -fsS "http://127.0.0.1:8080/healthz" >nul 2>nul
    if not errorlevel 1 (
        curl.exe -fsS -H "Authorization: Bearer %CRAWL4AI_API_TOKEN%" "http://127.0.0.1:12135/health" >nul 2>nul
        if not errorlevel 1 exit /b 0
    )
    timeout /t 2 /nobreak >nul
)
exit /b 1

:research_is_healthy
curl.exe -fsS "http://127.0.0.1:8080/healthz" >nul 2>nul
if errorlevel 1 exit /b 1
curl.exe -fsS -H "Authorization: Bearer %CRAWL4AI_API_TOKEN%" "http://127.0.0.1:12135/health" >nul 2>nul
exit /b %errorlevel%

:wait_for_api
for /l %%I in (1,1,45) do (
    call :api_has_research
    if not errorlevel 1 exit /b 0
    timeout /t 2 /nobreak >nul
)
exit /b 1

:wait_for_frontend
for /l %%I in (1,1,30) do (
    call :frontend_is_ready
    if not errorlevel 1 exit /b 0
    timeout /t 2 /nobreak >nul
)
exit /b 1

:frontend_is_ready
curl.exe --max-time 2 -fsS "http://127.0.0.1:%FRONTEND_PORT%/" >nul 2>nul
exit /b %errorlevel%

:port_is_listening
powershell -NoProfile -Command "if(Get-NetTCPConnection -State Listen -LocalPort %1 -ErrorAction SilentlyContinue){exit 0}else{exit 1}" >nul 2>nul
exit /b %errorlevel%

:api_has_research
powershell -NoProfile -Command "try{$health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if($health.service -eq 'MilitaryVideoGen API' -and $health.research_enabled -eq $true -and $health.runtime_contract -eq 'english-storyboard-v2'){exit 0}}catch{}; exit 1" >nul 2>nul
exit /b %errorlevel%

:stop_backend
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_api.ps1" -Port 8000
exit /b %errorlevel%

:stop_frontend
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_frontend.ps1" -Port %FRONTEND_PORT%
exit /b %errorlevel%
