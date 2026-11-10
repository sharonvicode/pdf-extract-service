# syntax=docker/dockerfile:1

# Two stages: uv is only needed to install the dependencies, so it stays in the
# builder stage. The final image carries only the virtualenv and the code: every
# tool it does not need at runtime is attack surface that grype reports.

# --- Build stage: installs the locked dependencies into /app/.venv ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Only the dependency files, so this layer stays cached across code changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project


# --- Final stage: what actually runs ---
# Same base as the builder: the virtualenv points to this image's Python.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# - apt-get upgrade: the official base image lags behind Debian's security fixes
#   (it shipped a zlib1g with two High CVEs already fixed upstream).
# - pip comes with the base image but is never used: the dependencies are installed with uv.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip \
    && useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# --chown while copying: a later `chown -R` would duplicate every file in a new layer
# (the image went from 700 MB to 333 MB).
COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
