import logging
from pythonjsonlogger import jsonlogger

# Central logger for the application
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(request_id)s %(method)s %(path)s %(status_code)s %(duration_ms)s %(message)s"
)
log_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(log_handler)
