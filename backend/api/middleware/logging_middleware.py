# backend/api/middleware/logging_middleware.py

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware, RequestResponseEndpoint
)
import structlog

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enterprise logging middleware for request tracking."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Bind request context to logger
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        logger.info(
            "request_started",
            query_params=str(request.query_params),
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            logger.info(
                "request_completed",
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(
                round(process_time * 1000, 2)
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "request_failed",
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
            )
            raise