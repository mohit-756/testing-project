from typing import Any, Optional
from dataclasses import dataclass
from fastapi import Depends

DEFAULT_LIMIT = "5/minute"

try:
    from fastapi_limiter.depends import RateLimiter
    _FASTAPI_LIMITER_AVAILABLE = True
except ImportError:
    _FASTAPI_LIMITER_AVAILABLE = False
    RateLimiter = None


@dataclass
class LimiterConfig:
    """Configuration for rate limiting."""
    times: int
    seconds: int


def limiter(limit: str = DEFAULT_LIMIT) -> Optional[Any]:
    """Convenient wrapper for the FastAPI-Limiter dependency.
    
    Returns None if fastapi-limiter is not installed (for graceful degradation).
    """
    if not _FASTAPI_LIMITER_AVAILABLE:
        return None

    parts = limit.split('/')
    times = int(parts[0])
    window = parts[1].strip().lower() if len(parts) > 1 else "minute"
    seconds = 60 if window.startswith("min") else 1
    try:
        return Depends(RateLimiter(times=times, seconds=seconds))
    except TypeError:
        return None