from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.public_paths import (
    public_api_file_reference,
    sanitize_public_payload,
    to_public_file_path,
    to_public_file_url,
)
from api.schemas.history import (
    GenerationJob,
    HistoryAsset,
    HistoryMessage,
    HistoryStatus,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    WorkflowSnapshot,
)
from api.tasks import task_manager
from military_video_gen.utils.safety import sanitize_error_message

router = APIRouter(tags=["History"])

TERMINAL_STATUS_MAP: Dict[str, HistoryStatus] = {
    "pending": "queued",
    "queued": "queued",
    "running": "running",
    "in_progress": "running",
    "completed": "success",
    "success": "success",
    "failed": "failed",
    "cancelled": "cancelled",
}


def normalize_status(status: Optional[str]) -> HistoryStatus:
    return TERMINAL_STATUS_MAP.get((status or "").lower(), "queued")


def denormalize_status(status: Optional[str]) -> Optional[str]:
    if status == "queued":
        return "pending"
    if status == "success":
        return "completed"
    return status


def infer_provider(workflow_id: Optional[str], config: Dict[str, Any]) -> str:
    workflow = (workflow_id or "").lower()
    if "runninghub" in workflow or config.get("runninghub_enabled"):
        return "runninghub"
    if "selfhost" in workflow or config.get("comfyui_url"):
        return "comfyui"
    return "local"


def get_session_id(task_id: str, metadata: Dict[str, Any]) -> str:
    input_params = metadata.get("input", {})
    return input_params.get("session_id") or metadata.get("session_id") or task_id


def title_from_metadata(task_id: str, metadata: Dict[str, Any]) -> str:
    input_params = metadata.get("input", {})
    title = input_params.get("title") or metadata.get("title")
    if title:
        return str(title)

    text = str(input_params.get("text") or "")
    if text:
        return text[:30] + ("..." if len(text) > 30 else "")

    return f"Video Session {task_id[:8]}"


def file_mime_type(path: str) -> Optional[str]:
    suffix = Path(path).suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".srt": "application/x-subrip",
        ".json": "application/json",
    }.get(suffix)


def asset_type_from_path(path: str) -> str:
    mime_type = file_mime_type(path) or ""
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    if path.endswith(".srt"):
        return "subtitle"
    if path.endswith(".json"):
        return "workflow"
    return "preview"


