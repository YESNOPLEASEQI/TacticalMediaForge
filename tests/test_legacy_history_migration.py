import json

import pytest

from scripts.migrate_legacy_history import migrate_legacy_history


class RecordingSync:
    def __init__(self):
        self.calls = []

    async def sync_task(self, task_id, metadata, storyboard, **kwargs):
        self.calls.append((task_id, metadata, storyboard, kwargs))


@pytest.mark.asyncio
async def test_legacy_migration_continues_after_invalid_history(tmp_path):
    valid = tmp_path / "valid-task"
    valid.mkdir()
    (valid / "metadata.json").write_text(
        json.dumps({"task_id": "valid-task", "input": {"title": "Valid"}}),
        encoding="utf-8",
    )
    (valid / "storyboard.json").write_text(
        json.dumps({"title": "Valid", "frames": []}),
        encoding="utf-8",
    )
    broken = tmp_path / "broken-task"
    broken.mkdir()
    (broken / "metadata.json").write_text("{broken", encoding="utf-8")

    sync = RecordingSync()
    stats = await migrate_legacy_history(tmp_path, sync)

    assert stats == {"scanned": 2, "imported": 1, "skipped": 0, "failed": 1}
    assert sync.calls[0][0] == "valid-task"
    assert sync.calls[0][2]["title"] == "Valid"
    assert sync.calls[0][3]["event_type"] == "legacy.imported"


@pytest.mark.asyncio
async def test_legacy_migration_dry_run_validates_without_writing(tmp_path):
    task = tmp_path / "task-a"
    task.mkdir()
    (task / "metadata.json").write_text(json.dumps({"task_id": "task-a"}), encoding="utf-8")
    sync = RecordingSync()

    stats = await migrate_legacy_history(tmp_path, sync, dry_run=True)

    assert stats == {"scanned": 1, "imported": 0, "skipped": 1, "failed": 0}
    assert sync.calls == []
