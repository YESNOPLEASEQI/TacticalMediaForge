"""Run live research for a narration revision composed only from extracted claims."""

from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = "1b07c106-eaf4-4ac2-8bbe-73769330f869"
SCRIPT_REVISION = 10
NARRATIONS = [
    "F-16战斗机由通用动力公司设计",
    "设计方就是General Dynamics",
    "首架量产F-16于1978年交付",
    "首次生产交付发生在1978年",
    "F-16曾在五个国家的工厂生产",
    "这五国包括美国比利时和荷兰",
    "还包括土耳其和韩国",
]


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    response = request_json(
        f"{BASE_URL}/content/research/async",
        method="POST",
        payload={
            "project_id": PROJECT_ID,
            "topic": "F-16基础科普",
            "narrations": NARRATIONS,
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
