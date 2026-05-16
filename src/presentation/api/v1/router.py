from fastapi import APIRouter

from src.presentation.api.v1 import (
    auth_routes,
    business_routes,
    onboarding_routes,
)

api_v1_router = APIRouter()

# Public (no tenant context required)
api_v1_router.include_router(onboarding_routes.router, prefix="/onboarding", tags=["onboarding"])
api_v1_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])

# Tenant-scoped routers are added here as bounded contexts come online:
api_v1_router.include_router(business_routes.router)
