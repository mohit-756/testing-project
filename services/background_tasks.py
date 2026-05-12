from fastapi import BackgroundTasks
from typing import Callable, Awaitable, Any
import traceback
from .logging import logger


def schedule_proctor_image_upload(
    background: BackgroundTasks,
    session_id: int,
    image_bytes: bytes,
    timestamp: str,
    event_id: int = None,
    request_id: str = ""
) -> None:
    """Schedule the S3 upload in background.
    If event_id is provided, the S3 URL will be saved to ProctorEvent.image_path."""
    async def _run():
        try:
            # Use the working sync S3 function (same as PDF/resume uploads)
            from utils.s3_utils import upload_proctor_image
            s3_url = upload_proctor_image(session_id, image_bytes, timestamp)
            
            logger.info(
                "proctor_image_uploaded",
                extra={"session_id": session_id, "request_id": request_id, "s3_url": s3_url},
            )
            
            # Save S3 URL to database if event_id provided
            if event_id and s3_url:
                try:
                    from models import ProctorEvent
                    from database import SessionLocal
                    db = SessionLocal()
                    try:
                        event = db.query(ProctorEvent).filter(ProctorEvent.id == event_id).first()
                        if event:
                            event.image_path = s3_url
                            db.commit()
                            logger.info(
                                "proctor_event_image_path_updated",
                                extra={"event_id": event_id, "s3_url": s3_url},
                            )
                    finally:
                        db.close()
                except Exception as db_err:
                    logger.warning(f"Failed to save S3 URL to database: {db_err}")
                    
        except Exception:
            logger.exception(
                "proctor_image_upload_failed",
                extra={"session_id": session_id, "request_id": request_id, "trace": traceback.format_exc()},
            )
    background.add_task(_run)


def schedule_generic_task(
    background: BackgroundTasks,
    func: Callable[..., Awaitable[Any]],
    *args,
    request_id: str = "",
    **kwargs,
) -> None:
    """Run *func* in the background while preserving *request_id* for logging."""
    async def _run():
        try:
            await func(*args, **kwargs)
            logger.info(
                "background_task_completed",
                extra={"func": func.__name__, "request_id": request_id},
            )
        except Exception:
            logger.exception(
                "background_task_failed",
                extra={"func": func.__name__, "request_id": request_id, "trace": traceback.format_exc()},
            )
    background.add_task(_run)
