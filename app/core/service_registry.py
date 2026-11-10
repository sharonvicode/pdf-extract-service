"""Service discovery: registers this replica in Consul so Traefik can find it.

Infrastructure only: the extraction logic knows nothing about Consul. The tags
(Traefik's routing configuration) come from the environment, so this module
does not know about Traefik either.
"""
import socket
from dataclasses import dataclass

import requests

from app.core.config import Settings

REQUEST_TIMEOUT_SECONDS = 5
# The port uvicorn listens on inside the container (Dockerfile CMD). It is fixed on
# purpose: the published port changes in the compose port mapping, and a configurable
# value here could drift from the real one and send Traefik's traffic nowhere.
SERVER_PORT = 8000


class ServiceRegistryError(Exception):
    """Consul could not be reached or rejected the request."""


@dataclass(frozen=True)
class ServiceRegistration:
    service_id: str
    name: str
    address: str
    port: int
    tags: tuple[str, ...]


def build_registration(settings: Settings) -> ServiceRegistration:
    """Describe this replica: its own id and address, so every replica registers apart."""
    hostname = socket.gethostname()
    return ServiceRegistration(
        service_id=f"{settings.consul_service_name}-{hostname}",
        name=settings.consul_service_name,
        address=socket.gethostbyname(hostname),
        port=SERVER_PORT,
        tags=tuple(settings.consul_service_tags),
    )


class ConsulRegistry:
    """Client of Consul's agent API for registering and deregistering services."""

    def __init__(self, consul_url: str) -> None:
        self._consul_url = consul_url.rstrip("/")

    def register(self, registration: ServiceRegistration) -> None:
        """Register the replica with an HTTP health check on its /health endpoint.

        Raises:
            ServiceRegistryError: if Consul cannot be reached or rejects the registration.
        """
        self._put(
            "/v1/agent/service/register",
            {
                "ID": registration.service_id,
                "Name": registration.name,
                "Address": registration.address,
                "Port": registration.port,
                "Tags": list(registration.tags),
                "Check": {
                    "HTTP": f"http://{registration.address}:{registration.port}/health",
                    "Interval": "10s",
                    "Timeout": "5s",
                    "DeregisterCriticalServiceAfter": "1m",
                },
            },
        )

    def deregister(self, service_id: str) -> None:
        """Remove the replica from Consul.

        Raises:
            ServiceRegistryError: if Consul cannot be reached or rejects the request.
        """
        self._put(f"/v1/agent/service/deregister/{service_id}")

    def _put(self, path: str, payload: dict | None = None) -> None:
        try:
            response = requests.put(f"{self._consul_url}{path}", json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ServiceRegistryError(f"Consul no respondió a {path}: {exc}") from exc
