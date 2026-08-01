import json
from pathlib import Path

import yaml
from comfykit.comfyui.workflow_parser import WorkflowParser

DEFAULT_VIDEO_WORKFLOW = "selfhost/video_ltx2_3_t2v.json"


def test_example_config_uses_ltx_2_3_as_default_video_workflow():
    config = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))

    assert config["comfyui"]["video"]["default_workflow"] == DEFAULT_VIDEO_WORKFLOW


def test_default_ltx_2_3_workflow_is_executable_and_accepts_project_parameters():
    workflow_path = Path("workflows") / DEFAULT_VIDEO_WORKFLOW
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    metadata = WorkflowParser().parse_workflow(workflow, workflow_path.stem)

    assert workflow
    assert all("class_type" in node and "inputs" in node for node in workflow.values())
    assert {"prompt", "width", "height", "duration", "seed"} <= set(metadata.params)
    assert metadata.mapping_info.output_mappings
