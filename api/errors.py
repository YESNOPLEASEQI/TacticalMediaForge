"""Safe public error helpers for API boundaries."""

from fastapi import HTTPException
from loguru import logger

from military_video_gen.utils.safety import sanitize_error_message


def internal_server_error(context: str, error: BaseException) -> HTTPException:
    """Log a sanitized diagnostic and return a non-reflective public 5xx error."""
    logger.error("{}: {}", context, sanitize_error_message(error))
    return HTTPException(status_code=500, detail="Internal server error")
