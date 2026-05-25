# services/observability-service/Dockerfile
FROM python:3.11-slim AS base
WORKDIR /app

RUN useradd --system --no-create-home --uid 1001 appuser
RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY uv.lock .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY app/ ./app/

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project
USER appuser
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--reload"]

FROM base AS production
EXPOSE 8003
USER appuser
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
