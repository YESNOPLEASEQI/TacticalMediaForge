"""Offline media-integrity regressions from the full-agent audit."""

from pathlib import Path

import ffmpeg
import pytest

from military_video_gen.services.video import VideoService
from military_video_gen.utils.media_validation import probe_media_file


def test_single_video_with_bgm_still_enters_mix_path(tmp_path, monkeypatch) -> None:
    source = tmp_path / "scene.mp4"
    source.write_bytes(b"synthetic-scene")
    output = tmp_path / "final.mp4"
    bgm = tmp_path / "music.mp3"
    bgm.write_bytes(b"synthetic-audio")
    service = VideoService()
    monkeypatch.setattr(service, "_ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(
        service,
        "_get_unique_temp_path",
        lambda *_args: str(tmp_path / "without-bgm.mp4"),
    )
    calls = []

    def fake_mix(*, video, bgm_path, output, volume, mode):
        calls.append((video, bgm_path, volume, mode))
        Path(output).write_bytes(b"mixed")
        return output

    monkeypatch.setattr(service, "_add_bgm_to_video", fake_mix)

    assert service.concat_videos([str(source)], str(output), bgm_path=str(bgm)) == str(output)
    assert calls and calls[0][1] == str(bgm)  # S55
    assert not (tmp_path / "without-bgm.mp4").exists()


def test_real_ffmpeg_output_passes_final_media_contract(tmp_path) -> None:
    output = tmp_path / "完整 成品.mp4"
    video = ffmpeg.input("color=c=black:s=64x64:r=10:d=0.4", f="lavfi")
    audio = ffmpeg.input("sine=frequency=440:duration=0.4", f="lavfi")
    (
        ffmpeg.output(
            video.video,
            audio.audio,
            str(output),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            shortest=None,
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )

    duration = probe_media_file(output, require_audio=True)
    assert 0.2 <= duration <= 1.0  # S56


def test_corrupt_nonempty_mp4_fails_final_media_contract(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not-an-mp4")
    with pytest.raises(ValueError, match="cannot be decoded"):
        probe_media_file(corrupt, require_audio=True)  # S57
