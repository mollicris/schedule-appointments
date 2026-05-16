from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class UseCase(ABC, Generic[TInput, TOutput]):
    """Base class for application use cases.

    Each use case implements exactly **one** business operation. The
    ``execute`` method takes a typed input DTO and returns a typed output DTO.

    Design rules:
    - One use case per file.
    - Dependencies (repositories, services) injected via ``__init__``.
    - No HTTP, FastAPI, or persistence concerns leak in here.
    - Application-level invariants and orchestration only — domain rules
      live in entities/value objects.
    """

    @abstractmethod
    async def execute(self, input_data: TInput) -> TOutput: ...
