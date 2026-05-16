from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Base response wrapper for all API responses."""

    success: bool = Field(description="Whether the request was successful")
    message: str | None = Field(None, description="Human-readable message")
    data: Any | None = Field(None, description="Response data payload")
    code: str | None = Field(None, description="Response code for client handling")


class SuccessResponse(BaseResponse, Generic[T]):
    """Successful response wrapper.

    Examples:
        SuccessResponse[TenantResponse](
            success=True,
            message="Tenant created successfully",
            data=tenant_data,
            code="TENANT_CREATED"
        )
    """

    success: bool = True
    data: T


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response wrapper for list endpoints.

    Examples:
        PaginatedResponse[TenantResponse](
            success=True,
            data=[tenant1, tenant2],
            pagination=PaginationMeta(total=100, page=1, page_size=10, pages=10)
        )
    """

    success: bool = True
    data: list[T]
    pagination: PaginationMeta | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")


class ErrorDetail(BaseModel):
    """Error detail with field-level information."""

    field: str | None = Field(None, description="Field name if applicable")
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")


class ErrorResponse(BaseResponse):
    """Error response wrapper.

    Examples:
        ErrorResponse(
            success=False,
            message="Validation failed",
            code="VALIDATION_ERROR",
            errors=[
                ErrorDetail(field="email", code="INVALID_EMAIL", message="Invalid email format"),
                ErrorDetail(field="password", code="TOO_SHORT", message="Password must be at least 8 characters")
            ]
        )
    """

    success: bool = False
    errors: list[ErrorDetail] = Field(default_factory=list)


class NotFoundResponse(ErrorResponse):
    """Response when a resource is not found."""

    success: bool = False
    code: str = "NOT_FOUND"
    message: str = "Resource not found"


class UnauthorizedResponse(ErrorResponse):
    """Response when authentication is required."""

    success: bool = False
    code: str = "UNAUTHORIZED"
    message: str = "Unauthorized"


class ForbiddenResponse(ErrorResponse):
    """Response when user lacks permissions."""

    success: bool = False
    code: str = "FORBIDDEN"
    message: str = "Forbidden"


class ConflictResponse(ErrorResponse):
    """Response when a conflict occurs (e.g., duplicate resource)."""

    success: bool = False
    code: str = "CONFLICT"
    message: str = "Conflict"
