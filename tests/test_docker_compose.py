"""Contract tests for docker-compose.yml: how Traefik protects the extractor replicas.

Traefik is configured through the extractor's Docker labels, so these tests
read the labels the same way Traefik does.
"""
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
def extractor_labels(compose) -> dict[str, str]:
    labels = compose["services"]["extractor"]["labels"]
    return dict(label.split("=", 1) for label in labels)


class TestCircuitBreaker:
    def test_a_hung_replica_counts_as_a_failure(self, compose):
        # Without a timeout Traefik waits forever on a replica that does not answer, so the
        # failure is never counted and the circuit never opens. Under the load tests legitimate
        # requests took up to 44 s (queued by backpressure), and k6 gives up at 60 s.
        command = compose["services"]["traefik"]["command"]

        assert "--serversTransport.forwardingTimeouts.responseHeaderTimeout=60s" in command

    def test_opens_only_on_network_errors(self, extractor_labels):
        # The extractor answers 503 on purpose when its queue is full (backpressure).
        # Counting those 503 would open the circuit exactly under load, so only
        # network errors (replicas down or not answering) may open it.
        expression = extractor_labels[f"{CIRCUIT_BREAKER_PREFIX}.expression"]

        assert expression == "NetworkErrorRatio() > 0.50"

    def test_stays_open_and_recovers_for_a_set_window(self, extractor_labels):
        assert extractor_labels[f"{CIRCUIT_BREAKER_PREFIX}.fallbackDuration"] == "10s"
        assert extractor_labels[f"{CIRCUIT_BREAKER_PREFIX}.recoveryDuration"] == "10s"

    @pytest.mark.parametrize("router", EXTRACTOR_ROUTERS)
    def test_protects_every_router(self, extractor_labels, router):
        middlewares = extractor_labels.get(f"traefik.http.routers.{router}.middlewares", "")

        assert CIRCUIT_BREAKER in middlewares.split(",")
