"""Submit and monitor a fresh video from the previously verified live snapshot."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
REQUEST_PATH = Path("audit/full-agent-test/live-api-tests/live-video-request.json")


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    payload = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    payload["video_fps"] = 16
    response = request_json(
        f"{BASE_URL}/video/generate/async",
        method="POST",
        payload=payload,
    )
    job_id = response["task_id"]
    print(json.dumps({"video_job_id": job_id}), flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        job = request_json(f"{BASE_URL}/jobs/{job_id}")
        print(json.dumps({
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress"),
            "stage": job.get("progress_stage"),
            "message": job.get("progress_message"),
            "result": job.get("result_json"),
            "error": job.get("error_message"),
        }, ensure_ascii=False), flush=True)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return
        time.sleep(10)
    raise TimeoutError(f"Video job {job_id} did not finish within 1200 seconds")


if __name__ == "__main__":
    main()
