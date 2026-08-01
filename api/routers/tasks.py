"""
Task management endpoints

Endpoints for managing async tasks (checking status, canceling, etc.)
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.errors import internal_server_error
from api.public_paths import sanitize_public_payload
from api.tasks import Task, TaskStatus, task_manager
from military_video_gen.database.runtime_jobs import sync_runtime_job
from military_video_gen.utils.safety import sanitize_error_message

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _public_task(task: Task) -> Task:
    """Return a detached task view with private paths and URLs redacted."""
    return task.model_copy(
        deep=True,
        update={
            "result": sanitize_public_payload(task.result),
            "request_params": sanitize_public_payload(task.request_params),
            "error": sanitize_error_message(task.error) if task.error else None,
        },
    )


@router.get("", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tasks")
):
    """
    List tasks
    
    Retrieve list of tasks with optional filtering.
    
    - **status**: Optional filter by status (pending/running/completed/failed/cancelled)
    - **limit**: Maximum number of tasks to return (default 100)
    
    Returns list of tasks sorted by creation time (newest first).
    """
    try:
        tasks = task_manager.list_tasks(status=status, limit=limit)
        return [_public_task(task) for task in tasks]
        
    except Exception as e:
        raise internal_server_error("List tasks error", e)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """
    Get task details
    
    Retrieve detailed information about a specific task.
    
    - **task_id**: Task ID
    
    Returns task details including status, progress, and result (if completed).
    """
    try:
        task = task_manager.get_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return _public_task(task)
        
    except HTTPException:
        raise
    except Exception as e:
        raise internal_server_error("Get task error", e)


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel task
    
    Cancel a running or pending task.
    
    - **task_id**: Task ID
    
    Returns success status.
    """
    try:
        success = task_manager.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        task = task_manager.get_task(task_id)
        if task is not None:
            await sync_runtime_job(task)
        
        return {
            "success": True,
            "message": f"Cancellation requested for task {task_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise internal_server_error("Cancel task error", e)

