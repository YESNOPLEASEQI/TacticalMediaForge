"""
Task Manager

In-memory task management for video generation jobs.
"""

import asyncio
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from loguru import logger

from api.config import api_config
from api.tasks.models import Task, TaskProgress, TaskStatus, TaskType
from military_video_gen.utils.safety import sanitize_error_message

SHUTDOWN_CANCELLATION_REASON = "Task cancelled because the application is shutting down"
TASK_CANCELLATION_REASON = "Task cancelled"
TASK_CANCELLATION_REQUESTED_REASON = "Task cancellation requested; waiting for active blocking work to stop"


class TaskManager:
    """
    Task manager for handling async video generation tasks
    
    Features:
    - In-memory storage (can be replaced with Redis later)
    - Task lifecycle management
    - Progress tracking
    - Auto cleanup of old tasks
    """
    
    def __init__(
        self,
        *,
        max_concurrent_tasks: int | None = None,
        task_timeout_seconds: float | None = None,
    ):
        self._tasks: Dict[str, Task] = {}
        self._task_futures: Dict[str, asyncio.Task] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        limit = max_concurrent_tasks or api_config.max_concurrent_tasks
        if limit < 1:
            raise ValueError("max_concurrent_tasks must be positive")
        self._task_semaphore = asyncio.Semaphore(limit)
        self._task_timeout_seconds = (
            task_timeout_seconds
            if task_timeout_seconds is not None
            else api_config.task_timeout_seconds
        )
    
    async def start(self):
        """Start task manager and cleanup scheduler"""
        if self._running:
            logger.warning("Task manager already running")
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("✅ Task manager started")
    
    async def stop(self):
        """Stop task manager and cancel all tasks"""
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Set the shutdown state before cancelling futures so their
        # CancelledError handlers persist the same reason.
        cancelled_tasks = []
        for task in self._tasks.values():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                continue
            task.status = TaskStatus.CANCELLED
            task.error = SHUTDOWN_CANCELLATION_REASON
            task.completed_at = datetime.now()
            cancelled_tasks.append(task)

        cancelled_futures = []
        for task_id, future in self._task_futures.items():
            if not future.done():
                future.cancel()
                cancelled_futures.append(future)
                logger.info(f"Cancelled task: {task_id}")

        if cancelled_futures:
            await asyncio.gather(*cancelled_futures, return_exceptions=True)

        # Also persists pending tasks without a future. Wait for all writes
        # before discarding the in-memory task records.
        for task in cancelled_tasks:
            await self._sync_runtime_job(task)
        
        self._tasks.clear()
        self._task_futures.clear()
        logger.info("✅ Task manager stopped")
    
    def create_task(
        self,
        task_type: TaskType,
        request_params: Optional[dict] = None
    ) -> Task:
        """
        Create a new task
        
        Args:
            task_type: Type of task
            request_params: Original request parameters
            
        Returns:
            Created task
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            request_params=deepcopy(request_params),
        )
        
        self._tasks[task_id] = task
        logger.info(f"Created task {task_id} ({task_type})")
        return task

    def create_or_get_task(
        self,
        task_type: TaskType,
        request_params: Optional[dict] = None,
    ) -> tuple[Task, bool]:
        """Reuse an identical active task to make API retries idempotent."""
        wanted = request_params or {}
        for task in self._tasks.values():
            if (
                task.task_type == task_type
                and task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}
                and (task.request_params or {}) == wanted
            ):
                return task, False
        return self.create_task(
            task_type=task_type,
            request_params=wanted,
        ), True
    
    async def execute_task(
        self,
        task_id: str,
        coro_func: Callable,
        *args,
        timeout_seconds: float | None = None,
        **kwargs
    ):
        """
        Execute task asynchronously
        
        Args:
            task_id: Task ID
            coro_func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return
        
        # Create async task
        deadline = timeout_seconds or self._task_timeout_seconds

        async def _execute():
            try:
                # The deadline begins as soon as background execution starts,
                # including runtime sync and semaphore queue time.
                async with asyncio.timeout(deadline):
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now()
                    await self._sync_runtime_job(task)
                    logger.info(f"Task {task_id} started")

                    async with self._task_semaphore:
                        result = await coro_func(*args, **kwargs)
                    if result is None:
                        raise RuntimeError("Task returned no result")
                
                # Update task with result
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                terminal_synced = await self._sync_runtime_job(task)
                if terminal_synced is False:
                    task.status = TaskStatus.FAILED
                    task.error = "Task result could not be persisted to the runtime database"
                    task.completed_at = datetime.now()
                    await self._sync_runtime_job(task)
                    logger.error(f"Task {task_id} failed terminal persistence")
                    return
                logger.info(f"Task {task_id} completed")
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                if task.error != SHUTDOWN_CANCELLATION_REASON:
                    task.error = TASK_CANCELLATION_REASON
                task.completed_at = datetime.now()
                await self._sync_runtime_job(task)
                logger.info(f"Task {task_id} cancelled")
                raise
            except TimeoutError:
                task.status = TaskStatus.FAILED
                task.error = f"Task timed out after {deadline:g} seconds"
                task.completed_at = datetime.now()
                await self._sync_runtime_job(task)
                logger.error(f"Task {task_id} timed out")
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = sanitize_error_message(e)
                task.completed_at = datetime.now()
                await self._sync_runtime_job(task)
                logger.error(f"Task {task_id} failed: {task.error}")
        
        # Start execution
        future = asyncio.create_task(_execute())
        self._task_futures[task_id] = future

    async def run_limited(
        self,
        coro_func: Callable,
        *args,
        timeout_seconds: float | None = None,
        **kwargs,
    ):
        """Run synchronous-endpoint work under the shared task bound/deadline."""
        deadline = timeout_seconds or self._task_timeout_seconds
        async with asyncio.timeout(deadline):
            async with self._task_semaphore:
                return await coro_func(*args, **kwargs)

    async def _sync_runtime_job(self, task: Task) -> bool:
        try:
            from military_video_gen.database.runtime_jobs import sync_runtime_job
            await sync_runtime_job(task)
            return True
        except Exception as exc:
            logger.error(
                f"GenerationJob sync failed for {task.task_id}: {sanitize_error_message(exc)}"
            )
            return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self._tasks.get(task_id)

    def discard_pending_task(self, task_id: str) -> bool:
        """Remove a task that failed before background execution was scheduled."""
        task = self._tasks.get(task_id)
        future = self._task_futures.get(task_id)
        if task is None or future is not None or task.status != TaskStatus.PENDING:
            return False
        del self._tasks[task_id]
        return True
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks with optional filtering
        
        Args:
            status: Filter by status
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks
        """
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def update_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str = "",
        stage: Optional[str] = None,
        current_scene: Optional[int] = None,
        total_scenes: Optional[int] = None,
    ):
        """
        Update task progress
        
        Args:
            task_id: Task ID
            current: Current progress
            total: Total steps
            message: Progress message
        """
        task = self._tasks.get(task_id)
        if not task:
            return
        
        percentage = (current / total * 100) if total > 0 else 0
        task.progress = TaskProgress(
            current=current,
            total=total,
            percentage=percentage,
            message=message,
            stage=stage,
            current_scene=current_scene,
            total_scenes=total_scenes,
        )
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled, False otherwise
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        # Do not cancel already-terminal tasks
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        # Cancel future if running
        future = self._task_futures.get(task_id)
        was_pending = task.status == TaskStatus.PENDING
        if future and not future.done():
            future.cancel()

        if was_pending:
            # A task cancelled before its coroutine's first instruction has no
            # active worker to wait for, so publish the terminal state here.
            task.status = TaskStatus.CANCELLED
            task.error = TASK_CANCELLATION_REASON
            task.completed_at = datetime.now()
            try:
                asyncio.get_running_loop().create_task(self._sync_runtime_job(task))
            except RuntimeError:
                pass
            logger.info(f"Cancelled pending task {task_id}")
            return True
        
        # Do not publish a terminal CANCELLED state until the coroutine and any
        # shielded blocking worker have actually stopped.
        if future and not future.done():
            task.error = TASK_CANCELLATION_REQUESTED_REASON
            logger.info(f"Cancellation requested for task {task_id}")
        else:
            task.status = TaskStatus.CANCELLED
            task.error = TASK_CANCELLATION_REASON
            task.completed_at = datetime.now()
            logger.info(f"Cancelled pending task {task_id}")
        return True
    
    async def _cleanup_loop(self):
        """Periodically clean up old completed tasks"""
        while self._running:
            try:
                await asyncio.sleep(api_config.task_cleanup_interval)
                self._cleanup_old_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {sanitize_error_message(e)}")
    
    def _cleanup_old_tasks(self):
        """Remove old completed/failed tasks"""
        cutoff_time = datetime.now() - timedelta(seconds=api_config.task_retention_time)
        
        tasks_to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at and task.completed_at < cutoff_time:
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self._tasks[task_id]
            if task_id in self._task_futures:
                del self._task_futures[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")


# Global task manager instance
task_manager = TaskManager()

