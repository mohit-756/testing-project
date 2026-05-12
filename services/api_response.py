from fastapi import Response
from pydantic import BaseModel
from typing import Any, Generic, TypeVar

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> dict:
        return cls(success=True, data=data).dict()

    @classmethod
    def fail(cls, error: str, status_code: int = 400) -> dict:
        return cls(success=False, error=error).dict()

def response_wrapper(func):
    """FastAPI route decorator to wrap return values in ApiResponse.
    If the wrapped function returns a dict, it will be placed under ``data``.
    Any raised HTTPException will be propagated unchanged.
    """
    async def inner(*args, **kwargs):
        result = await func(*args, **kwargs)
        return ApiResponse.ok(result)
    return inner
