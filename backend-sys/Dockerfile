# ====================================================
# --- Stage 1: Build & Dependency Cache ---
# ====================================================
FROM python:3.12-slim-bookworm AS builder

# Install Astral UV for high-speed dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy lock and project metadata to cache dependency installation layers
COPY pyproject.toml uv.lock ./

# Sync dependencies (excluding dev dependencies)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ====================================================
# --- Stage 2: Core Production Base (Shared Code) ---
# ====================================================
FROM python:3.12-slim-bookworm AS prd-base
WORKDIR /app

# Copy virtual environment containing compiled packages from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Ensure Python looks at the root folder for absolute module imports
ENV PYTHONPATH="/app"

# Copy the entire codebase so local shared files (e.g., `shared/`) are accessible
COPY . .


# ====================================================
# --- Stage 3: API Gateway Image ---
# ====================================================
FROM prd-base AS api_gateway
EXPOSE 8000
CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ====================================================
# --- Stage 4: Auth Service Image (gRPC) ---
# ====================================================
FROM prd-base AS auth_service
EXPOSE 50051
CMD ["python", "-m", "services.auth_service.main"]


# ====================================================
# --- Stage 5: Chat AI Service Image (gRPC) ---
# ====================================================
FROM prd-base AS chatai_service
EXPOSE 50052
# Points explicitly to the dashed folder path on your disk setup
CMD ["python", "-m", "services.chatai-service.main"]


# ====================================================
# --- Stage 6: Workers Image (gRPC / Consumer Loops) ---
# ====================================================
FROM prd-base AS workers
EXPOSE 50053
CMD ["python", "-m", "services.workers.main"]