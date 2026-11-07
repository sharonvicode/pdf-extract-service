"""Contract tests for docker-compose.yml: how Traefik finds and protects the extractor replicas.

Each replica registers itself in Consul with the tags from CONSUL_SERVICE_TAGS,
and Traefik reads its configuration from those tags, so these tests read the
tags the same way Traefik does.
"""
import json
from pathlib import Path

import pytest
import yaml

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker-compose.yml"
CIRCUIT_BREAKER = "extractor-circuit-breaker"
CIRCUIT_BREAKER_PREFIX = f"traefik.http.middlewares.{CIRCUIT_BREAKER}.circuitbreaker"
EXTRACTOR_ROUTERS = ("extractor", "extractor-tls")


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def traefik(compose) -> dict:
    return compose["services"]["traefik"]


@pytest.fixture(scope="module")
def extractor(compose) -> dict:
    return compose["services"]["extractor"]


@pytest.fixture(scope="module")
def extractor_tags(extractor) -> dict[str, str]:
    tags = json.loads(extractor["environment"]["CONSUL_SERVICE_TAGS"])
    return dict(tag.split("=", 1) for tag in tags)


class TestServiceDiscovery:
    def test_traefik_discovers_the_replicas_through_consul(self, traefik):
        assert "--providers.consulcatalog.endpoint.address=consul:8500" in traefik["command"]

    def test_traefik_stops_routing_to_a_replica_as_soon_as_it_leaves(self, traefik):
        # By default Traefik polls Consul every 15 s, and meanwhile keeps sending
        # requests to a replica that already deregistered. Watching reacts at once.
        assert "--providers.consulcatalog.watch=true" in traefik["command"]

    def test_traefik_only_routes_services_that_ask_for_it(self, traefik, extractor_tags):
        assert "--providers.consulcatalog.exposedByDefault=false" in traefik["command"]
        assert extractor_tags["traefik.enable"] == "true"

    def test_traefik_has_no_access_to_the_docker_api(self, traefik):
        # Reading Docker labels required mounting /var/run/docker.sock, which gives
        # control over Docker. With Consul, Traefik no longer needs it.
        assert not any(flag.startswith("--providers.docker") for flag in traefik["command"])
        assert not any("docker.sock" in volume for volume in traefik.get("volumes", []))

    def test_replicas_register_in_consul(self, extractor):
        assert extractor["environment"]["CONSUL_URL"] == "http://consul:8500"

    def test_replicas_start_once_consul_is_healthy(self, compose, extractor):
        assert "healthcheck" in compose["services"]["consul"]
        assert extractor["depends_on"]["consul"]["condition"] == "service_healthy"


class TestCircuitBreaker:
    def test_a_hung_replica_counts_as_a_failure(self, traefik):
        # Without a timeout Traefik waits forever on a replica that does not answer, so the
        # failure is never counted and the circuit never opens. Under the load tests legitimate
        # requests took up to 44 s (queued by backpressure), and k6 gives up at 60 s.
        assert "--serversTransport.forwardingTimeouts.responseHeaderTimeout=60s" in traefik["command"]

    def test_opens_only_on_network_errors(self, extractor_tags):
        # The extractor answers 503 on purpose when its queue is full (backpressure).
        # Counting those 503 would open the circuit exactly under load, so only
        # network errors (replicas down or not answering) may open it.
        expression = extractor_tags[f"{CIRCUIT_BREAKER_PREFIX}.expression"]

        assert expression == "NetworkErrorRatio() > 0.50"

    def test_stays_open_and_recovers_for_a_set_window(self, extractor_tags):
        assert extractor_tags[f"{CIRCUIT_BREAKER_PREFIX}.fallbackDuration"] == "10s"
        assert extractor_tags[f"{CIRCUIT_BREAKER_PREFIX}.recoveryDuration"] == "10s"

    @pytest.mark.parametrize("router", EXTRACTOR_ROUTERS)
    def test_protects_every_router(self, extractor_tags, router):
        middlewares = extractor_tags.get(f"traefik.http.routers.{router}.middlewares", "")

        assert CIRCUIT_BREAKER in middlewares.split(",")
