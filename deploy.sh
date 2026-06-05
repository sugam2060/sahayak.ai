#!/bin/bash
set -e

# Configuration
DEVICES_DIR="backend-sys"
DEPLOY_DIR="$DEVICES_DIR/deployment"
KEY_FILE="$DEPLOY_DIR/aws-key"
DOCKER_USER="sugam2060"

# Fix permissions issue on WSL/Linux where mounted NTFS permissions are too open
if [ -f "$KEY_FILE" ]; then
  cp "$KEY_FILE" /tmp/aws-key
  chmod 600 /tmp/aws-key
  KEY_FILE="/tmp/aws-key"
fi

# Fetch EC2 Public IP dynamically from Terraform outputs
echo "--> Fetching EC2 public IP from Terraform outputs..."
TF_CMD="terraform"
if ! command -v terraform &> /dev/null && command -v terraform.exe &> /dev/null; then
  TF_CMD="terraform.exe"
fi

if ! EC2_IP=$($TF_CMD -chdir="$DEPLOY_DIR" output -raw public_ip 2>/dev/null); then
  echo "Error: Could not retrieve public IP from Terraform. Make sure 'terraform apply' has run successfully."
  exit 1
fi
echo "--> Target EC2 IP: $EC2_IP"

# Check if a target service argument is provided
SERVICE=$1
if [ -z "$SERVICE" ]; then
  echo "Usage: ./deploy.sh [api_gateway|auth_service|chatai_service|workers|all]"
  exit 1
fi

build_and_push() {
  local target=$1
  local image_name=$2
  
  echo "=================================================="
  echo "Building and Pushing target: $target -> $image_name"
  echo "=================================================="
  
  # Build from the backend-sys context
  docker build --platform linux/amd64 --target "$target" -t "$DOCKER_USER/$image_name:latest" "$DEVICES_DIR"
  
  # Push to Docker Hub
  docker push "$DOCKER_USER/$image_name:latest"
}

# Run build and push based on the service argument
case "$SERVICE" in
  api_gateway)
    build_and_push "api_gateway" "sahayak-api-gateway"
    ;;
  auth_service)
    build_and_push "auth_service" "sahayak-auth-service"
    ;;
  chatai_service)
    build_and_push "chatai_service" "sahayak-chatai-service"
    ;;
  workers)
    build_and_push "workers" "sahayak-workers"
    ;;
  all)
    build_and_push "api_gateway" "sahayak-api-gateway"
    build_and_push "auth_service" "sahayak-auth-service"
    build_and_push "chatai_service" "sahayak-chatai-service"
    build_and_push "workers" "sahayak-workers"
    ;;
  *)
    echo "Unknown service: $SERVICE"
    echo "Available choices: api_gateway, auth_service, chatai_service, workers, all"
    exit 1
    ;;
esac

# SSH and deploy on the remote instance
echo "=================================================="
echo "Connecting to EC2 to pull and restart containers..."
echo "=================================================="

# echo "--> Copying updated docker-compose.yml to remote server..."
# scp -i "$KEY_FILE" -o StrictHostKeyChecking=no "$DEVICES_DIR/docker-compose.yml" "ubuntu@$EC2_IP:/app/docker-compose.yml"

# SSH, bypass prompt, and run remote commands
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "ubuntu@$EC2_IP" << 'EOF'
  cd /app
  echo "--> Pulling latest Docker images..."
  sudo docker compose pull
  echo "--> Restarting Docker Compose services..."
  sudo docker compose up -d --remove-orphans
  echo "--> Deployment complete!"
  sudo docker ps
EOF
