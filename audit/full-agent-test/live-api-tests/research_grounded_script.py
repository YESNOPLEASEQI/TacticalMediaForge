"""Create and monitor a verified storyboard from the grounded script job."""

from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = "1b07c106-eaf4-4ac2-8bbe-73769330f869"
SCRIPT_JOB_ID = "77894bae-e5d4-47e1-966f-bd76fc79b8e2"
SCRIPT_REVISION = 4


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    script_job = request_json(f"{BASE_URL}/jobs/{SCRIPT_JOB_ID}")
    script_result = script_job["result_json"]
    narrations = script_result.get("narrations") or []
    if script_job["status"] != "completed" or script_result.get("research_status") != "reference_ready":
        raise RuntimeError("Grounded script job is not reference_ready")
    if len(narrations) != 7:
        raise RuntimeError(f"Expected seven grounded narrations, got {len(narrations)}")

    response = request_json(
        f"{BASE_URL}/content/research/async",
        method="POST",
        payload={
            "project_id": PROJECT_ID,
            "topic": "F-16基础科普",
            "narrations": narrations,
            "asset_type": "video",
            "mode": "verified",
            "script_revision": SCRIPT_REVISION,
            "force_refresh": True,
        },
    )
    job_id = response["job_id"]
    print(json.dumps({"research_job_id": job_id}, ensure_ascii=False), flush=True)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        job = request_json(f"{BASE_URL}/jobs/{job_id}")
        result = job.get("result_json") or {}
        print(json.dumps({
            "job_id": job_id,
            "status": job["status"],
            "progress_stage": job.get("progress_stage"),
            "research_status": result.get("research_status"),
            "verification_status": result.get("verification_status"),
            "warnings": result.get("warnings", []),
            "scene_count": len(result.get("storyboard_plan") or []),
            "error": job.get("error_message"),
        }, ensure_ascii=False), flush=True)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return
        time.sleep(10)
    raise TimeoutError(f"Research job {job_id} did not finish within 900 seconds")


if __name__ == "__main__":
    main()
