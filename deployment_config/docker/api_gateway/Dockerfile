FROM python:3.12-slim AS builder

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy only the files needed for installing dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies without the project itself to cache this layer
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Final runtime image
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the shared components and gateway service files
COPY shared/ /app/shared/
COPY services/api_gateway/ /app/services/api_gateway/

EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.api_gateway.main"]
