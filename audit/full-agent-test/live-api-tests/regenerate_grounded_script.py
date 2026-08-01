"""Regenerate the current seven-scene script through the real reference pipeline."""

from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = "1b07c106-eaf4-4ac2-8bbe-73769330f869"


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    project = request_json(f"{BASE_URL}/projects/{PROJECT_ID}")
    draft = project["settings_json"]["workspace_draft"]
    topic = draft["sourceText"].strip()
    response = request_json(
        f"{BASE_URL}/content/narration/async",
        method="POST",
        payload={
            "project_id": PROJECT_ID,
            "text": topic,
            "n_scenes": 7,
            "min_words": 5,
            "max_words": 20,
            "mode": "reference",
        },
    )
    job_id = response["job_id"]
    print(json.dumps({"script_job_id": job_id}, ensure_ascii=False), flush=True)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        job = request_json(f"{BASE_URL}/jobs/{job_id}")
        result = job.get("result_json") or {}
        print(json.dumps({
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "research_status": result.get("research_status"),
            "warnings": result.get("warnings", []),
            "narrations": result.get("narrations", []),
            "error": job.get("error_message"),
        }, ensure_ascii=False), flush=True)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return
        time.sleep(10)
    raise TimeoutError(f"Script job {job_id} did not finish within 900 seconds")


if __name__ == "__main__":
    main()
