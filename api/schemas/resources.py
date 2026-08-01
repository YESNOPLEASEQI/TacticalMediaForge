"""
Resource discovery API schemas
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class WorkflowInfo(BaseModel):
    """Workflow information"""
    name: str = Field(..., description="Workflow filename")
    display_name: str = Field(..., description="Display name with source info")
    source: str = Field(..., description="Source (runninghub or selfhost)")
    path: str = Field(..., description="Project-relative public workflow path")
    key: str = Field(..., description="Workflow key (source/name)")
    workflow_id: Optional[str] = Field(None, description="RunningHub workflow ID (if applicable)")


class WorkflowListResponse(BaseModel):
    """Workflow list response"""
    success: bool = True
    message: str = "Success"
    workflows: List[WorkflowInfo] = Field(..., description="List of available workflows")


class TemplateInfo(BaseModel):
    """Template information"""
    name: str = Field(..., description="Template filename")
    display_name: str = Field(..., description="Display name")
    size: str = Field(..., description="Size (e.g., 1080x1920)")
    width: int = Field(..., description="Width in pixels")
    height: int = Field(..., description="Height in pixels")
    orientation: str = Field(..., description="Orientation (portrait/landscape/square)")
    path: str = Field(..., description="Project-relative public template path")
    key: str = Field(..., description="Template key (size/name)")


class TemplateListResponse(BaseModel):
    """Template list response"""
    success: bool = True
    message: str = "Success"
    templates: List[TemplateInfo] = Field(..., description="List of available templates")


class BGMInfo(BaseModel):
    """BGM information"""
    name: str = Field(..., description="BGM filename")
    path: str = Field(..., description="Project-relative public BGM path")
    source: str = Field(..., description="Source (default or custom)")


class BGMListResponse(BaseModel):
    """BGM list response"""
    success: bool = True
    message: str = "Success"
    bgm_files: List[BGMInfo] = Field(..., description="List of available BGM files")

