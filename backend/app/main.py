"""FastAPI application entrypoint for CCI STEM Connect Impact Measurement System."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextAndRateLimitMiddleware
from app.core.responses import ok


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend REST API for the CCI STEM Connect Professional Engagement & "
            "Impact Measurement System. Measures six configurable pillars, supports "
            "flexible question cards and questionnaires, tracks 30/60/90-day outcomes "
            "with evidence classification, and exposes aggregate event analytics."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextAndRateLimitMiddleware)
    register_exception_handlers(app)

    @app.get("/health", tags=["Health"], summary="Service health check")
    def health_check(request: Request):
        return ok(
            {
                "status": "healthy",
                "service": settings.app_name,
                "version": settings.app_version,
                "environment": settings.app_env,
            },
            request_id=getattr(request.state, "request_id", None),
        )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
