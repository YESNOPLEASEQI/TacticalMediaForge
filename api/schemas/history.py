from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

HistoryStatus = Literal["queued", "running", "success", "failed", "cancelled"]
MessageRole = Literal["user", "assistant", "system", "tool"]
AssetType = Literal["video", "image", "audio", "subtitle", "workflow", "preview", "mask"]


class SessionSummary(BaseModel):
    id: str
    title: str
    user_id: Optional[str] = None
    project_type: str = "video_agent"
    status: HistoryStatus
    job_count: int = 1
    latest_job_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HistoryMessage(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: Dict[str, Any]
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationJob(BaseModel):
    id: str
    session_id: str
    message_id: Optional[str] = None
    status: HistoryStatus
    progress: int = 0
    provider: str = "local"
    external_job_id: Optional[str] = None
    prompt: str = ""
    negative_prompt: Optional[str] = None
    model_name: Optional[str] = None
    workflow_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[int] = None
    seed: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)


class HistoryAsset(BaseModel):
    id: str
    job_id: str
    session_id: str
    asset_type: AssetType
    url: Optional[str] = None
    local_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowSnapshot(BaseModel):
    id: str
    job_id: str
    session_id: str
    workflow_name: str
    workflow_json: Dict[str, Any] = Field(default_factory=dict)
    ui_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionSummary]
    total: int


class SessionDetail(BaseModel):
    session: SessionSummary
    messages: List[HistoryMessage]
    generation_jobs: List[GenerationJob]
    assets: List[HistoryAsset]
    workflow_snapshots: List[WorkflowSnapshot]

