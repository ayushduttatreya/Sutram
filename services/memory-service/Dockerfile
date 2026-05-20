# Dockerfile
FROM python:3.11-slim AS base
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY app/ ./app/

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]

FROM base AS production
EXPOSE 8002
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
