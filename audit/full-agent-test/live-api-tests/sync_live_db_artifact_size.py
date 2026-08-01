"""Synchronize the repaired live-E2E artifact size into its persisted records."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "military_video_gen.db"
VIDEO_PATH = ROOT / "output" / "20260728_135256_1437" / "final.mp4"
PROJECT_ID = "1b07c106-eaf4-4ac2-8bbe-73769330f869"
JOB_IDS = (
    "ce092b1a-8f41-448a-98db-9787cd9a04fb",
    "54c728ec-e3ac-575d-95e5-18ff819c7e77",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    size = VIDEO_PATH.stat().st_size
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in JOB_IDS)

    jobs = connection.execute(
        f"SELECT id, status, result_json FROM generation_jobs WHERE id IN ({placeholders})",
        JOB_IDS,
    ).fetchall()
    assets = connection.execute(
        "SELECT id, job_id, local_path, size_bytes FROM assets WHERE project_id = ? "
        "AND local_path LIKE ?",
        (PROJECT_ID, "%20260728_135256_1437%"),
    ).fetchall()
    outputs = connection.execute(
        "SELECT id, generation_job_id, status, duration, video_asset_id "
        "FROM output_versions WHERE project_id = ?",
        (PROJECT_ID,),
    ).fetchall()
    scripts = connection.execute(
        "SELECT id, version_no, status, full_text, source, model_name, metadata_json "
        "FROM script_versions WHERE project_id = ? ORDER BY version_no",
        (PROJECT_ID,),
    ).fetchall()
    storyboards = connection.execute(
        "SELECT id, script_version_id, version_no, status, scene_count, metadata_json "
        "FROM storyboard_versions WHERE project_id = ? ORDER BY version_no",
        (PROJECT_ID,),
    ).fetchall()

    print(json.dumps({
        "video_size": size,
        "jobs": [dict(row) for row in jobs],
        "assets": [dict(row) for row in assets],
        "outputs": [dict(row) for row in outputs],
        "scripts": [dict(row) for row in scripts],
        "storyboards": [dict(row) for row in storyboards],
    }, ensure_ascii=False, indent=2))

    if not args.apply:
        connection.close()
        return

    if {row["id"] for row in jobs} != set(JOB_IDS):
        raise RuntimeError("Expected live generation job records were not found")

    with connection:
        for row in jobs:
            result = json.loads(row["result_json"])
            result["file_size"] = size
            connection.execute(
                "UPDATE generation_jobs SET result_json = ? WHERE id = ?",
                (json.dumps(result, ensure_ascii=False), row["id"]),
            )
        for asset in assets:
            asset_path = Path(asset["local_path"]).resolve()
            if ROOT not in asset_path.parents or not asset_path.is_file():
                raise RuntimeError(f"Unsafe or missing asset path: {asset_path}")
            connection.execute(
                "UPDATE assets SET size_bytes = ? WHERE id = ?",
                (asset_path.stat().st_size, asset["id"]),
            )
    connection.close()
    print(f"Synchronized {len(jobs)} jobs and {len(assets)} assets to {size} bytes")


if __name__ == "__main__":
    main()
