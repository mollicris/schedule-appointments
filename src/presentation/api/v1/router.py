from fastapi import APIRouter

from src.presentation.api.v1 import (
    auth_routes,
    onboarding_routes,
)

api_v1_router = APIRouter()

# Public (no tenant context required)
api_v1_router.include_router(onboarding_routes.router, prefix="/onboarding", tags=["onboarding"])
api_v1_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])

# Tenant-scoped routers are added here as bounded contexts come online:
# api_v1_router.include_router(businesses_routes.router, prefix="/businesses", tags=["businesses"])
# api_v1_router.include_router(services_routes.router, prefix="/services", tags=["services"])
# api_v1_router.include_router(appointments_routes.router, prefix="/appointments", tags=["appointments"])
# api_v1_router.include_router(conversations_routes.router, prefix="/conversations", tags=["conversations"])
# api_v1_router.include_router(analytics_routes.router, prefix="/analytics", tags=["analytics"])
