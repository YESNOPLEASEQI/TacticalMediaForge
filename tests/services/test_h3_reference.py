import json

from military_video_gen.services.frame_processor import (
    build_h3_reference_prompt,
    normalize_h3_video_duration,
)
from military_video_gen.services.media import MediaService


def test_h3_prompt_marks_references_as_identity_not_first_frame():
    prompt = build_h3_reference_prompt("A tracked vehicle turns through dust.", 2)

    assert "<Picture 1>" in prompt
    assert "<Picture 2>" in prompt
    assert "identity and structure references" in prompt
    assert "not first frames" in prompt
    assert "SHOT:\nA tracked vehicle turns through dust." in prompt


def test_h3_duration_is_clamped_to_supported_range():
    assert normalize_h3_video_duration(2.1) == 5
    assert normalize_h3_video_duration(7.2) == 8
    assert normalize_h3_video_duration(18.0) == 15


def test_h3_workflow_binds_only_selected_reference_images(tmp_path, monkeypatch):
    source = tmp_path / "workflow.json"
    source.write_text(
        json.dumps(
            {
                "reference_image_0": {
                    "class_type": "LoadImage",
                    "inputs": {},
                },
                "reference_image_1": {
                    "class_type": "LoadImage",
                    "inputs": {},
                },
                "h3": {
                    "class_type": "MiniMaxH3ReferenceToVideo",
                    "inputs": {
                        "ref_images.ref_image_0": ["reference_image_0", 0],
                        "ref_images.ref_image_1": ["reference_image_1", 0],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MILITARY_VIDEO_GEN_ROOT", str(tmp_path / "root"))

    prepared = MediaService._prepare_h3_reference_workflow(str(source), ["/safe/one.png"])
    try:
        workflow = json.loads(prepared.read_text(encoding="utf-8"))
        assert "reference_image_0" in workflow
        assert "reference_image_1" not in workflow
        assert "ref_images.ref_image_0" in workflow["h3"]["inputs"]
        assert "ref_images.ref_image_1" not in workflow["h3"]["inputs"]
        assert "first_frame" not in json.dumps(workflow)
    finally:
        prepared.unlink(missing_ok=True)
