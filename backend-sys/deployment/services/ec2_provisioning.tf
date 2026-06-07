# Create EC2 Instance for Kafka Broker
resource "aws_instance" "sahayak_kafka" {
  ami                    = var.ami
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.kafka_security_group_ids
  key_name               = var.key_name

  # Allocate 20GB block storage
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # Provisioning script (User Data) to set up Docker, and run Kafka Broker
  user_data = <<-EOF
              #!/bin/bash
              set -ex

              # Configure 2GB of Swap space to prevent OOM errors on t3.micro (1GB RAM)
              fallocate -l 2G /swapfile
              chmod 600 /swapfile
              mkswap /swapfile
              swapon /swapfile
              echo '/swapfile none swap sw 0 0' >> /etc/fstab

              # 1. Update package registry and install common utils
              apt-get update -y
              apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

              # 2. Add Docker's official GPG key and repository
              mkdir -p /etc/apt/keyrings
              curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
              echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

              # 3. Install Docker CE and Docker Compose plugin
              apt-get update -y
              apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

              # 4. Enable and start Docker service
              systemctl enable docker
              systemctl start docker

              # 5. Create application structure
              mkdir -p /app
              cd /app

              # Get private IP dynamically (wait if network interface is not fully up yet)
              PRIVATE_IP=""
              while [ -z "$PRIVATE_IP" ]; do
                PRIVATE_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || hostname -I | awk '{print $1}')
                [ -z "$PRIVATE_IP" ] && sleep 1
              done

              # 6. Write docker-compose.yml for Kafka only
              cat << COMPOSE_EOF > docker-compose.yml
              version: '3.8'

              services:
                kafka:
                  image: confluentinc/cp-kafka:7.6.0
                  container_name: sahayak-kafka
                  ports:
                    - "9092:9092"
                  environment:
                    KAFKA_NODE_ID: 1
                    KAFKA_PROCESS_ROLES: 'broker,controller'
                    KAFKA_CONTROLLER_QUORUM_VOTERS: '1@localhost:29093'
                    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093
                    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://$PRIVATE_IP:9092
                    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT'
                    KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
                    KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
                    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
                    KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
                    KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
                    KAFKA_LOG_DIRS: '/var/lib/kafka/data'
                    CLUSTER_ID: '4L62xkiaTFaJZtEPPItygg'
                    KAFKA_HEAP_OPTS: '-Xmx256m -Xms128m'
                  volumes:
                    - kafka_data:/var/lib/kafka/data
                  restart: unless-stopped

              volumes:
                kafka_data:
                  driver: local
              COMPOSE_EOF

              # 7. Pull and spin up containers
              docker compose up -d
              EOF

  tags = {
    Name = "sahayak-kafka-broker"
  }
}

# Create EC2 Instance for Application Services (API Gateway, Auth, ChatAI, Workers)
resource "aws_instance" "sahayak_server" {
  ami                    = var.ami
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.vpc_security_group_ids
  key_name               = var.key_name

  # Allocate 20GB block storage
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # Provisioning script (User Data) to set up Docker, Docker Compose, Nginx, and Start App
  user_data = <<-EOF
              #!/bin/bash
              set -ex

              # Configure 2GB of Swap space to prevent OOM errors on t3.micro (1GB RAM)
              fallocate -l 2G /swapfile
              chmod 600 /swapfile
              mkswap /swapfile
              swapon /swapfile
              echo '/swapfile none swap sw 0 0' >> /etc/fstab

              # 1. Update package registry and install common utils + nginx
              apt-get update -y
              apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release nginx git

              # 2. Add Docker's official GPG key and repository
              mkdir -p /etc/apt/keyrings
              curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
              echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

              # 3. Install Docker CE and Docker Compose plugin
              apt-get update -y
              apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

              # 4. Enable and start Docker service
              systemctl enable docker
              systemctl start docker

              # 5. Create application structure
              mkdir -p /app
              cd /app

              # 6. Write docker-compose.yml file
              cat << 'COMPOSE_EOF' > docker-compose.yml
              version: '3.8'

              services:
                kafka-ui:
                  image: provectuslabs/kafka-ui:latest
                  container_name: sahayak-kafka-ui
                  ports:
                    - "8080:8080"
                  environment:
                    KAFKA_CLUSTERS_0_NAME: "sahayak-single-node-cluster"
                    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: "${aws_instance.sahayak_kafka.private_ip}:9092"
                    DYNAMIC_CONFIG_ENABLED: 'true'
                  restart: unless-stopped

                api_gateway:
                  image: sugam2060/sahayak-api-gateway:latest
                  container_name: sahayak-api-gateway
                  ports:
                    - "8000:8000"
                  env_file:
                    - .env
                  environment:
                    - AUTH_SERVICE_ADDR=auth_service:50051
                    - CHATAI_SERVICE_ADDR=chatai_service:50052
                    - WORKERS_SERVICE_ADDR=workers:50053
                    - KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092
                  depends_on:
                    auth_service:
                      condition: service_started
                    chatai_service:
                      condition: service_started
                    workers:
                      condition: service_started
                  restart: unless-stopped

                auth_service:
                  image: sugam2060/sahayak-auth-service:latest
                  container_name: sahayak-auth-service
                  expose:
                    - "50051"
                  env_file:
                    - .env
                  environment:
                    - KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092
                    - WORKERS_SERVICE_ADDR=workers:50053
                    - CHATAI_SERVICE_ADDR=chatai_service:50052
                  restart: unless-stopped

                chatai_service:
                  image: sugam2060/sahayak-chatai-service:latest
                  container_name: sahayak-chatai-service
                  expose:
                    - "50052"
                  env_file:
                    - .env
                  environment:
                    - KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092
                    - WORKERS_SERVICE_ADDR=workers:50053
                  restart: unless-stopped

                workers:
                  image: sugam2060/sahayak-workers:latest
                  container_name: sahayak-workers
                  expose:
                    - "50053"
                  env_file:
                    - .env
                  environment:
                    - KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092
                  restart: unless-stopped
              COMPOSE_EOF

              # 7. Write the provided .env file contents, substituting localhost:9092 with the remote Kafka private IP
              cat << 'ENV_EOF' > .env
              ${replace(replace(var.env_file_content, "KAFKA_BOOTSTRAP_SERVERS=localhost:9092,localhost:9093,localhost:9094", "KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092"), "KAFKA_BOOTSTRAP_SERVERS=localhost:9092", "KAFKA_BOOTSTRAP_SERVERS=${aws_instance.sahayak_kafka.private_ip}:9092")}
              ENV_EOF

              # 8. Configure Nginx proxying port 80 to port 8000 (API Gateway)
              cat << 'NGINX_EOF' > /etc/nginx/sites-available/default
              server {
                  listen 80;
                  server_name _;

                  # Max payload upload size limit
                  client_max_body_size 20M;

                  location / {
                      proxy_pass http://localhost:8000;
                      proxy_set_header Host $host;
                      proxy_set_header X-Real-IP $remote_addr;
                      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                      proxy_set_header X-Forwarded-Proto $scheme;

                      # WebSocket proxy headers (essential for WebSocket chat features)
                      proxy_http_version 1.1;
                      proxy_set_header Upgrade $http_upgrade;
                      proxy_set_header Connection "upgrade";
                      
                      # Disable cache for real-time operations
                      proxy_cache_bypass $http_upgrade;
                  }
              }
              NGINX_EOF

              # 9. Restart Nginx to apply changes
              systemctl restart nginx

              # 10. Pull and spin up containers
              docker compose up -d
              EOF

  tags = {
    Name = "sahayak-backend-server"
  }
}
