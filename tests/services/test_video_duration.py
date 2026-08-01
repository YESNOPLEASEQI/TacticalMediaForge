import json
from pathlib import Path

from comfykit.comfyui.workflow_parser import WorkflowParser

from military_video_gen.services.frame_processor import (
    derive_video_seed,
    normalize_video_duration,
    wan_video_frame_count,
)


def test_video_target_duration_rounds_up_to_whole_seconds():
    assert normalize_video_duration(5.01) == 6
    assert normalize_video_duration(6.0) == 6
    assert normalize_video_duration(0.1) == 1


def test_wan_frame_count_covers_the_integer_duration_at_16_fps():
    assert wan_video_frame_count(6) == 97
    assert wan_video_frame_count(7) == 113


def test_video_seed_is_stable_and_unique_per_scene():
    seeds = [derive_video_seed("task-1", index) for index in range(7)]

    assert len(set(seeds)) == 7
    assert seeds == [derive_video_seed("task-1", index) for index in range(7)]
    assert derive_video_seed("task-2", 0) != seeds[0]
    assert derive_video_seed("task-1", 1, base_seed=42) == 43


def test_local_wan_workflow_exposes_video_length_parameter():
    workflow_path = Path("workflows/selfhost/video_wan2.1_fusionx.json")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    metadata = WorkflowParser().parse_workflow(workflow, workflow_path.stem)
    mappings = {
        (mapping.param_name, mapping.node_id, mapping.input_field)
        for mapping in metadata.mapping_info.param_mappings
    }

    assert ("video_length", "40", "length") in mappings
