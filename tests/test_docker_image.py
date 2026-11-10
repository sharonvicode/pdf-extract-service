"""Tests for the production image: it carries only what the service needs to run.

They start containers of an already built image, so they are skipped unless
EXTRACTOR_IMAGE names it:

    docker build -t extractor-service:latest .
    EXTRACTOR_IMAGE=extractor-service:latest uv run pytest tests/test_docker_image.py
"""
import os
import subprocess

import pytest

IMAGE = os.getenv("EXTRACTOR_IMAGE")
# First zlib1g release that fixes CVE-2026-76844 and CVE-2026-85091 (High), reported by grype.
ZLIB_FIXED_VERSION = "1:1.3.dfsg+really1.3.1-1+deb13u1"

pytestmark = pytest.mark.skipif(IMAGE is None, reason="EXTRACTOR_IMAGE is not set")


def run_in_image(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", IMAGE, "-c", command],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestImageContents:
    """Every tool the service does not use at runtime is attack surface that grype reports."""

    def test_has_no_uv(self):
        # uv only installs the dependencies while building the image.
        assert run_in_image("command -v uv").returncode != 0

    def test_has_no_pip(self):
        # The base image ships pip in the system Python, but the dependencies are installed
        # with uv. Searched by its metadata, as grype finds it, wherever it is installed.
        result = run_in_image("find / -xdev -name 'pip-*.dist-info'")

        assert result.stdout == ""

    def test_zlib_has_the_security_fix(self):
        installed = "$(dpkg-query -W -f='${Version}' zlib1g)"

        result = run_in_image(f'dpkg --compare-versions "{installed}" ge "{ZLIB_FIXED_VERSION}"')

        assert result.returncode == 0


class TestImageRuntime:
    def test_the_application_and_its_dependencies_load(self):
        result = run_in_image("python -c 'import app.main'")

        assert result.returncode == 0, result.stderr

    def test_runs_as_a_non_root_user(self):
        assert run_in_image("id -u").stdout.strip() != "0"
