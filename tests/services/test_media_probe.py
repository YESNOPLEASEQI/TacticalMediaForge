import subprocess
from unittest.mock import Mock, patch

from military_video_gen.utils.media_probe import probe_duration


def test_probe_duration_uses_bounded_read_and_parses_duration():
    process = type("Process", (), {"returncode": 0, "pid": 123})()
    process.communicate = Mock(return_value=("3.84\n", ""))
    with patch("military_video_gen.utils.media_probe.shutil.which", return_value="ffprobe.exe"), patch(
        "military_video_gen.utils.media_probe.subprocess.Popen", return_value=process
    ) as popen:
        assert probe_duration("sample.mp3") == 3.84

    command = popen.call_args.args[0]
    assert command[command.index("-read_intervals") + 1] == "%+1"
    assert process.communicate.call_args.kwargs["timeout"] == 8.0


def test_probe_duration_returns_none_after_probe_timeout():
    process = type("Process", (), {"pid": 123, "returncode": None})()
    process.communicate = Mock(side_effect=subprocess.TimeoutExpired("ffprobe", 3))
    process.kill = Mock()
    with patch("military_video_gen.utils.media_probe.shutil.which", return_value="ffprobe.exe"), patch(
        "military_video_gen.utils.media_probe.subprocess.Popen", return_value=process,
    ), patch(
        "military_video_gen.utils.media_probe.subprocess.run",
        return_value=type("Result", (), {})(),
    ):
        assert probe_duration("broken.mp3") is None
