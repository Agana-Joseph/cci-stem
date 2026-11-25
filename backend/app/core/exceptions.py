"""Domain exceptions and standardised FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error translated into the standard error envelope."""

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any | None = None) -> None:
        msg = (
            f"{resource} '{identifier}' was not found."
            if identifier is not None
            else f"{resource} was not found."
        )
        super().__init__(
            message=msg,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationAppError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Administrative API key is required.") -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitExceededError(AppError):
    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__(
            message="Too many requests. Please slow down and retry later.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": retry_after_seconds},
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "One or more request parameters failed validation.",
                    "details": jsonable_encoder(exc.errors()),
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal error occurred.",
                    "details": None,
                },
                "request_id": request_id,
            },
        )
