"""Generation job API schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    parent_job_id: Optional[str] = None
    job_type: str
    provider: str
    status: str
    progress: float
    external_job_id: Optional[str]
    workflow_id: Optional[str]
    model_name: Optional[str]
    params_json: dict[str, Any]
    result_json: dict[str, Any]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_stage: Optional[str] = None
    progress_message: Optional[str] = None
