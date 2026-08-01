"""Remove retired prompt strings from persisted output JSON artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from military_video_gen.prompts.legacy_contract import (
    LEGACY_PROMPT_FRAGMENTS,
    scrub_legacy_prompt_payload,
)


def _legacy_quoted_string_pattern() -> re.Pattern[str]:
    fragments = "|".join(re.escape(item) for item in LEGACY_PROMPT_FRAGMENTS)
    return re.compile(
        rf'"(?:[^"\\]|\\.)*(?:{fragments})(?:[^"\\]|\\.)*"',
        flags=re.IGNORECASE,
    )


def clean_artifacts(root: Path) -> tuple[int, int]:
    changed_files = 0
    removed_strings = 0
    quoted_pattern = _legacy_quoted_string_pattern()
    for path in sorted(root.rglob("*.json")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(fragment in text.casefold() for fragment in LEGACY_PROMPT_FRAGMENTS):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            cleaned, count = quoted_pattern.subn('""', text)
        else:
            payload, count = scrub_legacy_prompt_payload(payload)
            cleaned = json.dumps(payload, ensure_ascii=False, indent=2)
        if count:
            path.write_text(cleaned, encoding="utf-8")
            changed_files += 1
            removed_strings += count
    return changed_files, removed_strings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("output"))
    args = parser.parse_args()
    files, strings = clean_artifacts(args.root.resolve())
    print(json.dumps({"changed_files": files, "removed_strings": strings}))


if __name__ == "__main__":
    main()
