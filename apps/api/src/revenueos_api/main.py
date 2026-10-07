"""RevenueOS FastAPI application factory."""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from revenueos_shared.config import get_settings
from revenueos_shared.correlation import CorrelationIdMiddleware
from revenueos_shared.logging import configure_logging

from revenueos_api.routers import health

logger = logging.getLogger("revenueos.api")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings, service="api")

    app = FastAPI(
        title="RevenueOS API",
        version=settings.app_version,
        description="RevenueOS / AffiliateOS — V1A-0 bootstrap API",
        contact={"name": "RevenueOS"},
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)

    @app.get("/", tags=["meta"])
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "service": "revenueos-api",
                "phase": settings.phase,
                "version": settings.app_version,
                "environment": settings.environment,
                "docs": "/docs",
                "health": "/health",
                "time": datetime.now(timezone.utc).isoformat(),
            }
        )

    logger.info(
        "api app created",
        extra={"event": "app_created", "component": "api"},
    )
    return app


app = create_app()
