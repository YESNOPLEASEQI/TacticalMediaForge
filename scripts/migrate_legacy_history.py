"""Import ``output/{task_id}`` JSON history into the relational database."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from military_video_gen.database.history_sync import HistoryDatabaseSync
from military_video_gen.database.session import AsyncSessionFactory, create_session_factory


async def migrate_legacy_history(
    output_dir: Path,
    database_sync: HistoryDatabaseSync,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    stats = {"scanned": 0, "imported": 0, "skipped": 0, "failed": 0}
    if not output_dir.exists():
        logger.warning(f"Legacy output directory does not exist: {output_dir}")
        return stats

    for metadata_path in sorted(output_dir.glob("*/metadata.json")):
        stats["scanned"] += 1
        task_dir = metadata_path.parent
        try:
            metadata: Any = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("metadata.json root must be an object")
            storyboard = None
            storyboard_path = task_dir / "storyboard.json"
            if storyboard_path.exists():
                storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
                if not isinstance(storyboard, dict):
                    raise ValueError("storyboard.json root must be an object")
            task_id = str(metadata.get("task_id") or task_dir.name)
            if dry_run:
                stats["skipped"] += 1
                continue
            await database_sync.sync_task(
                task_id,
                metadata,
                storyboard,
                event_type="legacy.imported",
            )
            stats["imported"] += 1
        except Exception as exc:
            stats["failed"] += 1
            logger.exception(f"Failed to import legacy history {task_dir.name}: {exc}")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--database-url")
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def async_main(args: argparse.Namespace) -> int:
    factory = (
        create_session_factory(args.database_url)
        if args.database_url
        else AsyncSessionFactory
    )
    try:
        stats = await migrate_legacy_history(
            args.output_dir,
            HistoryDatabaseSync(factory),
            dry_run=args.dry_run,
        )
    finally:
        if args.database_url:
            await factory.kw["bind"].dispose()
    print(json.dumps(stats, ensure_ascii=False))
    return 1 if stats["failed"] else 0


def main() -> int:
    return asyncio.run(async_main(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
