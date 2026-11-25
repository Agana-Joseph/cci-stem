"""HTTP middlewares: request correlation ID and sliding-window rate limiting."""

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.core.rate_limiter import rate_limiter


class RequestContextAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        settings = get_settings()
        if (
            settings.rate_limit_enabled
            and request.method != "OPTIONS"
            and not request.url.path.startswith("/health")
        ):
            client_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else "unknown")
            )
            path = request.url.path
            if path.endswith("/participants/lookup"):
                bucket_name = "lookup"
                limit = settings.rate_limit_lookup_per_minute
            elif path.endswith("/assessments/submit") or path.endswith("/submit"):
                bucket_name = "submit"
                limit = settings.rate_limit_submit_per_minute
            else:
                bucket_name = "general"
                limit = settings.rate_limit_requests_per_minute

            allowed, remaining, retry_after = rate_limiter.check(
                f"{bucket_name}:{client_ip}", limit=limit, window_seconds=60
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-Request-ID": request_id,
                    },
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down and retry later.",
                            "details": {"retry_after_seconds": retry_after},
                        },
                        "request_id": request_id,
                    },
                )
        else:
            remaining = None

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
