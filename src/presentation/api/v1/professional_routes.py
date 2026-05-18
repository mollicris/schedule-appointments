from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.application.professional.create_professional import (
    CreateProfessionalInput,
    CreateProfessionalOutput,
    CreateProfessionalUseCase,
)
from src.application.professional.delete_professional import (
    DeleteProfessionalInput,
    DeleteProfessionalOutput,
    DeleteProfessionalUseCase,
)
from src.application.professional.get_professional import (
    GetProfessionalInput,
    GetProfessionalOutput,
    GetProfessionalUseCase,
)
from src.application.professional.list_professionals import (
    ListProfessionalsInput,
    ListProfessionalsOutput,
    ListProfessionalsUseCase,
)
from src.application.professional.update_professional import (
    UpdateProfessionalInput,
    UpdateProfessionalOutput,
    UpdateProfessionalUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.professional.repository import ProfessionalRepository
from src.presentation.dependencies import (
    get_professional_repository,
    get_unit_of_work,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response

router = APIRouter(prefix="/businesses/{business_id}/professionals", tags=["professionals"])


class CreateProfessionalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=127)
    phone: str | None = Field(default=None, max_length=20)
    user_id: UUID | None = None


class UpdateProfessionalRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=127)
    phone: str | None = Field(default=None, max_length=20)


class ProfessionalDetailResponse(BaseModel):
    professional_id: UUID
    business_id: UUID
    user_id: UUID | None
    name: str
    phone: str | None
    is_active: bool


class ProfessionalSummaryResponse(BaseModel):
    professional_id: UUID
    user_id: UUID | None
    name: str
    phone: str | None
    is_active: bool


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a professional in a business",
    description="Link an existing user account to a business as a professional.",
)
async def create_professional(
    business_id: UUID,
    payload: CreateProfessionalRequest,
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CreateProfessionalUseCase(professionals=professionals, uow=uow)
    output: CreateProfessionalOutput = await use_case.execute(
        CreateProfessionalInput(
            business_id=business_id,
            name=payload.name,
            phone=payload.phone,
            user_id=payload.user_id,
        )
    )
    return success_response(
        message="Professional registered successfully",
        code="PROFESSIONAL_CREATED",
        data={"professional_id": str(output.professional_id), "name": output.name},
    )


@router.get(
    "/{professional_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a professional by ID",
)
async def get_professional(
    business_id: UUID,
    professional_id: UUID,
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
) -> SuccessResponse:
    use_case = GetProfessionalUseCase(professionals=professionals)
    output: GetProfessionalOutput = await use_case.execute(
        GetProfessionalInput(professional_id=professional_id)
    )
    return success_response(
        message="Professional retrieved successfully",
        code="PROFESSIONAL_FOUND",
        data=ProfessionalDetailResponse(
            professional_id=output.professional_id,
            business_id=output.business_id,
            user_id=output.user_id,
            name=output.name,
            phone=output.phone,
            is_active=output.is_active,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List professionals in a business",
    description="Retrieve a paginated list of active professionals for the specified business.",
)
async def list_professionals(
    business_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListProfessionalsUseCase(professionals=professionals)
    output: ListProfessionalsOutput = await use_case.execute(
        ListProfessionalsInput(
            business_id=business_id,
            page=page,
            page_size=page_size,
        )
    )
    return paginated_response(
        data=[
            ProfessionalSummaryResponse(
                professional_id=p.professional_id,
                user_id=p.user_id,
                name=p.name,
                phone=p.phone,
                is_active=p.is_active,
            )
            for p in output.professionals
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@router.put(
    "/{professional_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a professional",
)
async def update_professional(
    business_id: UUID,
    professional_id: UUID,
    payload: UpdateProfessionalRequest,
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateProfessionalUseCase(professionals=professionals, uow=uow)
    output: UpdateProfessionalOutput = await use_case.execute(
        UpdateProfessionalInput(
            professional_id=professional_id,
            name=payload.name,
            phone=payload.phone,
        )
    )
    return success_response(
        message="Professional updated successfully",
        code="PROFESSIONAL_UPDATED",
        data=ProfessionalSummaryResponse(
            professional_id=output.professional_id,
            user_id=None,
            name=output.name,
            phone=output.phone,
            is_active=True,
        ),
    )


@router.delete(
    "/{professional_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a professional from a business",
    description="Soft-delete a professional (marks them as inactive).",
)
async def delete_professional(
    business_id: UUID,
    professional_id: UUID,
    professionals: Annotated[ProfessionalRepository, Depends(get_professional_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = DeleteProfessionalUseCase(professionals=professionals, uow=uow)
    output: DeleteProfessionalOutput = await use_case.execute(
        DeleteProfessionalInput(professional_id=professional_id)
    )
    return success_response(
        message="Professional removed successfully",
        code="PROFESSIONAL_DELETED",
        data={"professional_id": str(output.professional_id), "deleted": output.deleted},
    )
