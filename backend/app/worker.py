import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from arq.connections import RedisSettings
from app.core.config import settings
from app.core.logger import get_logger
from app.services.tasks import process_csv_upload, fetch_mock_bank_data_task, recompute_detections_task

logger = get_logger(__name__)


class WorkerSettings:
    """Configuration class for the arq worker."""

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [process_csv_upload, fetch_mock_bank_data_task, recompute_detections_task]


logger.info(
    "ARQ worker registered with %d task(s): %s",
    len(WorkerSettings.functions),
    [fn.__name__ for fn in WorkerSettings.functions],
)
