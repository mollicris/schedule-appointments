from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.onboarding.complete_wizard import CompleteWizardInput, CompleteWizardUseCase
from src.application.onboarding.connect_whatsapp import ConnectWhatsAppInput, ConnectWhatsAppUseCase
from src.application.onboarding.industry_templates import get_templates
from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.business.repository import BusinessRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import BusinessRuleViolationError, NotFoundError, ValidationError
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.value_objects import TenantStatus
from src.infrastructure.whatsapp.meta_graph_client import MetaGraphClient
from src.presentation.dependencies import (
    get_business_hours_repository,
    get_business_repository,
    get_meta_graph_client,
    get_service_repository,
    get_tenant_repository,
    get_unit_of_work,
)

router = APIRouter()


class DefaultServiceInfo(BaseModel):
    name: str
    description: str
    duration_minutes: int


class WizardStateResponse(BaseModel):
    tenant_id: UUID
    tenant_name: str
    industry: str
    status: str
    suggested_business_name: str
    default_open_at: str
    default_close_at: str
    open_days: list[str]
    default_services: list[DefaultServiceInfo]


class CompleteWizardRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=30)
    timezone: str = Field(default="UTC", max_length=50)
    address: str | None = Field(default=None, max_length=200)


class CompleteWizardResponseData(BaseModel):
    business_id: UUID
    business_slug: str
    tenant_status: str
    services_created: int


class CompleteWizardResponse(BaseModel):
    success: bool = True
    message: str
    data: CompleteWizardResponseData


@router.get(
    "/state",
    status_code=status.HTTP_200_OK,
    summary="Get current wizard state for the authenticated tenant",
    responses={
        403: {"description": "Tenant has not completed email verification"},
        404: {"description": "Tenant not found"},
    },
)
async def get_wizard_state(
    tenants: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> WizardStateResponse:
    ctx = get_current_tenant()
    tenant = await tenants.get_by_id(ctx.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.status not in (TenantStatus.ONBOARDING, TenantStatus.ACTIVE):
        raise HTTPException(
            status_code=403,
            detail="Wizard is only available after email verification",
        )
    templates = get_templates(tenant.industry)
    return WizardStateResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        industry=tenant.industry,
        status=tenant.status.value,
        suggested_business_name=tenant.name,
        default_open_at="08:00",
        default_close_at="18:00",
        open_days=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"],
        default_services=[
            DefaultServiceInfo(
                name=t.name,
                description=t.description,
                duration_minutes=t.duration_minutes,
            )
            for t in templates
        ],
    )


@router.post(
    "/complete",
    status_code=status.HTTP_200_OK,
    summary="Complete the onboarding wizard and activate the tenant",
    responses={
        403: {"description": "Tenant is not in ONBOARDING status"},
        422: {"description": "Validation error"},
    },
)
async def complete_wizard(
    payload: CompleteWizardRequest,
    tenants: Annotated[TenantRepository, Depends(get_tenant_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    business_hours: Annotated[BusinessHourRepository, Depends(get_business_hours_repository)],
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CompleteWizardResponse:
    use_case = CompleteWizardUseCase(
        tenants=tenants,
        businesses=businesses,
        business_hours=business_hours,
        services=services,
        uow=uow,
    )
    try:
        output = await use_case.execute(
            CompleteWizardInput(
                business_name=payload.business_name,
                phone=payload.phone,
                timezone=payload.timezone,
                address=payload.address,
            )
        )
    except BusinessRuleViolationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CompleteWizardResponse(
        success=True,
        message=f"Onboarding completo. Se crearon {output.services_created} servicios por defecto.",
        data=CompleteWizardResponseData(
            business_id=output.business_id,
            business_slug=output.business_slug,
            tenant_status=output.tenant_status,
            services_created=output.services_created,
        ),
    )


# ── WhatsApp Embedded Signup ──────────────────────────────────────────────────


class WhatsAppConnectRequest(BaseModel):
    code: str = Field(min_length=1, description="Auth code returned by the Facebook Embedded Signup popup")
    redirect_uri: str = Field(default="", description="Must match the URI registered in your Meta App")


class WhatsAppConnectResponseData(BaseModel):
    business_id: UUID
    waba_id: str
    phone_number_id: str
    phone_display: str


class WhatsAppConnectResponse(BaseModel):
    success: bool = True
    message: str
    data: WhatsAppConnectResponseData


class WhatsAppStatusResponse(BaseModel):
    connected: bool
    phone_number_id: str | None
    waba_id: str | None
    phone_display: str | None
    meta_app_id: str


@router.post(
    "/whatsapp/connect",
    status_code=status.HTTP_200_OK,
    summary="Complete WhatsApp Embedded Signup — exchange OAuth code for credentials",
    responses={
        400: {"description": "Meta API error or missing WABA/phone"},
        404: {"description": "No active business found"},
    },
)
async def connect_whatsapp(
    payload: WhatsAppConnectRequest,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    meta_client: Annotated[MetaGraphClient, Depends(get_meta_graph_client)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WhatsAppConnectResponse:
    use_case = ConnectWhatsAppUseCase(
        businesses=businesses,
        meta_client=meta_client,
        uow=uow,
    )
    try:
        output = await use_case.execute(
            ConnectWhatsAppInput(code=payload.code, redirect_uri=payload.redirect_uri)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WhatsAppConnectResponse(
        success=True,
        message=f"WhatsApp conectado correctamente al número {output.phone_display}.",
        data=WhatsAppConnectResponseData(
            business_id=output.business_id,
            waba_id=output.waba_id,
            phone_number_id=output.phone_number_id,
            phone_display=output.phone_display,
        ),
    )


@router.get(
    "/whatsapp/status",
    status_code=status.HTTP_200_OK,
    summary="Check WhatsApp connection status for the current tenant's business",
)
async def get_whatsapp_status(
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    meta_client: Annotated[MetaGraphClient, Depends(get_meta_graph_client)],
) -> WhatsAppStatusResponse:
    from src.infrastructure.config.settings import get_settings
    settings = get_settings()

    active = await businesses.list_active(limit=1)
    if not active:
        return WhatsAppStatusResponse(
            connected=False,
            phone_number_id=None,
            waba_id=None,
            phone_display=None,
            meta_app_id=settings.meta_app_id,
        )

    business = active[0]
    connected = bool(business.whatsapp_phone_number_id and business.whatsapp_waba_id)
    return WhatsAppStatusResponse(
        connected=connected,
        phone_number_id=business.whatsapp_phone_number_id,
        waba_id=business.whatsapp_waba_id,
        phone_display=business.owner_whatsapp,
        meta_app_id=settings.meta_app_id,
    )
