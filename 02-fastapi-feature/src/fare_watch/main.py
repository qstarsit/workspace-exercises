from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from fare_watch.clients.hermes import HttpHermesClient
from fare_watch.config import Settings
from fare_watch.exception_handlers import register_exception_handlers
from fare_watch.routers import airports, fares, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the shared Hermes HTTP connection pool and close it on shutdown.

    Args:
        app: The application being started.

    Yields:
        Control to the running application.
    """
    settings: Settings = app.state.settings
    async with httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=settings.timeout_seconds,
        headers=settings.request_headers,
    ) as http:
        app.state.hermes_client = HttpHermesClient(http)
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Args:
        settings: Settings to use; read from the environment when omitted.

    Returns:
        The configured application.
    """
    app = FastAPI(title="Fare Watch", lifespan=lifespan)
    app.state.settings = settings or Settings()
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(airports.router)
    app.include_router(fares.router)
    return app


app = create_app()
