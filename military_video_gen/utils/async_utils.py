"""Async execution helpers with honest cancellation semantics."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


async def run_async_until_stopped(operation: Awaitable[T]) -> T:
    """Defer caller cancellation until an async provider operation finishes."""
    worker = asyncio.ensure_future(operation)
    cancellation_requested = False
    while True:
        try:
            result = await asyncio.shield(worker)
        except asyncio.CancelledError:
            if worker.cancelled():
                raise
            cancellation_requested = True
            continue
        except BaseException:
            if cancellation_requested:
                raise asyncio.CancelledError from None
            raise
        if cancellation_requested:
            raise asyncio.CancelledError
        return result


async def run_blocking_until_stopped(
    function: Callable[..., T],
    /,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run blocking work without declaring cancellation before it has stopped.

    Python cannot force-kill a thread that is inside FFmpeg or a provider SDK.
    Shielding the worker and deferring ``CancelledError`` ensures callers never
    observe a terminal CANCELLED/TIMED_OUT state while that worker can still
    write files or submit a late result. Cancellation remains cooperative at
    the next boundary for SDKs that do not expose their own cancel operation.
    """
    worker = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancellation_requested = False
    cancellation_hook_called = False
    while True:
        try:
            result = await asyncio.shield(worker)
        except asyncio.CancelledError:
            if worker.cancelled():
                raise
            cancellation_requested = True
            if not cancellation_hook_called:
                cancellation_hook_called = True
                owner = getattr(function, "__self__", None)
                cancel_hook = getattr(owner, "cancel_active_operations", None)
                if callable(cancel_hook):
                    hook_worker = asyncio.create_task(asyncio.to_thread(cancel_hook))
                    try:
                        await asyncio.shield(hook_worker)
                    except BaseException:
                        # A failed provider cancel hook cannot become false
                        # success; terminal state still waits for the worker.
                        pass
            continue
        except BaseException:
            if cancellation_requested:
                raise asyncio.CancelledError from None
            raise
        if cancellation_requested:
            raise asyncio.CancelledError
        return result
