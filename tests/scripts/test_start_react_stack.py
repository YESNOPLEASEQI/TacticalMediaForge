from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "start_react_stack.bat"
API_RUNNER = Path(__file__).parents[2] / "scripts" / "run_api.ps1"
API_STOPPER = Path(__file__).parents[2] / "scripts" / "stop_api.ps1"
FRONTEND_STOPPER = Path(__file__).parents[2] / "scripts" / "stop_frontend.ps1"


def test_existing_project_api_is_restarted_instead_of_reused() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    existing_api_branch = content.split("call :port_is_listening 8000", 1)[1].split(
        "call :port_is_listening %FRONTEND_PORT%", 1
    )[0]

    assert "call :stop_backend" in existing_api_branch
    assert "Backend is already listening" not in existing_api_branch
    assert "Opening backend window" in existing_api_branch
    assert ":stop_backend" in content
    assert r"scripts\stop_api.ps1" in content
    assert API_STOPPER.exists()
    assert "taskkill.exe" in API_STOPPER.read_text(encoding="utf-8")


def test_api_launcher_disables_console_quick_edit() -> None:
    batch = SCRIPT.read_text(encoding="utf-8")

    assert 'scripts\\run_api.ps1' in batch
    assert API_RUNNER.exists()
    content = API_RUNNER.read_text(encoding="utf-8")
    assert "ENABLE_QUICK_EDIT_MODE" in content
    assert "SetConsoleMode" in content
    assert "uv run python api/app.py" in content


def test_existing_project_frontend_is_restarted_instead_of_reused() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    frontend_branch = content.split("call :port_is_listening %FRONTEND_PORT%", 1)[1].split(
        "echo Waiting for frontend", 1
    )[0]

    assert "call :stop_frontend" in frontend_branch
    assert "Frontend is already listening" not in frontend_branch
    assert "Opening frontend window" in frontend_branch
    assert ":stop_frontend" in content
    assert r"scripts\stop_frontend.ps1" in content
    assert FRONTEND_STOPPER.exists()

    stopper = FRONTEND_STOPPER.read_text(encoding="utf-8")
    assert "Refusing to stop" in stopper
    assert 'Name -ine "node.exe"' in stopper
    assert 'CommandLine -notlike "*vite*"' in stopper
    assert "taskkill.exe" in stopper


def test_desktop_launchers_bind_api_to_loopback_only() -> None:
    batch = SCRIPT.read_text(encoding="utf-8")
    runner = API_RUNNER.read_text(encoding="utf-8")

    assert "-ListenAddress 127.0.0.1" in batch
    assert '[string]$ListenAddress = "127.0.0.1"' in runner
    assert "-ListenAddress 0.0.0.0" not in batch
    assert 'set "FRONTEND_PORT=5273"' in batch
