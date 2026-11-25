"""Standardised API response envelope helpers."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody
    request_id: str | None = None


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool


def ok(
    data: Any,
    *,
    meta: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "meta": meta,
        "request_id": request_id,
    }
