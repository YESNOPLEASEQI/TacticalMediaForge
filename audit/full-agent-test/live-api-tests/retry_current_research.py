"""Retry the current revision-3 research snapshot and print terminal status."""

from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
PARENT_JOB_ID = "460467e8-83ff-411d-b9b7-acf70129a6b2"


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parent = request_json(f"{BASE_URL}/jobs/{PARENT_JOB_ID}")
    params = dict(parent["params_json"])
    research_request = {
        key: params[key]
        for key in (
            "project_id",
            "topic",
            "narrations",
            "asset_type",
            "mode",
            "script_revision",
        )
    }
    response = request_json(
        f"{BASE_URL}/content/research/{PARENT_JOB_ID}/retry",
        method="POST",
        payload={
            "parent_job_id": PARENT_JOB_ID,
            "force_refresh": True,
            "request": research_request,
        },
    )
    job_id = response["job_id"]
    print(json.dumps({"retry_job_id": job_id}, ensure_ascii=False), flush=True)

    deadline = time.monotonic() + 720
    while time.monotonic() < deadline:
        job = request_json(f"{BASE_URL}/jobs/{job_id}")
        result = job.get("result_json") or {}
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": job["status"],
                    "progress": job["progress"],
                    "progress_stage": job.get("progress_stage"),
                    "research_status": result.get("research_status"),
                    "verification_status": result.get("verification_status"),
                    "warnings": result.get("warnings", []),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if job["status"] in {"completed", "failed", "cancelled"}:
            return
        time.sleep(10)
    raise TimeoutError(f"Research retry {job_id} did not finish within 720 seconds")


if __name__ == "__main__":
    main()
