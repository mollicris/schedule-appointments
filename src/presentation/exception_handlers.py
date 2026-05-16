from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.domain.shared.errors import (
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    NotFoundError,
    TenantIsolationError,
    ValidationError,
)
from src.presentation.schemas.responses import ErrorDetail, ErrorResponse


class APIException(Exception):
    """Base exception for API errors with HTTP status code mapping."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: list[ErrorDetail] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


def domain_error_to_api_exception(error: DomainError) -> APIException:
    """Convert domain errors to API exceptions with appropriate HTTP status codes."""
    if isinstance(error, ValidationError):
        return APIException(
            message=str(error),
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=[ErrorDetail(code="VALIDATION_ERROR", message=str(error))],
        )
    elif isinstance(error, ConflictError):
        return APIException(
            message=str(error),
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=[ErrorDetail(code="CONFLICT", message=str(error))],
        )
    elif isinstance(error, NotFoundError):
        return APIException(
            message=str(error),
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[ErrorDetail(code="NOT_FOUND", message=str(error))],
        )
    elif isinstance(error, TenantIsolationError):
        return APIException(
            message=str(error),
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=[ErrorDetail(code="FORBIDDEN", message=str(error))],
        )
    elif isinstance(error, BusinessRuleViolationError):
        return APIException(
            message=str(error),
            code="BUSINESS_RULE_VIOLATION",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=[ErrorDetail(code="BUSINESS_RULE_VIOLATION", message=str(error))],
        )
    else:
        return APIException(
            message="An error occurred",
            code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=[ErrorDetail(code="INTERNAL_ERROR", message=str(error))],
        )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle APIException and return formatted error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            message=exc.message,
            code=exc.code,
            errors=exc.details,
        ).model_dump(),
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain errors and convert to API exceptions."""
    api_exc = domain_error_to_api_exception(exc)
    return await api_exception_handler(request, api_exc)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            message="An unexpected error occurred",
            code="INTERNAL_SERVER_ERROR",
            errors=[ErrorDetail(code="INTERNAL_SERVER_ERROR", message=str(exc))],
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
