from slowapi import Limiter
from slowapi.util import get_remote_address
from config.settings import settings
import structlog

logger = structlog.get_logger()

# Determine storage URI
storage_uri = "memory://"

if settings.REDIS_URL and not settings.REDIS_URL.startswith("memory"):
    # If a real Redis URL is configured (e.g. Upstash in production)
    storage_uri = settings.REDIS_URL
else:
    storage_uri = "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
        f"{settings.RATE_LIMIT_PER_DAY}/day"
    ],
    storage_uri=storage_uri,
)