"""Tests for the registration of each replica in Consul (service discovery).

A fake Consul answers over real HTTP, so the tests check the requests the
service actually sends to Consul's agent API.
"""
import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.service_registry import ConsulRegistry, ServiceRegistration, ServiceRegistryError, build_registration
from app.main import create_app

REGISTRATION = ServiceRegistration(
    service_id="extractor-abc123",
    name="extractor",
    address="172.18.0.5",
    port=8000,
    tags=("traefik.enable=true",),
)


class _FakeConsulHandler(BaseHTTPRequestHandler):
    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else None
        self.server.received.append((self.path, body))
        self.send_response(self.server.status)
        self.end_headers()

    def log_message(self, *args):
        pass


class FakeConsul:
    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeConsulHandler)
        self._server.received = []
        self._server.status = 200
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def received(self) -> list[tuple[str, dict | None]]:
        return self._server.received

    def answer_with(self, status: int) -> None:
        self._server.status = status

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def consul():
    fake = FakeConsul()
    yield fake
    fake.stop()


@pytest.fixture
def settings_from_env(monkeypatch):
    """Let each test choose its environment: create_app reads the cached settings."""
    monkeypatch.delenv("CONSUL_URL", raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


class TestConsulRegistry:
    def test_registers_the_replica_with_a_health_check(self, consul):
        ConsulRegistry(consul.url).register(REGISTRATION)

        assert consul.received == [
            (
                "/v1/agent/service/register",
                {
                    "ID": "extractor-abc123",
                    "Name": "extractor",
                    "Address": "172.18.0.5",
                    "Port": 8000,
                    "Tags": ["traefik.enable=true"],
                    "Check": {
                        "HTTP": "http://172.18.0.5:8000/health",
                        "Interval": "10s",
                        "Timeout": "5s",
                        "DeregisterCriticalServiceAfter": "1m",
                    },
                },
            )
        ]

    def test_deregisters_the_replica(self, consul):
        ConsulRegistry(consul.url).deregister("extractor-abc123")

        assert consul.received == [("/v1/agent/service/deregister/extractor-abc123", None)]

    def test_rejected_registration_raises(self, consul):
        consul.answer_with(500)

        with pytest.raises(ServiceRegistryError):
            ConsulRegistry(consul.url).register(REGISTRATION)

    def test_unreachable_consul_raises(self):
        with pytest.raises(ServiceRegistryError):
            ConsulRegistry("http://127.0.0.1:1").register(REGISTRATION)


class TestBuildRegistration:
    def test_each_replica_registers_under_its_own_id_and_address(self, monkeypatch):
        monkeypatch.setattr(socket, "gethostname", lambda: "abc123")
        monkeypatch.setattr(socket, "gethostbyname", lambda host: {"abc123": "172.18.0.5"}[host])
        settings = Settings(_env_file=None, consul_service_tags=["traefik.enable=true"])

        assert build_registration(settings) == REGISTRATION


class TestAppLifespan:
    def test_registers_on_startup_and_deregisters_on_shutdown(self, consul, settings_from_env):
        settings_from_env.setenv("CONSUL_URL", consul.url)

        with TestClient(create_app()):
            assert [path for path, _ in consul.received] == ["/v1/agent/service/register"]

        assert consul.received[-1][0].startswith("/v1/agent/service/deregister/extractor-")

    def test_without_consul_url_the_replica_does_not_register(self, consul, settings_from_env):
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200

        assert consul.received == []

    def test_does_not_start_when_consul_is_unreachable(self, settings_from_env):
        settings_from_env.setenv("CONSUL_URL", "http://127.0.0.1:1")

        with pytest.raises(ServiceRegistryError):
            with TestClient(create_app()):
                pass

    def test_a_failed_deregistration_does_not_break_the_shutdown(self, consul, settings_from_env, caplog):
        settings_from_env.setenv("CONSUL_URL", consul.url)

        with caplog.at_level(logging.WARNING):
            with TestClient(create_app()):
                consul.answer_with(500)

        assert "Consul" in caplog.text
