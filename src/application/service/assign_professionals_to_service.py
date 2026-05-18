from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class AssignProfessionalsToServiceInput:
    service_id: UUID
    professional_ids: list[UUID]


@dataclass(frozen=True)
class AssignProfessionalsToServiceOutput:
    service_id: UUID
    professional_ids: list[UUID]


class AssignProfessionalsToServiceUseCase(
    UseCase[AssignProfessionalsToServiceInput, AssignProfessionalsToServiceOutput]
):
    """Replace the set of professionals that can perform a given service.

    Validates:
      - The service exists.
      - Every professional exists, belongs to the same business as the service, and is active.
    """

    def __init__(
        self,
        services: ServiceRepository,
        professionals: ProfessionalRepository,
        uow: UnitOfWork,
    ) -> None:
        self._services = services
        self._professionals = professionals
        self._uow = uow

    async def execute(
        self, input_data: AssignProfessionalsToServiceInput
    ) -> AssignProfessionalsToServiceOutput:
        async with self._uow:
            service = await self._services.get_by_id(input_data.service_id)
            if not service:
                raise NotFoundError(f"Service {input_data.service_id} not found")

            unique_ids = list({pid for pid in input_data.professional_ids})

            for pid in unique_ids:
                professional = await self._professionals.get_by_id(pid)
                if not professional:
                    raise NotFoundError(f"Professional {pid} not found")
                if professional.business_id != service.business_id:
                    raise ValidationError(
                        f"Professional {pid} does not belong to this business"
                    )
                if not professional.is_active:
                    raise ValidationError(f"Professional {pid} is inactive")

            await self._services.set_professionals(service.id, unique_ids)
            await self._uow.commit()

        return AssignProfessionalsToServiceOutput(
            service_id=service.id,
            professional_ids=unique_ids,
        )
