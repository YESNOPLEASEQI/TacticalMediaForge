"""Align the persisted UI draft with the completed verified live-E2E job."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = "1b07c106-eaf4-4ac2-8bbe-73769330f869"
RESEARCH_JOB_ID = "9f694887-3222-4ae0-bea4-cd017d795c24"
VIDEO_JOB_IDS = {
    "ce092b1a-8f41-448a-98db-9787cd9a04fb",
    "54c728ec-e3ac-575d-95e5-18ff819c7e77",
    "5fcf3798-c2c6-4a8f-8c10-291ed06b0283",
}
NARRATION = "F-16由洛克希德·马丁制造，首架生产型于1978年交付。"


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    project = request_json(f"{BASE_URL}/projects/{PROJECT_ID}")
    research_job = request_json(f"{BASE_URL}/jobs/{RESEARCH_JOB_ID}")
    snapshot = research_job["result_json"]
    request_payload = json.loads(
        open("audit/full-agent-test/live-api-tests/live-video-request.json", encoding="utf-8").read()
    )
    settings = dict(project.get("settings_json") or {})
    draft = dict(settings.get("workspace_draft") or {})
    source_scene = request_payload["confirmed_storyboard"][0]
    scenes = [{
        "id": "scene-1",
        "index": source_scene["index"],
        "narration": source_scene["narration"],
        "visualDescription": source_scene["visual_description"],
        "mediaPrompt": source_scene["media_prompt"],
        "estimatedDuration": source_scene["estimated_duration"],
        "assetType": source_scene["asset_type"],
        "status": "completed",
        "researchJobId": source_scene["research_job_id"],
        "subjectId": source_scene["subject_id"],
        "claimIds": source_scene["claim_ids"],
        "visualFactIds": source_scene["visual_fact_ids"],
        "fieldProvenance": source_scene["field_provenance"],
        "fallbackLevel": source_scene["fallback_level"],
        "verificationStatus": source_scene["verification_status"],
        "negativeConstraints": source_scene["negative_constraints"],
        "warnings": source_scene["warnings"],
    }]
    draft.update(
        {
            "sessionId": PROJECT_ID,
            "stage": "video",
            "title": "F-16基础科普",
            "narrations": [NARRATION],
            "scriptConfirmed": True,
            "scriptMode": "reference",
            "storyboard": scenes,
            "storyboardConfirmed": True,
            "contentRevision": 2,
            "submittedRevision": 1,
            "research": {
                "mode": "verified",
                "activeJobId": RESEARCH_JOB_ID,
                "inputHash": snapshot["input_hash"],
                "scriptRevision": snapshot["script_revision"],
                "status": snapshot["research_status"],
                "sourceCount": len(snapshot["sources"]),
                "sources": snapshot["sources"],
                "warnings": snapshot["warnings"],
                "stale": False,
            },
            "config": {
                "nScenes": 1,
                "frameTemplate": "1080x1080/image_minimal_framed.html",
                "mediaWorkflow": "selfhost/image_flux.json",
                "bgmEnabled": False,
                "bgmPath": "",
                "bgmVolume": 0.0,
            },
            "appliedJobIds": sorted(set(draft.get("appliedJobIds") or []) | VIDEO_JOB_IDS),
        }
    )
    settings["active_research_job_id"] = RESEARCH_JOB_ID
    settings["workspace_draft"] = draft
    settings["workspace_draft_updated_at"] = datetime.now(timezone.utc).isoformat()

    updated = request_json(
        f"{BASE_URL}/projects/{PROJECT_ID}",
        method="PATCH",
        payload={
            "title": "F-16基础科普",
            "source_text": NARRATION,
            "current_stage": "output",
            "status": "completed",
            "settings_json": settings,
        },
    )
    saved = updated["settings_json"]["workspace_draft"]
    print(json.dumps({
        "project_status": updated["status"],
        "current_stage": updated["current_stage"],
        "title": updated["title"],
        "narrations": saved["narrations"],
        "storyboard_confirmed": saved["storyboardConfirmed"],
        "scene_status": saved["storyboard"][0]["status"],
        "research_job_id": saved["storyboard"][0]["researchJobId"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
