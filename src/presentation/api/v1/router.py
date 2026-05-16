from fastapi import APIRouter

from src.presentation.api.v1 import (
    appointment_routes,
    auth_routes,
    business_hours_routes,
    business_routes,
    onboarding_routes,
    professional_routes,
    service_routes,
)

api_v1_router = APIRouter()

# Public (no tenant context required)
api_v1_router.include_router(onboarding_routes.router, prefix="/onboarding", tags=["onboarding"])
api_v1_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])

# Tenant-scoped routers are added here as bounded contexts come online:
api_v1_router.include_router(business_routes.router)
api_v1_router.include_router(service_routes.router)
api_v1_router.include_router(professional_routes.router)
api_v1_router.include_router(business_hours_routes.router)
api_v1_router.include_router(appointment_routes.router)
