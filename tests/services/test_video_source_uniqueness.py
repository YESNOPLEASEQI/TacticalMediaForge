from pathlib import Path

import pytest

from military_video_gen.models.storyboard import StoryboardFrame
from military_video_gen.pipelines.standard import assert_unique_generated_video_sources


def frame(index: int, path: Path) -> StoryboardFrame:
    return StoryboardFrame(
        index=index,
        narration=f"scene {index}",
        image_prompt=f"prompt {index}",
        video_path=str(path),
    )


def test_distinct_generated_video_sources_pass(tmp_path: Path) -> None:
    first = tmp_path / "01_video.mp4"
    second = tmp_path / "02_video.mp4"
    first.write_bytes(b"video-one")
    second.write_bytes(b"video-two")

    assert_unique_generated_video_sources([frame(0, first), frame(1, second)])


def test_duplicate_generated_video_sources_stop_final_timeline(tmp_path: Path) -> None:
    first = tmp_path / "01_video.mp4"
    second = tmp_path / "02_video.mp4"
    first.write_bytes(b"same-video")
    second.write_bytes(b"same-video")

    with pytest.raises(RuntimeError, match="duplicated across scenes.*1/2"):
        assert_unique_generated_video_sources([frame(0, first), frame(1, second)])
