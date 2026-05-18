"""ORM models for all bounded contexts.

These models are registered on Base.metadata and used by Alembic
for auto-generating migrations. Each model corresponds to a domain
aggregate root or supporting entity.

Mapper functions in ``infrastructure/persistence/mappers.py`` translate
between ORM models (persistence) and domain entities (business logic).
"""

from src.infrastructure.persistence.models.appointment import AppointmentModel
from src.infrastructure.persistence.models.business import (
    BusinessHourModel,
    BusinessModel,
    ProfessionalModel,
    ServiceModel,
    ServiceProfessionalModel,
)
from src.infrastructure.persistence.models.client import ClientModel
from src.infrastructure.persistence.models.conversation import ConversationModel, HumanTransferModel, MessageModel
from src.infrastructure.persistence.models.identity import UserModel
from src.infrastructure.persistence.models.tenants import TenantModel

__all__ = [
    "TenantModel",
    "UserModel",
    "BusinessModel",
    "ServiceModel",
    "ProfessionalModel",
    "ServiceProfessionalModel",
    "BusinessHourModel",
    "AppointmentModel",
    "ClientModel",
    "ConversationModel",
    "MessageModel",
    "HumanTransferModel",
]
