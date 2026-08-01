from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from api.config import APIConfig
from api.routers.files import get_file


def test_api_defaults_to_loopback_and_local_frontend_origins() -> None:
    config = APIConfig()

    assert config.host == "127.0.0.1"
    assert "*" not in config.cors_origins
    assert config.cors_origins == [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


@pytest.mark.asyncio
async def test_file_endpoint_serves_files_inside_allowed_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    video = output / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.chdir(tmp_path)

    response = await get_file("video.mp4")

    assert isinstance(response, FileResponse)
    assert Path(response.path) == video


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested_path",
    [
        "../config.yaml",
        "output/../config.yaml",
        "templates/../../config.yaml",
    ],
)
async def test_file_endpoint_rejects_directory_traversal(
    monkeypatch,
    tmp_path: Path,
    requested_path: str,
) -> None:
    (tmp_path / "output").mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "config.yaml").write_text("api_key: secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HTTPException) as raised:
        await get_file(requested_path)

    assert raised.value.status_code == 403
