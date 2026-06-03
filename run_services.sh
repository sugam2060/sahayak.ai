#!/bin/bash

# Trap Ctrl+C (SIGINT) and exit signals to kill all background processes started by this script
trap 'echo "Stopping all services..."; kill $(jobs -p) 2>/dev/null' EXIT INT TERM

# Unset external VIRTUAL_ENV variable to prevent uv warnings about mismatched virtualenv paths
unset VIRTUAL_ENV

# Detect appropriate command to run python services (uv or virtualenv python)
if command -v uv &> /dev/null; then
  PYTHON_CMD="uv run"
else
  if [ -f "backend-sys/.venv/Scripts/python" ]; then
    PYTHON_CMD=".venv/Scripts/python"
  elif [ -f "backend-sys/.venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
  else
    PYTHON_CMD="python"
  fi
fi

echo "=================================================="
echo "Starting Sahayak AI Development Environment"
echo "Using command: $PYTHON_CMD"
echo "=================================================="

# 1. Run frontend-sys in dev mode
echo "--> Starting frontend-sys (Next.js)..."
(cd frontend-sys && npm run dev) &

# 2. Run backend auth_service
echo "--> Starting backend auth_service (gRPC)..."
(cd backend-sys && $PYTHON_CMD -m services.auth_service.main) &

# 3. Run backend api_gateway
# Note: The folder is 'services/api_gateway', so we use 'services.api_gateway.main'
echo "--> Starting backend api_gateway (FastAPI)..."
(cd backend-sys && $PYTHON_CMD -m services.api_gateway.main) &

# 4. Run Kafka worker for mail_service
echo "--> Starting Kafka worker for mail_service..."
(cd backend-sys && $PYTHON_CMD -m services.workers.main) &

# 5. Run backend chatai-service (Kafka-based Agent)
echo "--> Starting backend chatai-service (Kafka)..."
(cd backend-sys && $PYTHON_CMD -m services.chatai-service.main) &

echo "=================================================="
echo "All services started. Press Ctrl+C to stop them all."
echo "=================================================="

# Wait for all background processes to finish
wait
