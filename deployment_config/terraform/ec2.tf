# Retrieve the latest Ubuntu 22.04 AMI
data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

# SSH Key Pair generation (fallback if key_name is not provided)
resource "tls_private_key" "key" {
  count     = var.key_name == "" ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "generated" {
  count      = var.key_name == "" ? 1 : 0
  key_name   = "${var.project_name}-ssh-key"
  public_key = tls_private_key.key[0].public_key_openssh
}

locals {
  selected_key_name = var.key_name != "" ? var.key_name : aws_key_pair.generated[0].key_name
}

# IAM Role & Policy for ECR read-only access
resource "aws_iam_role" "ec2_ecr_role" {
  name = "${var.project_name}-ec2-ecr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  role       = aws_iam_role.ec2_ecr_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-instance-profile"
  role = aws_iam_role.ec2_ecr_role.name
}

# 1. API Gateway Instance
resource "aws_instance" "api_gateway" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = element(data.aws_subnets.default.ids, 0)
  key_name             = local.selected_key_name
  vpc_security_group_ids = [aws_security_group.api_gateway.id]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  # Basic startup script to install Docker
  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name        = "${var.project_name}-api-gateway"
    Environment = var.environment
  }
}

# 2. Auth Service Instance
resource "aws_instance" "auth_service" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = element(data.aws_subnets.default.ids, 0)
  key_name             = local.selected_key_name
  vpc_security_group_ids = [aws_security_group.auth_service.id]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name        = "${var.project_name}-auth-service"
    Environment = var.environment
  }
}

# 3. ChatAI Service Instance
resource "aws_instance" "chatai_service" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = element(data.aws_subnets.default.ids, 0)
  key_name             = local.selected_key_name
  vpc_security_group_ids = [aws_security_group.chatai_service.id]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name        = "${var.project_name}-chatai-service"
    Environment = var.environment
  }
}

# 4. Celery Worker Instance
resource "aws_instance" "celery_worker" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = element(data.aws_subnets.default.ids, 0)
  key_name             = local.selected_key_name
  vpc_security_group_ids = [aws_security_group.celery_worker.id]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name        = "${var.project_name}-celery-worker"
    Environment = var.environment
  }
}
