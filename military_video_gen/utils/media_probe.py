"""Bounded media metadata probes.

Some generated MP3 files do not contain a complete metadata index. An
unbounded ffprobe call can then wait indefinitely while a video job appears
stuck. Keep probing isolated here so every caller shares the same safeguards.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from typing import Optional


def probe_duration(path: str, *, timeout_seconds: float = 8.0) -> Optional[float]:
    """Return a media duration, or ``None`` when probing is unavailable."""

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None

    command = [
        ffprobe,
        "-v",
        "error",
        "-read_intervals",
        "%+1",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        path,
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, ValueError):
        return None
    try:
        stdout, _ = process.communicate(timeout=timeout_seconds)
        if process.returncode != 0:
            return None
        duration = float(stdout.strip())
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        if os.name == "nt":
            # WinGet shims can leave the real ffprobe child behind after
            # Popen.kill(); terminate the small process tree as well.
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
            except subprocess.SubprocessError:
                pass
        try:
            process.communicate(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass
        return None
    except (OSError, ValueError, subprocess.SubprocessError):
        try:
            process.kill()
            process.communicate(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    if not math.isfinite(duration) or duration <= 0:
        return None
    return duration
