from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import time
from uuid import UUID

from src.application.onboarding.industry_templates import get_templates
from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.business import Business
from src.domain.business.repository import BusinessRepository
from src.domain.business_hours.business_hour import BusinessHour, DayOfWeek
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.service.repository import ServiceRepository
from src.domain.service.service import Service
from src.domain.shared.errors import BusinessRuleViolationError, ValidationError
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.value_objects import TenantStatus

_OPEN_AT = time(8, 0)
_CLOSE_AT = time(18, 0)


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")[:48] or "business"


@dataclass(frozen=True)
class CompleteWizardInput:
    business_name: str
    phone: str
    timezone: str = "UTC"
    address: str | None = None


@dataclass(frozen=True)
class CompleteWizardOutput:
    business_id: UUID
    business_slug: str
    tenant_status: str
    services_created: int


class CompleteWizardUseCase(UseCase[CompleteWizardInput, CompleteWizardOutput]):
    """Final step of auto-onboarding wizard.

    Creates the tenant's first Business, seeds default business hours
    (Mon–Sat 08:00–18:00, Sunday closed), and transitions the tenant
    from ONBOARDING → ACTIVE.
    """

    def __init__(
        self,
        tenants: TenantRepository,
        businesses: BusinessRepository,
        business_hours: BusinessHourRepository,
        services: ServiceRepository,
        uow: UnitOfWork,
    ) -> None:
        self._tenants = tenants
        self._businesses = businesses
        self._business_hours = business_hours
        self._services = services
        self._uow = uow

    async def execute(self, input_data: CompleteWizardInput) -> CompleteWizardOutput:
        self._validate(input_data)
        ctx = get_current_tenant()

        tenant = await self._tenants.get_by_id(ctx.tenant_id)
        if not tenant:
            raise ValidationError("Tenant not found")
        if tenant.status != TenantStatus.ONBOARDING:
            raise BusinessRuleViolationError(
                f"Wizard can only be completed from ONBOARDING status, current: {tenant.status.value}"
            )

        # Resolve unique slug
        base = _slugify(input_data.business_name)
        slug = base
        suffix = 1
        while await self._businesses.slug_exists(slug):
            suffix += 1
            slug = f"{base}-{suffix}"
            if suffix > 1000:
                raise BusinessRuleViolationError("Unable to generate a unique business slug")

        business = Business.create(
            tenant_id=ctx.tenant_id,
            name=input_data.business_name,
            slug=slug,
            phone=input_data.phone,
            timezone=input_data.timezone,
            address=input_data.address,
        )

        default_hours = [
            BusinessHour.create(
                tenant_id=ctx.tenant_id,
                business_id=business.id,
                day_of_week=day,
                open_at=_OPEN_AT,
                close_at=_CLOSE_AT,
                is_closed=(day == DayOfWeek.SUNDAY),
            )
            for day in range(7)
        ]

        templates = get_templates(tenant.industry)
        default_services = [
            Service.create(
                tenant_id=ctx.tenant_id,
                business_id=business.id,
                name=t.name,
                description=t.description,
                duration_minutes=t.duration_minutes,
            )
            for t in templates
        ]

        tenant.complete_onboarding()

        async with self._uow:
            await self._businesses.add(business)
            await self._business_hours.upsert_many(default_hours)
            for svc in default_services:
                await self._services.add(svc)
            await self._tenants.update(tenant)
            await self._uow.commit()

        return CompleteWizardOutput(
            business_id=business.id,
            business_slug=business.slug,
            tenant_status=tenant.status.value,
            services_created=len(default_services),
        )

    def _validate(self, data: CompleteWizardInput) -> None:
        if not data.business_name.strip():
            raise ValidationError("Business name is required")
        if not data.phone.strip():
            raise ValidationError("Phone number is required")
