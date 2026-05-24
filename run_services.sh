#!/bin/bash

# Trap Ctrl+C (SIGINT) and exit signals to kill all background processes started by this script
trap 'echo "Stopping all services..."; kill $(jobs -p) 2>/dev/null' EXIT INT TERM

# Unset external VIRTUAL_ENV variable to prevent uv warnings about mismatched virtualenv paths
unset VIRTUAL_ENV


echo "=================================================="
echo "Starting Sahayak AI Development Environment"
echo "=================================================="

# 1. Run frontend-sys in dev mode
echo "--> Starting frontend-sys (Next.js)..."
(cd frontend-sys && npm run dev) &

# 2. Run backend auth_service
echo "--> Starting backend auth_service (gRPC)..."
(cd backend-sys && uv run -m services.auth_service.main) &

# 3. Run backend api_gateway
# Note: The folder is 'services/api_gateway', so we use 'services.api_gateway.main'
echo "--> Starting backend api_gateway (FastAPI)..."
(cd backend-sys && uv run -m services.api_gateway.main) &

# 4. Run Kafka worker for mail_service
echo "--> Starting Kafka worker for mail_service..."
(cd backend-sys && uv run -m services.workers.kafka_worker) &

# 5. Run backend chatai-service (Kafka-based Agent)
echo "--> Starting backend chatai-service (Kafka)..."
(cd backend-sys && uv run -m services.chatai-service.main) &

echo "=================================================="
echo "All services started. Press Ctrl+C to stop them all."
echo "=================================================="

# Wait for all background processes to finish
wait
