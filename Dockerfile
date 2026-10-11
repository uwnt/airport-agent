# syntax=docker/dockerfile:1
# Image for the web server. Two stages: the first installs the locked dependencies and the app
# into a virtual environment with uv; the second copies only that environment onto a clean Python,
# so build tools and caches never reach the final image.
#
# Build:  docker build --build-arg RELEASE_SHA="$(git rev-parse HEAD)" -t airport-agent .
# Run:    docker compose up --build   (see docker-compose.yml)

# Same Python patch version in both stages: the venv points at /usr/local/bin/python3.
ARG PYTHON_IMAGE=python:3.13.16-slim-trixie

# ---- Stage 1: build the virtual environment ----
FROM ${PYTHON_IMAGE} AS build

# uv pinned to the version that wrote uv.lock (and inside the build backend's range in pyproject).
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv

ENV UV_CACHE_DIR=/var/cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first: this layer is reused until pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/var/cache/uv \
    uv sync --locked --no-dev --no-editable --no-install-project

# Then the app itself, installed into the venv as a regular (non-editable) package.
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/var/cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- Stage 2: runtime ----
FROM ${PYTHON_IMAGE} AS runtime

ARG RELEASE_SHA=""
# The repository URL, passed in by CI (the image workflow), so it is not hard-coded here.
ARG SOURCE_URL=""
ENV RELEASE_SHA=${RELEASE_SHA} \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.revision="${RELEASE_SHA}" \
      org.opencontainers.image.title="airport-agent" \
      org.opencontainers.image.description="Chat agent that ranks US airports for terminal-expansion investment."

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

WORKDIR /app
# Only the venv: the app is installed inside it, so no source files are needed.
COPY --from=build --chown=app:app /app/.venv /app/.venv
# The data snapshot (/app/data) and the `refresh` command are added with the data pipeline (#14).

USER app

EXPOSE 8000

# slim has no curl, so the check uses Python's own HTTP client.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# 0.0.0.0 inside the container so the published port reaches it; docker-compose.yml publishes it
# on the host's localhost only.
CMD ["uvicorn", "airport_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
