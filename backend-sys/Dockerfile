# Use a lightweight python base image
FROM python:3.12-slim-bookworm AS builder

# Install Astral UV for fast build caching
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy lock and project metadata to cache dependencies installation
COPY pyproject.toml uv.lock ./

# Sync dependencies (excluding dev group)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- Final Production Image ---
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtual environment containing installed packages
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy codebase
COPY . .

# Default to API Gateway. Can be overridden in Docker commands for other services.
CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