def safe_url(request: Request, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        return to_public_file_url(request, path)
    except ValueError:
        return None


def merge_metadata_with_live_task(task_id: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(metadata or {})
    live_task = task_manager.get_task(task_id)
    if not live_task:
        return merged

    merged.setdefault("task_id", live_task.task_id)
    merged["status"] = live_task.status.value
    merged.setdefault("created_at", live_task.created_at.isoformat())
    if live_task.completed_at:
        merged["completed_at"] = live_task.completed_at.isoformat()
    if live_task.request_params:
        merged.setdefault("input", live_task.request_params)
    if live_task.result:
        merged.setdefault("result", live_task.result)
    if live_task.error:
        merged["error"] = live_task.error
    if live_task.progress:
        merged["progress"] = live_task.progress.model_dump()

    return merged


async def load_metadata(military_video_gen: MilitaryVideoGenDep, task_id: str) -> Optional[Dict[str, Any]]:
    metadata = await military_video_gen.persistence.load_task_metadata(task_id)
    if metadata:
        return merge_metadata_with_live_task(task_id, metadata)

    live_task = task_manager.get_task(task_id)
    if not live_task:
        return None

    return merge_metadata_with_live_task(task_id, None)


async def resolve_latest_task_id(military_video_gen: Any, session_id: str) -> str:
    """Resolve a public session ID to its newest persisted or live task."""
    task_ids = {session_id}
    persisted_tasks = await military_video_gen.persistence.list_tasks(limit=200)
    task_ids.update(
        task.get("task_id") for task in persisted_tasks if task.get("task_id")
    )
    task_ids.update(task.task_id for task in task_manager.list_tasks(limit=200))

    candidates = []
    for task_id in task_ids:
        metadata = await load_metadata(military_video_gen, task_id)
        if not metadata or get_session_id(task_id, metadata) != session_id:
            continue
        updated_at = (
            metadata.get("completed_at")
            or metadata.get("updated_at")
            or metadata.get("created_at")
            or ""
        )
        candidates.append((updated_at, task_id))

    return max(candidates, default=("", session_id))[1]


def build_session_summary(request: Request, task_id: str, metadata: Dict[str, Any]) -> SessionSummary:
    input_params = metadata.get("input", {})
    result = metadata.get("result", {}) or {}
    video_path = result.get("video_path")
    video_url = safe_url(request, video_path) or public_api_file_reference(
        result.get("video_url")
    )
    session_id = get_session_id(task_id, metadata)
    updated_at = metadata.get("completed_at") or metadata.get("updated_at") or metadata.get("created_at")
    status = normalize_status(metadata.get("status"))

    return SessionSummary(
        id=session_id,
        title=title_from_metadata(task_id, metadata),
        user_id=input_params.get("user_id"),
        project_type=input_params.get("project_type", "video_agent"),
        status=status,
        job_count=1,
        latest_job_id=task_id,
        video_url=video_url,
        created_at=metadata.get("created_at"),
        updated_at=updated_at,
        metadata={
            "task_id": task_id,
            "n_frames": result.get("n_frames", 0),
            "duration": result.get("duration", 0),
            "file_size": result.get("file_size", 0),
            "mode": input_params.get("mode"),
            "tags": input_params.get("tags", []),
        },
    )


def build_messages(session_id: str, task_id: str, metadata: Dict[str, Any], storyboard: Any) -> List[HistoryMessage]:
    input_params = metadata.get("input", {}) or {}
    user_message_id = f"{task_id}:user"
    messages = [
        HistoryMessage(
            id=user_message_id,
            session_id=session_id,
            role="user",
            content={
                "text": input_params.get("text") or "",
                "attachments": sanitize_public_payload(
                    input_params.get("attachments", []),
                    field_name="attachments",
                ),
                "intent": "generate_video",
            },
            created_at=metadata.get("created_at"),
            metadata={"mode": input_params.get("mode"), "title": input_params.get("title")},
        )
    ]

    if storyboard:
        scenes = [
            {
                "index": frame.index,
                "narration": frame.narration,
                "image_prompt": frame.image_prompt,
                "visual_description": frame.visual_description or frame.image_prompt,
                "media_prompt": frame.image_prompt,
                "duration": frame.duration,
                "estimated_duration": frame.estimated_duration or frame.duration,
                "asset_type": frame.media_type or ("video" if frame.video_path else "image"),
                "media_type": frame.media_type,
            }
            for frame in storyboard.frames
        ]
        messages.append(
            HistoryMessage(
                id=f"{task_id}:assistant",
                session_id=session_id,
                role="assistant",
                content={
                    "text": f"已拆解为 {len(scenes)} 个镜头，并保存生成参数与产物。",
                    "agentSummary": storyboard.title,
                    "scenes": scenes,
                },
                created_at=storyboard.created_at.isoformat() if storyboard.created_at else metadata.get("created_at"),
                metadata={"source": "storyboard"},
            )
        )

    return messages


def progress_from_metadata(metadata: Dict[str, Any]) -> int:
    progress = metadata.get("progress")
    if isinstance(progress, dict):
        percentage = progress.get("percentage")
        if isinstance(percentage, (int, float)):
            return max(0, min(100, int(percentage)))
    return 100 if normalize_status(metadata.get("status")) == "success" else 0


def build_generation_job(request: Request, session_id: str, task_id: str, metadata: Dict[str, Any]) -> GenerationJob:
    input_params = metadata.get("input", {}) or {}
    raw_result = dict(metadata.get("result", {}) or {})
    config = metadata.get("config", {}) or {}
    workflow_id = input_params.get("media_workflow") or input_params.get("workflow_id")
    video_path = raw_result.get("video_path")
    result = sanitize_public_payload(raw_result)
    if video_path:
        result["video_url"] = safe_url(request, video_path)

    return GenerationJob(
        id=task_id,
        session_id=session_id,
        message_id=f"{task_id}:user",
        status=normalize_status(metadata.get("status")),
        progress=progress_from_metadata(metadata),
        provider=infer_provider(workflow_id, config),
        external_job_id=metadata.get("external_job_id") or result.get("external_job_id"),
        prompt=input_params.get("text") or "",
        negative_prompt=input_params.get("negative_prompt"),
        model_name=config.get("llm_model") or input_params.get("model_name"),
        workflow_id=workflow_id,
        width=input_params.get("media_width"),
        height=input_params.get("media_height"),
        duration=result.get("duration"),
        fps=input_params.get("video_fps"),
        seed=input_params.get("seed"),
        error_message=sanitize_error_message(
            metadata.get("error") or metadata.get("error_message") or ""
        ) or None,
        created_at=metadata.get("created_at"),
        updated_at=metadata.get("completed_at") or metadata.get("updated_at") or metadata.get("created_at"),
        completed_at=metadata.get("completed_at"),
        params=sanitize_public_payload(input_params),
        result=result,
    )


def build_asset(
    request: Request,
    *,
    asset_id: str,
    task_id: str,
    session_id: str,
    path: Optional[str],
    created_at: Optional[str],
    duration: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[HistoryAsset]:
    if not path:
        return None

    internal_path = str(path)
    path_obj = Path(internal_path)
    size_bytes = path_obj.stat().st_size if path_obj.exists() else None
    try:
        public_path = to_public_file_path(internal_path)
    except ValueError:
        public_path = None

    return HistoryAsset(
        id=asset_id,
        job_id=task_id,
        session_id=session_id,
        asset_type=asset_type_from_path(internal_path),  # type: ignore[arg-type]
        url=safe_url(request, internal_path),
        local_path=public_path,
        filename=path_obj.name,
        mime_type=file_mime_type(internal_path),
        size_bytes=size_bytes,
        duration=duration,
        created_at=created_at,
        metadata=sanitize_public_payload(metadata or {}),
    )


def non_empty_assets(assets: Iterable[Optional[HistoryAsset]]) -> List[HistoryAsset]:
    return [asset for asset in assets if asset is not None]


def build_assets(request: Request, session_id: str, task_id: str, metadata: Dict[str, Any], storyboard: Any) -> List[HistoryAsset]:
    result = metadata.get("result", {}) or {}
    assets = [
        build_asset(
            request,
            asset_id=f"{task_id}:final",
            task_id=task_id,
            session_id=session_id,
            path=result.get("video_path"),
            duration=result.get("duration"),
            created_at=metadata.get("completed_at") or metadata.get("created_at"),
            metadata={"role": "final_video"},
        )
    ]

    if storyboard:
        for frame in storyboard.frames:
            for field_name in ["image_path", "video_path", "audio_path", "composed_image_path", "video_segment_path"]:
                path = getattr(frame, field_name, None)
                assets.append(
                    build_asset(
                        request,
                        asset_id=f"{task_id}:frame:{frame.index}:{field_name}",
                        task_id=task_id,
                        session_id=session_id,
                        path=path,
                        duration=frame.duration if "video" in field_name or field_name == "audio_path" else None,
                        created_at=frame.created_at.isoformat() if frame.created_at else metadata.get("created_at"),
                        metadata={"frame_index": frame.index, "field": field_name},
                    )
                )

    return non_empty_assets(assets)


def load_workflow_json(workflow_id: Optional[str]) -> Dict[str, Any]:
    if not workflow_id:
        return {}

    workflow_path = Path("workflows") / workflow_id
    try:
        resolved = workflow_path.resolve()
        workflows_root = Path("workflows").resolve()
        if not resolved.is_file() or workflows_root not in resolved.parents:
            return {}

        import json

        with open(resolved, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {"workflow": payload}
    except Exception as exc:
        logger.debug(
            f"Unable to load workflow snapshot {workflow_id}: "
            f"{sanitize_error_message(exc)}"
        )
        return {}


def build_workflow_snapshot(session_id: str, task_id: str, metadata: Dict[str, Any], storyboard: Any) -> WorkflowSnapshot:
    input_params = metadata.get("input", {}) or {}
    workflow_id = input_params.get("media_workflow") or input_params.get("workflow_id") or "unknown"
    config = {}
    if storyboard:
        config = {
            "title": storyboard.title,
            "config": storyboard.config.model_dump() if hasattr(storyboard.config, "model_dump") else {},
            "frames": [
                {
                    "index": frame.index,
                    "narration": frame.narration,
                    "image_prompt": frame.image_prompt,
                    "visual_description": frame.visual_description or frame.image_prompt,
                    "media_prompt": frame.image_prompt,
                    "duration": frame.duration,
                    "estimated_duration": frame.estimated_duration or frame.duration,
                    "asset_type": frame.media_type or ("video" if frame.video_path else "image"),
                    "media_type": frame.media_type,
                }
                for frame in storyboard.frames
            ],
        }

    return WorkflowSnapshot(
        id=f"{task_id}:workflow",
        job_id=task_id,
        session_id=session_id,
        workflow_name=workflow_id,
        workflow_json=sanitize_public_payload(load_workflow_json(workflow_id)),
        ui_json=sanitize_public_payload({"input": input_params, "storyboard": config}),
        created_at=metadata.get("created_at"),
    )


async def build_session_detail(request: Request, military_video_gen: MilitaryVideoGenDep, task_id: str) -> SessionDetail:
    task_id = await resolve_latest_task_id(military_video_gen, task_id)
    metadata = await load_metadata(military_video_gen, task_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Session {task_id} not found")

    storyboard = await military_video_gen.persistence.load_storyboard(task_id)
    session_id = get_session_id(task_id, metadata)
    session = build_session_summary(request, task_id, metadata)

    return SessionDetail(
        session=session,
        messages=build_messages(session_id, task_id, metadata, storyboard),
        generation_jobs=[build_generation_job(request, session_id, task_id, metadata)],
        assets=build_assets(request, session_id, task_id, metadata, storyboard),
        workflow_snapshots=[build_workflow_snapshot(session_id, task_id, metadata, storyboard)],
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    military_video_gen: MilitaryVideoGenDep,
    status: Optional[HistoryStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    persistence_status = denormalize_status(status)
    persisted_tasks = await military_video_gen.persistence.list_tasks(status=persistence_status, limit=limit)
    task_ids = {task.get("task_id") for task in persisted_tasks if task.get("task_id")}

    live_tasks = task_manager.list_tasks(limit=limit)
    for live_task in live_tasks:
        if normalize_status(live_task.status.value) == status or status is None:
            if live_task.task_id not in task_ids:
                persisted_tasks.append(
                    {
                        "task_id": live_task.task_id,
                        "created_at": live_task.created_at.isoformat(),
                        "completed_at": live_task.completed_at.isoformat() if live_task.completed_at else None,
                        "status": live_task.status.value,
                        "title": (live_task.request_params or {}).get("title") or "Running video task",
                    }
                )

    sessions_by_id: Dict[str, SessionSummary] = {}
    for task in persisted_tasks:
        task_id = task.get("task_id")
        if not task_id:
            continue
        metadata = await load_metadata(military_video_gen, task_id)
        if not metadata:
            continue
        summary = build_session_summary(request, task_id, metadata)
        existing = sessions_by_id.get(summary.id)
        if existing is None:
            sessions_by_id[summary.id] = summary
            continue

        job_count = existing.job_count + 1
        existing_time = existing.updated_at or existing.created_at or ""
        summary_time = summary.updated_at or summary.created_at or ""
        selected = summary if summary_time > existing_time else existing
        sessions_by_id[summary.id] = selected.model_copy(update={"job_count": job_count})

    sessions = list(sessions_by_id.values())
    sessions.sort(key=lambda item: item.updated_at or item.created_at or "", reverse=True)
    return SessionListResponse(sessions=sessions[:limit], total=len(sessions))


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request, military_video_gen: MilitaryVideoGenDep):
    return await build_session_detail(request, military_video_gen, session_id)


@router.get("/sessions/{session_id}/messages", response_model=List[HistoryMessage])
async def get_session_messages(session_id: str, request: Request, military_video_gen: MilitaryVideoGenDep):
    detail = await build_session_detail(request, military_video_gen, session_id)
    return detail.messages


@router.get("/sessions/{session_id}/jobs", response_model=List[GenerationJob])
async def get_session_jobs(session_id: str, request: Request, military_video_gen: MilitaryVideoGenDep):
    detail = await build_session_detail(request, military_video_gen, session_id)
    return detail.generation_jobs


@router.get("/generation-jobs/{job_id}", response_model=GenerationJob)
async def get_generation_job(job_id: str, request: Request, military_video_gen: MilitaryVideoGenDep):
    detail = await build_session_detail(request, military_video_gen, job_id)
    return detail.generation_jobs[0]


@router.get("/generation-jobs/{job_id}/workflow", response_model=WorkflowSnapshot)
async def get_generation_job_workflow(job_id: str, request: Request, military_video_gen: MilitaryVideoGenDep):
    detail = await build_session_detail(request, military_video_gen, job_id)
    return detail.workflow_snapshots[0]


@router.post("/generation-jobs/{job_id}/retry")
async def retry_generation_job(job_id: str, military_video_gen: MilitaryVideoGenDep):
    input_params = await military_video_gen.history.duplicate_task(job_id)
    if not input_params:
        raise HTTPException(status_code=404, detail=f"Generation job {job_id} not found")
    return {"params": sanitize_public_payload(input_params)}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, military_video_gen: MilitaryVideoGenDep):
    live_task = task_manager.get_task(session_id)
    if live_task and live_task.status.value in {"pending", "running"}:
        task_manager.cancel_task(session_id)

    deleted = await military_video_gen.history.delete_task(session_id)
    if not deleted and not live_task:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"success": True, "message": f"Session {session_id} deleted"}
