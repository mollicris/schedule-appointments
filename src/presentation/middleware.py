from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.application.shared.tenant_context import TenantContext, set_current_tenant
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.config.settings import get_settings

_PUBLIC_PREFIXES = (
    "/api/v1/onboarding",
    "/api/v1/auth",
    "/health",
    "/docs",
    "/openapi",
    "/webhooks",
)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Validates the JWT Bearer token and sets TenantContext for every protected request.

    Public routes (onboarding, auth, health, docs, webhooks) bypass this check.
    """

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app, **kwargs)
        settings = get_settings()
        self._jwt = JWTService(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        )

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Missing or invalid Authorization header", "code": "UNAUTHORIZED"},
            )

        token = auth_header[len("Bearer "):]
        try:
            payload = self._jwt.decode_access_token(token)
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Invalid or expired access token", "code": "UNAUTHORIZED"},
            )

        set_current_tenant(TenantContext(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            roles=frozenset([payload.role]),
        ))

        return await call_next(request)
