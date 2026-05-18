from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.application.service.create_service import (
    CreateServiceInput,
    CreateServiceOutput,
    CreateServiceUseCase,
)
from src.application.service.delete_service import (
    DeleteServiceInput,
    DeleteServiceOutput,
    DeleteServiceUseCase,
)
from src.application.service.get_service import (
    GetServiceInput,
    GetServiceOutput,
    GetServiceUseCase,
)
from src.application.service.list_services import (
    ListServicesInput,
    ListServicesOutput,
    ListServicesUseCase,
)
from src.application.service.update_service import (
    UpdateServiceInput,
    UpdateServiceOutput,
    UpdateServiceUseCase,
)
from src.application.service.assign_professionals_to_service import (
    AssignProfessionalsToServiceInput,
    AssignProfessionalsToServiceOutput,
    AssignProfessionalsToServiceUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.presentation.dependencies import (
    get_professional_repository,
    get_service_repository,
    get_unit_of_work,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response

router = APIRouter(prefix="/businesses/{business_id}/services", tags=["services"])


class CreateServiceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=127)
    duration_minutes: int = Field(default=30, ge=1, le=480)
    description: str | None = Field(default=None)
    price: int | None = Field(default=None, ge=0, description="Price in cents")


class UpdateServiceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=127)
    duration_minutes: int | None = Field(default=None, ge=1, le=480)
    description: str | None = Field(default=None)
    price: int | None = Field(default=None, ge=0, description="Price in cents")


class ServiceDetailResponse(BaseModel):
    service_id: UUID
    business_id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price: int | None
    is_active: bool
    professional_ids: list[UUID] = []


class ServiceSummaryResponse(BaseModel):
    service_id: UUID
    name: str
    duration_minutes: int
    price: int | None
    is_active: bool
    professional_ids: list[UUID] = []


class AssignProfessionalsRequest(BaseModel):
    professional_ids: list[UUID] = Field(default_factory=list)


class AssignProfessionalsResponseData(BaseModel):
    service_id: UUID
    professional_ids: list[UUID]


class CreateServiceResponseData(BaseModel):
    service_id: UUID
    name: str
    duration_minutes: int


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service",
    description="Create a new service under the specified business.",
)
async def create_service(
    business_id: UUID,
    payload: CreateServiceRequest,
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CreateServiceUseCase(services=services, uow=uow)
    output: CreateServiceOutput = await use_case.execute(
        CreateServiceInput(
            business_id=business_id,
            name=payload.name,
            duration_minutes=payload.duration_minutes,
            description=payload.description,
            price=payload.price,
        )
    )
    return success_response(
        message="Service created successfully",
        code="SERVICE_CREATED",
        data=CreateServiceResponseData(
            service_id=output.service_id,
            name=output.name,
            duration_minutes=output.duration_minutes,
        ),
    )


@router.get(
    "/{service_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a service by ID",
    description="Retrieve details of a specific service.",
)
async def get_service(
    business_id: UUID,
    service_id: UUID,
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
) -> SuccessResponse:
    use_case = GetServiceUseCase(services=services)
    output: GetServiceOutput = await use_case.execute(GetServiceInput(service_id=service_id))

    return success_response(
        message="Service retrieved successfully",
        code="SERVICE_FOUND",
        data=ServiceDetailResponse(
            service_id=output.service_id,
            business_id=output.business_id,
            name=output.name,
            description=output.description,
            duration_minutes=output.duration_minutes,
            price=output.price,
            is_active=output.is_active,
            professional_ids=output.professional_ids,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List services for a business",
    description="Retrieve a paginated list of active services for the specified business.",
)
async def list_services(
    business_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    services: Annotated[ServiceRepository, Depends(get_service_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListServicesUseCase(services=services)
    output: ListServicesOutput = await use_case.execute(
        ListServicesInput(
            business_id=business_id,
            page=page,
            page_size=page_size,
        )
    )

    return paginated_response(
        data=[
            ServiceSummaryResponse(
                service_id=s.service_id,
                name=s.name,
                duration_minutes=s.duration_minutes,
                price=s.price,
                is_active=s.is_active,
                professional_ids=s.professional_ids,
            )
            for s in output.services
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@router.put(
    "/{service_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a service",
    description="Update the details of an existing service.",
)
async def update_service(
    business_id: UUID,
    service_id: UUID,
    payload: UpdateServiceRequest,
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateServiceUseCase(services=services, uow=uow)
    output: UpdateServiceOutput = await use_case.execute(
        UpdateServiceInput(
            service_id=service_id,
            name=payload.name,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            price=payload.price,
        )
    )
    return success_response(
        message="Service updated successfully",
        code="SERVICE_UPDATED",
        data=ServiceDetailResponse(
            service_id=output.service_id,
            business_id=business_id,
            name=output.name,
            description=None,
            duration_minutes=output.duration_minutes,
            price=output.price,
            is_active=True,
        ),
    )


@router.put(
    "/{service_id}/professionals",
    status_code=status.HTTP_200_OK,
    summary="Assign professionals to a service",
    description="Replace the set of professionals that can perform this service.",
)
async def assign_professionals(
    business_id: UUID,
    service_id: UUID,
    payload: AssignProfessionalsRequest,
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = AssignProfessionalsToServiceUseCase(
        services=services, professionals=professionals, uow=uow
    )
    output: AssignProfessionalsToServiceOutput = await use_case.execute(
        AssignProfessionalsToServiceInput(
            service_id=service_id,
            professional_ids=payload.professional_ids,
        )
    )
    return success_response(
        message="Professionals assigned to service successfully",
        code="SERVICE_PROFESSIONALS_ASSIGNED",
        data=AssignProfessionalsResponseData(
            service_id=output.service_id,
            professional_ids=output.professional_ids,
        ),
    )


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a service",
    description="Soft-delete a service (marks it as inactive).",
)
async def delete_service(
    business_id: UUID,
    service_id: UUID,
    services: Annotated[ServiceRepository, Depends(get_service_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = DeleteServiceUseCase(services=services, uow=uow)
    output: DeleteServiceOutput = await use_case.execute(
        DeleteServiceInput(service_id=service_id)
    )
    return success_response(
        message="Service deleted successfully",
        code="SERVICE_DELETED",
        data={"service_id": str(output.service_id), "deleted": output.deleted},
    )
