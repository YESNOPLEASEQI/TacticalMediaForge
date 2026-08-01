import asyncio
from pathlib import Path

from military_video_gen.services.frame_html import HTMLFrameGenerator
from military_video_gen.services.video import VideoService
from military_video_gen.utils.subtitles import build_subtitle_cues
from military_video_gen.utils.template_util import resolve_template_path


TASK_DIR = Path("output/20260728_135256_1437")
FRAMES_DIR = TASK_DIR / "frames"
NARRATION = "F-16由洛克希德·马丁制造，首架生产型于1978年交付。"
DURATION = 5.616


async def main() -> None:
    cues = build_subtitle_cues(NARRATION, DURATION)
    generator = HTMLFrameGenerator(
        resolve_template_path("1080x1080/image_minimal_framed.html")
    )
    rendered = []
    for index, cue in enumerate(cues, start=1):
        output = FRAMES_DIR / f"01_composed_{index:02d}.png"
        await generator.generate_frame(
            title="F-16基础科普",
            text=cue.text,
            image=str(FRAMES_DIR / "01_image.png"),
            ext={"hide_branding": True},
            output_path=str(output),
        )
        rendered.append((str(output), cue.end - cue.start))

    await HTMLFrameGenerator.close_browser()
    VideoService().create_video_from_timed_images(
        images=rendered,
        audio=str(FRAMES_DIR / "01_audio.mp3"),
        output=str(FRAMES_DIR / "01_segment.mp4"),
        fps=15,
    )


if __name__ == "__main__":
    asyncio.run(main())
