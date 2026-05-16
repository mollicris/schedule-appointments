from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.config.settings import get_settings
from src.infrastructure.config.logging import configure_logging
from src.presentation.api.v1.router import api_v1_router
from src.presentation.exception_handlers import register_exception_handlers
from src.presentation.middleware import TenantContextMiddleware
from src.presentation.webhooks.router import webhooks_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/webhooks")

    register_exception_handlers(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
