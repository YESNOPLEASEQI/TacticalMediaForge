from pathlib import Path
from types import SimpleNamespace

import pytest

from military_video_gen.models.storyboard import (
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
)
from military_video_gen.services.frame_processor import FrameProcessor
from military_video_gen.utils.subtitles import (
    build_subtitle_cues,
    split_subtitle_text,
)


def test_long_narration_splits_into_short_subtitle_cards() -> None:
    text = "火药燃烧后产生高压气体，推动弹丸沿炮管高速前进，最终飞出炮口。"

    chunks = split_subtitle_text(text)

    assert chunks == [
        "火药燃烧后产生高压气体，",
        "推动弹丸沿炮管高速前进，",
        "最终飞出炮口。",
    ]
    assert "".join(chunks) == text
    assert all(len(chunk) <= 16 for chunk in chunks)


def test_subtitle_cues_cover_the_whole_audio_without_gaps() -> None:
    cues = build_subtitle_cues("雷达先发射电磁波，再接收目标反射回来的信号。", 8.0)

    assert len(cues) == 2
    assert cues[0].start == 0
    assert cues[-1].end == 8.0
    assert all(left.end == right.start for left, right in zip(cues, cues[1:]))
    assert cues[0].end < cues[1].end


@pytest.mark.asyncio
async def test_frame_composition_renders_one_image_for_each_subtitle_cue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    processor = FrameProcessor(SimpleNamespace())
    frame = StoryboardFrame(
        index=0,
        narration="雷达先发射电磁波，再接收目标反射回来的信号。",
        image_prompt="prompt",
        audio_path=str(tmp_path / "audio.mp3"),
        audio_duration=8.0,
    )
    config = StoryboardConfig(media_width=1024, media_height=1024, task_id="task")
    storyboard = Storyboard(title="雷达", config=config, frames=[frame])
    rendered_texts: list[str] = []

    async def fake_compose(_frame, _storyboard, _config, output_path, subtitle_text=None):
        rendered_texts.append(subtitle_text)
        return output_path

    monkeypatch.setattr(processor, "_compose_frame_html", fake_compose)
    monkeypatch.setattr(
        "military_video_gen.utils.os_util.get_task_frame_path",
        lambda *_args: str(tmp_path / "01_composed.png"),
    )

    await processor._step_compose_frame(frame, storyboard, config)

    assert rendered_texts == ["雷达先发射电磁波，", "再接收目标反射回来的信号。"]
    assert [Path(path).name for path in frame.composed_image_paths] == [
        "01_composed_01.png",
        "01_composed_02.png",
    ]
    assert frame.composed_image_path == frame.composed_image_paths[0]


@pytest.mark.asyncio
async def test_image_scene_uses_timed_cards_without_generating_more_scenes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []

    class FakeVideoService:
        def create_video_from_timed_images(self, **kwargs):
            calls.append(kwargs)
            return kwargs["output"]

    monkeypatch.setattr(
        "military_video_gen.services.video.VideoService",
        FakeVideoService,
    )
    monkeypatch.setattr(
        "military_video_gen.utils.os_util.get_task_frame_path",
        lambda *_args: str(tmp_path / "01_segment.mp4"),
    )
    frame = StoryboardFrame(
        index=0,
        narration="雷达先发射电磁波，再接收目标反射回来的信号。",
        image_prompt="prompt",
        audio_path=str(tmp_path / "audio.mp3"),
        media_type="image",
        composed_image_path=str(tmp_path / "card-1.png"),
        composed_image_paths=[
            str(tmp_path / "card-1.png"),
            str(tmp_path / "card-2.png"),
        ],
        audio_duration=8.0,
    )
    config = StoryboardConfig(media_width=1024, media_height=1024, task_id="task")

    await FrameProcessor(SimpleNamespace())._step_create_video_segment(frame, config)

    assert len(calls) == 1
    assert [path for path, _duration in calls[0]["images"]] == frame.composed_image_paths
    assert sum(duration for _path, duration in calls[0]["images"]) == pytest.approx(8.0)
    assert frame.video_segment_path == str(tmp_path / "01_segment.mp4")
