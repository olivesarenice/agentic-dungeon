"""
LLM Request Logger - Tracks all API calls to LLM/AI providers.
"""

import time
import uuid
from datetime import datetime
from typing import Optional

from database.models import DBLLMRequest


class LLMRequestLogger:
    """
    Helper class for logging LLM API requests.
    Creates log entries that can be committed by the caller.
    """

    @staticmethod
    def create_log_entry(
        function_call: str,
        provider: str,
        model_id: str,
        prompt: str,
        status: int,
        response: Optional[str] = None,
        retry_count: int = 0,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> DBLLMRequest:
        """
        Create a log entry for an LLM request.

        Args:
            function_call: Function name (e.g., "llm_get_response", "image_generate", "tts_generate")
            provider: Provider name (e.g., "google", "elevenlabs")
            model_id: Model identifier (e.g., "gemini-2.5-flash")
            prompt: Input prompt/text
            status: HTTP status code (200, 429, 500, etc.)
            response: Response text or file path for media
            retry_count: Number of retries before final status
            latency_ms: Response time in milliseconds
            error_message: Error details if failed

        Returns:
            DBLLMRequest object (not yet committed to DB)
        """
        return DBLLMRequest(
            id=str(uuid.uuid4()),
            created_at=datetime.now(),
            function_call=function_call,
            provider=provider,
            model_id=model_id,
            status=status,
            prompt=prompt[:10000] if prompt else "",  # Truncate very long prompts
            response=(
                response[:10000] if response else None
            ),  # Truncate very long responses
            retry_count=retry_count,
            latency_ms=latency_ms,
            error_message=error_message[:2000] if error_message else None,
        )


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.end_time = time.time()

    @property
    def elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds."""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0


def detect_error_status(error: Exception) -> int:
    """
    Detect HTTP status code from exception.

    Args:
        error: The exception that was raised

    Returns:
        HTTP status code (429 for rate limit, 500 for other errors)
    """
    error_str = str(error).lower()

    if (
        "429" in str(error)
        or "rate" in error_str
        or "quota" in error_str
        or "resource_exhausted" in error_str
    ):
        return 429
    elif "timeout" in error_str:
        return 408
    elif "401" in str(error) or "unauthorized" in error_str:
        return 401
    elif "403" in str(error) or "forbidden" in error_str:
        return 403
    elif "404" in str(error) or "not found" in error_str:
        return 404
    else:
        return 500


def flush_all_llm_logs(session) -> int:
    """
    Flush all pending LLM logs from all modules to the database.

    This collects logs from:
    - llm_module (text generation)
    - text2img_module (image generation)
    - tts_module (audio generation)

    Args:
        session: SQLAlchemy database session

    Returns:
        Number of log entries committed
    """
    from llm.llm_module import get_pending_llm_logs
    from llm.text2img_module import get_pending_image_logs
    from llm.tts_module import get_pending_tts_logs

    # Collect all pending logs
    all_logs = []
    all_logs.extend(get_pending_llm_logs())
    all_logs.extend(get_pending_image_logs())
    all_logs.extend(get_pending_tts_logs())

    if not all_logs:
        return 0

    # Add all to session
    for log_entry in all_logs:
        session.add(log_entry)

    # Commit
    session.commit()

    print(f"[LLM_LOGS] Flushed {len(all_logs)} log entries to database")
    return len(all_logs)
