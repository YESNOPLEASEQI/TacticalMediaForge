from pathlib import Path

import pytest
import requests

from military_video_gen.services.api_services.image_processor import ImageProcessor


def test_download_never_disables_tls_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fail_with_ssl_error(*args: object, **kwargs: object) -> None:
        calls.append(kwargs)
        raise requests.exceptions.SSLError("certificate rejected")

    monkeypatch.setattr(requests, "get", fail_with_ssl_error)

    with pytest.raises(requests.exceptions.SSLError):
        ImageProcessor().download_image(
            "https://example.invalid/image.png",
            str(tmp_path / "image.png"),
            max_retries=1,
        )

    assert len(calls) == 1
    assert calls[0]["verify"] is True
