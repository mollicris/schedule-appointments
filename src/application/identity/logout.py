from __future__ import annotations

from dataclasses import dataclass

from src.application.shared.use_case import UseCase
from src.infrastructure.cache.redis_client import get_redis


@dataclass(frozen=True)
class LogoutInput:
    refresh_token: str


@dataclass(frozen=True)
class LogoutOutput:
    revoked: bool


class LogoutUseCase(UseCase[LogoutInput, LogoutOutput]):
    async def execute(self, input_data: LogoutInput) -> LogoutOutput:
        redis = await get_redis()
        deleted = await redis.delete(f"refresh:{input_data.refresh_token}")
        return LogoutOutput(revoked=deleted > 0)
