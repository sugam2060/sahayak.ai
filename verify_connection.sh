#!/bin/bash
set -e

# Configuration
DEVICES_DIR="backend-sys"
DEPLOY_DIR="$DEVICES_DIR/deployment"
KEY_FILE="$DEPLOY_DIR/aws-key"

echo "--> Fetching IPs from Terraform..."
TF_CMD="terraform"
if ! command -v terraform &> /dev/null && command -v terraform.exe &> /dev/null; then
  TF_CMD="terraform.exe"
fi

WEB_IP=$($TF_CMD -chdir="$DEPLOY_DIR" output -raw public_ip 2>/dev/null)
KAFKA_IP=$($TF_CMD -chdir="$DEPLOY_DIR" output -raw kafka_private_ip 2>/dev/null)

if [ -z "$WEB_IP" ] || [ -z "$KAFKA_IP" ]; then
  echo "Error: Could not retrieve IPs. Run terraform apply first."
  exit 1
fi

echo "--> Web Instance IP: $WEB_IP"
echo "--> Kafka Instance Private IP: $KAFKA_IP"

# Step 1: Copy private key to Web Instance
echo "--> Copying private key to web instance..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no "$KEY_FILE" "ubuntu@$WEB_IP:/home/ubuntu/.ssh/aws-key"

# Step 2: SSH into Web Instance and from there into Kafka Instance
echo "--> Connecting to Web Instance and attempting to SSH into Kafka Instance..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "ubuntu@$WEB_IP" -t << EOF
  chmod 600 /home/ubuntu/.ssh/aws-key
  echo "--> Successfully connected to Web Instance."
  echo "--> Attempting to SSH into Kafka Instance ($KAFKA_IP)..."
  ssh -i /home/ubuntu/.ssh/aws-key -o StrictHostKeyChecking=no "ubuntu@$KAFKA_IP" "echo '--> SUCCESSFULLY CONNECTED TO KAFKA INSTANCE!'; sudo docker ps"
EOF
