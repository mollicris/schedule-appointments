from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.application.business.create_business import (
    CreateBusinessInput,
    CreateBusinessOutput,
    CreateBusinessUseCase,
)
from src.application.business.delete_business import (
    DeleteBusinessInput,
    DeleteBusinessOutput,
    DeleteBusinessUseCase,
)
from src.application.business.get_business import (
    GetBusinessInput,
    GetBusinessOutput,
    GetBusinessUseCase,
)
from src.application.business.list_businesses import (
    ListBusinessesInput,
    ListBusinessesOutput,
    ListBusinessesUseCase,
)
from src.application.business.update_business import (
    UpdateBusinessInput,
    UpdateBusinessOutput,
    UpdateBusinessUseCase,
)
from src.application.business.update_business_whatsapp import (
    UpdateBusinessWhatsappInput,
    UpdateBusinessWhatsappOutput,
    UpdateBusinessWhatsappUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.business.repository import BusinessRepository
from src.presentation.dependencies import (
    get_business_repository,
    get_unit_of_work,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response

router = APIRouter(prefix="/businesses", tags=["businesses"])


class CreateBusinessRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=20)
    slug: str | None = Field(default=None, max_length=127)
    timezone: str = Field(default="UTC", max_length=63)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None)
    description: str | None = Field(default=None)


class BusinessDetailResponse(BaseModel):
    business_id: UUID
    name: str
    slug: str
    phone: str
    email: str | None
    address: str | None
    description: str | None
    timezone: str
    is_active: bool
    whatsapp_phone_number_id: str | None = None
    owner_whatsapp: str | None = None
    has_whatsapp_app_secret: bool = False


class UpdateWhatsappRequest(BaseModel):
    phone_number_id: str | None = Field(default=None, max_length=64)
    app_secret: str | None = Field(default=None, max_length=255)
    owner_whatsapp: str | None = Field(default=None, max_length=20)


class WhatsappConfigResponse(BaseModel):
    business_id: UUID
    whatsapp_phone_number_id: str | None
    owner_whatsapp: str | None
    has_whatsapp_app_secret: bool


class BusinessSummaryResponse(BaseModel):
    business_id: UUID
    name: str
    slug: str
    phone: str
    is_active: bool


class UpdateBusinessRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None)
    description: str | None = Field(default=None)
    timezone: str | None = Field(default=None, max_length=63)


class CreateBusinessResponseData(BaseModel):
    business_id: UUID
    slug: str


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business",
    description="Create a new business for the authenticated tenant.",
)
async def create_business(
    payload: CreateBusinessRequest,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CreateBusinessUseCase(
        businesses=businesses,
        uow=uow,
    )
    output: CreateBusinessOutput = await use_case.execute(
        CreateBusinessInput(
            name=payload.name,
            phone=payload.phone,
            slug=payload.slug,
            timezone=payload.timezone,
            email=payload.email,
            address=payload.address,
            description=payload.description,
        )
    )
    return success_response(
        message="Business created successfully",
        code="BUSINESS_CREATED",
        data=CreateBusinessResponseData(
            business_id=output.business_id,
            slug=output.slug,
        ),
    )


@router.get(
    "/{business_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a business by ID",
    description="Retrieve details of a specific business for the authenticated tenant.",
)
async def get_business(
    business_id: UUID,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
) -> SuccessResponse:
    use_case = GetBusinessUseCase(businesses=businesses)
    output: GetBusinessOutput = await use_case.execute(GetBusinessInput(business_id=business_id))

    return success_response(
        message="Business retrieved successfully",
        code="BUSINESS_FOUND",
        data=BusinessDetailResponse(
            business_id=output.business_id,
            name=output.name,
            slug=output.slug,
            phone=output.phone,
            email=output.email,
            address=output.address,
            description=output.description,
            timezone=output.timezone,
            is_active=output.is_active,
            whatsapp_phone_number_id=output.whatsapp_phone_number_id,
            owner_whatsapp=output.owner_whatsapp,
            has_whatsapp_app_secret=output.has_whatsapp_app_secret,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List all active businesses",
    description="Retrieve a paginated list of active businesses for the authenticated tenant.",
)
async def list_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListBusinessesUseCase(businesses=businesses)
    output: ListBusinessesOutput = await use_case.execute(
        ListBusinessesInput(page=page, page_size=page_size)
    )

    return paginated_response(
        data=[
            BusinessSummaryResponse(
                business_id=b.business_id,
                name=b.name,
                slug=b.slug,
                phone=b.phone,
                is_active=b.is_active,
            )
            for b in output.businesses
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@router.put(
    "/{business_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a business",
    description="Update the details of an existing business.",
)
async def update_business(
    business_id: UUID,
    payload: UpdateBusinessRequest,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateBusinessUseCase(businesses=businesses, uow=uow)
    output: UpdateBusinessOutput = await use_case.execute(
        UpdateBusinessInput(
            business_id=business_id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            description=payload.description,
            timezone=payload.timezone,
        )
    )
    return success_response(
        message="Business updated successfully",
        code="BUSINESS_UPDATED",
        data=BusinessSummaryResponse(
            business_id=output.business_id,
            name=output.name,
            slug=output.slug,
            phone=output.phone,
            is_active=True,
        ),
    )


@router.patch(
    "/{business_id}/whatsapp",
    status_code=status.HTTP_200_OK,
    summary="Configure WhatsApp integration",
    description="Set or update the WhatsApp Phone Number ID, app secret, and owner WhatsApp number for a business.",
)
async def update_business_whatsapp(
    business_id: UUID,
    payload: UpdateWhatsappRequest,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateBusinessWhatsappUseCase(businesses=businesses, uow=uow)
    output: UpdateBusinessWhatsappOutput = await use_case.execute(
        UpdateBusinessWhatsappInput(
            business_id=business_id,
            phone_number_id=payload.phone_number_id,
            app_secret=payload.app_secret,
            owner_whatsapp=payload.owner_whatsapp,
        )
    )
    return success_response(
        message="WhatsApp configuration updated successfully",
        code="WHATSAPP_CONFIGURED",
        data=WhatsappConfigResponse(
            business_id=output.business_id,
            whatsapp_phone_number_id=output.whatsapp_phone_number_id,
            owner_whatsapp=output.owner_whatsapp,
            has_whatsapp_app_secret=output.has_whatsapp_app_secret,
        ),
    )


@router.delete(
    "/{business_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a business",
    description="Soft-delete a business (marks it as inactive).",
)
async def delete_business(
    business_id: UUID,
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = DeleteBusinessUseCase(businesses=businesses, uow=uow)
    output: DeleteBusinessOutput = await use_case.execute(
        DeleteBusinessInput(business_id=business_id)
    )
    return success_response(
        message="Business deleted successfully",
        code="BUSINESS_DELETED",
        data={"business_id": str(output.business_id), "deleted": output.deleted},
    )
