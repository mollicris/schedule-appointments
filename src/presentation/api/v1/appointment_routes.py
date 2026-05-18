from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.application.appointment.book_appointment import BookAppointmentInput, BookAppointmentUseCase
from src.application.appointment.cancel_appointment import CancelAppointmentInput, CancelAppointmentUseCase
from src.application.appointment.get_appointment import GetAppointmentInput, GetAppointmentUseCase
from src.application.appointment.get_available_slots import GetAvailableSlotsInput, GetAvailableSlotsUseCase
from src.application.appointment.list_appointments import ListAppointmentsInput, ListAppointmentsUseCase
from src.application.appointment.reschedule_appointment import (
    RescheduleAppointmentInput,
    RescheduleAppointmentUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.repository import ClientRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.presentation.dependencies import (
    get_appointment_repository,
    get_business_hours_repository,
    get_client_repository,
    get_professional_repository,
    get_service_repository,
    get_unit_of_work,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response

router = APIRouter(prefix="/appointments", tags=["appointments"])


# ── Request / Response schemas ────────────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    business_id: UUID
    service_id: UUID
    scheduled_at: datetime = Field(description="UTC datetime for the appointment start")
    client_name: str = Field(min_length=1, max_length=255)
    client_whatsapp: str = Field(min_length=7, max_length=20)
    professional_id: UUID | None = None
    notes: str | None = None
    client_email: str | None = None


class AppointmentDetailSchema(BaseModel):
    appointment_id: UUID
    business_id: UUID
    service_id: UUID
    client_id: UUID
    professional_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    ends_at: datetime
    status: str
    notes: str | None
    cancelled_reason: str | None
    cancelled_at: datetime | None
    created_at: datetime


class AppointmentSummarySchema(BaseModel):
    appointment_id: UUID
    service_id: UUID
    service_name: str
    client_id: UUID
    client_name: str
    professional_id: UUID | None
    professional_name: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    ends_at: datetime
    status: str


class CancelRequest(BaseModel):
    reason: str | None = None


class RescheduleRequest(BaseModel):
    new_scheduled_at: datetime = Field(description="New UTC datetime for the appointment")


class AvailableSlotsSchema(BaseModel):
    slots: list[str]
    date: date
    service_duration_minutes: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Book a new appointment",
)
async def book_appointment(
    payload: BookAppointmentRequest,
    appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    clients: Annotated[ClientRepository, Depends(get_client_repository)],
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = BookAppointmentUseCase(
        appointments=appointments,
        services=services,
        clients=clients,
        professionals=professionals,
        uow=uow,
    )
    output = await use_case.execute(BookAppointmentInput(
        business_id=payload.business_id,
        service_id=payload.service_id,
        scheduled_at=payload.scheduled_at,
        client_name=payload.client_name,
        client_whatsapp=payload.client_whatsapp,
        professional_id=payload.professional_id,
        notes=payload.notes,
        client_email=payload.client_email,
    ))
    return success_response(
        message="Appointment booked successfully",
        code="APPOINTMENT_BOOKED",
        data=AppointmentDetailSchema(
            appointment_id=output.appointment_id,
            business_id=output.business_id,
            service_id=output.service_id,
            client_id=output.client_id,
            professional_id=output.professional_id,
            scheduled_at=output.scheduled_at,
            duration_minutes=output.duration_minutes,
            ends_at=output.ends_at,
            status=output.status.value,
            notes=None,
            cancelled_reason=None,
            cancelled_at=None,
            created_at=output.scheduled_at,
        ),
    )


@router.get(
    "/availability",
    status_code=status.HTTP_200_OK,
    summary="Get available time slots for a service on a given date",
)
async def get_available_slots(
    business_id: UUID = Query(...),
    service_id: UUID = Query(...),
    on_date: date = Query(...),
    professional_id: UUID | None = Query(default=None),
    appointments: AppointmentRepository = Depends(get_appointment_repository),
    services: ServiceRepository = Depends(get_service_repository),
    business_hours: BusinessHourRepository = Depends(get_business_hours_repository),
) -> SuccessResponse:
    use_case = GetAvailableSlotsUseCase(
        business_hours=business_hours,
        appointments=appointments,
        services=services,
    )
    output = await use_case.execute(GetAvailableSlotsInput(
        business_id=business_id,
        service_id=service_id,
        on_date=on_date,
        professional_id=professional_id,
    ))
    return success_response(
        message="Available slots retrieved",
        code="SLOTS_RETRIEVED",
        data=AvailableSlotsSchema(
            slots=output.slots,
            date=output.date,
            service_duration_minutes=output.service_duration_minutes,
        ),
    )


@router.get(
    "/{appointment_id}",
    status_code=status.HTTP_200_OK,
    summary="Get appointment details",
)
async def get_appointment(
    appointment_id: UUID,
    appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
) -> SuccessResponse:
    use_case = GetAppointmentUseCase(appointments=appointments)
    output = await use_case.execute(GetAppointmentInput(appointment_id=appointment_id))
    return success_response(
        message="Appointment retrieved",
        code="APPOINTMENT_FOUND",
        data=AppointmentDetailSchema(
            appointment_id=output.appointment_id,
            business_id=output.business_id,
            service_id=output.service_id,
            client_id=output.client_id,
            professional_id=output.professional_id,
            scheduled_at=output.scheduled_at,
            duration_minutes=output.duration_minutes,
            ends_at=output.ends_at,
            status=output.status.value,
            notes=output.notes,
            cancelled_reason=output.cancelled_reason,
            cancelled_at=output.cancelled_at,
            created_at=output.created_at,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List appointments for a business",
)
async def list_appointments(
    business_id: UUID = Query(...),
    on_date: date | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)] = ...,
    clients: Annotated[ClientRepository, Depends(get_client_repository)] = ...,
    services: Annotated[ServiceRepository, Depends(get_service_repository)] = ...,
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListAppointmentsUseCase(
        appointments=appointments,
        clients=clients,
        services=services,
        professionals=professionals,
    )
    output = await use_case.execute(ListAppointmentsInput(
        business_id=business_id,
        on_date=on_date,
        page=page,
        page_size=page_size,
    ))
    return paginated_response(
        data=[
            AppointmentSummarySchema(
                appointment_id=a.appointment_id,
                service_id=a.service_id,
                service_name=a.service_name,
                client_id=a.client_id,
                client_name=a.client_name,
                professional_id=a.professional_id,
                professional_name=a.professional_name,
                scheduled_at=a.scheduled_at,
                duration_minutes=a.duration_minutes,
                ends_at=a.ends_at,
                status=a.status.value,
            )
            for a in output.appointments
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@router.patch(
    "/{appointment_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel an appointment",
)
async def cancel_appointment(
    appointment_id: UUID,
    payload: CancelRequest,
    appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CancelAppointmentUseCase(appointments=appointments, uow=uow)
    output = await use_case.execute(CancelAppointmentInput(
        appointment_id=appointment_id,
        reason=payload.reason,
    ))
    return success_response(
        message="Appointment cancelled",
        code="APPOINTMENT_CANCELLED",
        data={"appointment_id": str(output.appointment_id), "status": output.status.value},
    )


@router.patch(
    "/{appointment_id}/reschedule",
    status_code=status.HTTP_200_OK,
    summary="Reschedule an appointment to a new time",
)
async def reschedule_appointment(
    appointment_id: UUID,
    payload: RescheduleRequest,
    appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = RescheduleAppointmentUseCase(appointments=appointments, uow=uow)
    output = await use_case.execute(RescheduleAppointmentInput(
        appointment_id=appointment_id,
        new_scheduled_at=payload.new_scheduled_at,
    ))
    return success_response(
        message="Appointment rescheduled",
        code="APPOINTMENT_RESCHEDULED",
        data={
            "appointment_id": str(output.appointment_id),
            "scheduled_at": output.scheduled_at.isoformat(),
            "ends_at": output.ends_at.isoformat(),
            "status": output.status.value,
        },
    )
