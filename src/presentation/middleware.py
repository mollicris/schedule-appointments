from __future__ import annotations

from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.application.shared.tenant_context import set_current_tenant, TenantContext
from src.domain.shared.errors import ValidationError


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract tenant context from request and set it in ContextVar.

    Phase 1: Uses X-Tenant-ID header for testing. In production, this
    will extract tenant_id from JWT token.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip context setting for public endpoints and system routes
        if request.url.path.startswith(("/api/v1/onboarding", "/api/v1/auth", "/health", "/docs", "/openapi")):
            return await call_next(request)

        # For tenant-scoped endpoints, extract tenant_id from header
        tenant_id_header = request.headers.get("X-Tenant-ID")
        if not tenant_id_header:
            raise ValidationError("Missing X-Tenant-ID header")

        try:
            tenant_id = UUID(tenant_id_header)
        except ValueError as e:
            raise ValidationError("Invalid X-Tenant-ID format") from e

        # Set tenant context for this request
        context = TenantContext(tenant_id=tenant_id)
        set_current_tenant(context)

        return await call_next(request)
