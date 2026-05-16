from __future__ import annotations

from typing import Any, Generic, TypeVar

from src.presentation.schemas.responses import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)

T = TypeVar("T")


def success_response(
    data: T | None = None,
    message: str = "Success",
    code: str | None = None,
) -> SuccessResponse[T]:
    """Helper to create a success response.

    Args:
        data: Response payload
        message: Human-readable success message
        code: Optional response code for client handling

    Returns:
        SuccessResponse with structured data
    """
    return SuccessResponse(
        success=True,
        message=message,
        data=data,
        code=code,
    )


def paginated_response(
    data: list[T],
    total: int,
    page: int = 1,
    page_size: int = 10,
    message: str = "Items retrieved successfully",
    code: str | None = None,
) -> PaginatedResponse[T]:
    pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        success=True,
        message=message,
        data=data,
        code=code,
        pagination=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        ),
    )


# HTTP Status Code Constants
HTTP_STATUS_CODES = {
    # 2xx Success
    "OK": 200,
    "CREATED": 201,
    "ACCEPTED": 202,
    "NO_CONTENT": 204,
    # 3xx Redirection
    "MOVED_PERMANENTLY": 301,
    "FOUND": 302,
    "NOT_MODIFIED": 304,
    # 4xx Client Error
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "UNPROCESSABLE_ENTITY": 422,
    "TOO_MANY_REQUESTS": 429,
    # 5xx Server Error
    "INTERNAL_SERVER_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503,
}
