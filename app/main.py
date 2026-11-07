"""Application factory and entrypoint for the Extractor microservice."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import extract
from app.api.error_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.service_registry import ConsulRegistry, ServiceRegistryError, build_registration

logger = logging.getLogger(__name__)


def _consul_lifespan(settings: Settings):
    """Register the replica in Consul on startup and deregister it on shutdown."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.consul_url is None:
            yield
            return

        registry = ConsulRegistry(settings.consul_url)
        registration = build_registration(settings)
        # Fail fast: a replica Traefik cannot discover would never receive traffic.
        registry.register(registration)
        try:
            yield
        finally:
            try:
                registry.deregister(registration.service_id)
            except ServiceRegistryError:
                # Consul drops it anyway once its health check stays critical.
                logger.warning("No se pudo dar de baja la réplica en Consul", exc_info=True)

    return lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Microservicio independiente que extrae el texto de archivos PDF.",
        lifespan=_consul_lifespan(settings),
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(extract.router, tags=["extraccion"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
