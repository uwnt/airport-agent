# syntax=docker/dockerfile:1
# One image, two commands: the web server (default) and `airport-agent refresh`, which builds a
# new data snapshot (see docker-compose.yml). Two stages: the first installs the locked dependencies and the app
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

# The repository URL, passed in by CI (the image workflow), so it is not hard-coded here.
ARG SOURCE_URL=""
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.title="airport-agent" \
      org.opencontainers.image.description="Chat agent that ranks US airports for terminal-expansion investment."

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

WORKDIR /app
# Only the venv: the app is installed inside it, so no source files are needed.
COPY --from=build --chown=app:app /app/.venv /app/.venv
# Settings, the friction constraints scoring reads, the verified domain notes the profile tool
# quotes (found at docs/DOMAIN_NOTES.md from the working folder), the committed data snapshots
# and the OpenSky sample `refresh` falls back on. The app reads them relative to /app (DATA_STORE defaults to
# file://data/snapshots); `airport-agent refresh` (on the venv's PATH) writes new snapshots there
# and its downloads to /app/data/cache.
COPY --chown=app:app config ./config
COPY --chown=app:app docs/DOMAIN_NOTES.md ./docs/
COPY --chown=app:app data/constraints.yaml ./data/
COPY --chown=app:app data/snapshots ./data/snapshots
COPY --chown=app:app data/samples/opensky_departures_panc.json ./data/samples/
RUN mkdir -p /app/data/cache && chown -R app:app /app/data

# The commit last, so a new commit only rebuilds the layers below.
ARG RELEASE_SHA=""
ENV RELEASE_SHA=${RELEASE_SHA}
LABEL org.opencontainers.image.revision="${RELEASE_SHA}"

USER app

EXPOSE 8000

# slim has no curl, so the check uses Python's own HTTP client.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# 0.0.0.0 inside the container so the published port reaches it; docker-compose.yml publishes it
# on the host's localhost only.
CMD ["uvicorn", "airport_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
