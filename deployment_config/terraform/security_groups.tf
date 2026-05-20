resource "aws_security_group" "api_gateway" {
  name        = "${var.project_name}-gateway-sg"
  description = "Security group for API Gateway"
  vpc_id      = data.aws_vpc.default.id

  # HTTP API Gateway ingress
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH ingress
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-gateway-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "auth_service" {
  name        = "${var.project_name}-auth-sg"
  description = "Security group for gRPC Auth Service"
  vpc_id      = data.aws_vpc.default.id

  # gRPC ingress from Gateway only
  ingress {
    from_port       = 50051
    to_port         = 50051
    protocol        = "tcp"
    security_groups = [aws_security_group.api_gateway.id]
  }

  # SSH ingress
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-auth-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "chatai_service" {
  name        = "${var.project_name}-chatai-sg"
  description = "Security group for gRPC ChatAI Service"
  vpc_id      = data.aws_vpc.default.id

  # gRPC ingress from Gateway only
  ingress {
    from_port       = 50052
    to_port         = 50052
    protocol        = "tcp"
    security_groups = [aws_security_group.api_gateway.id]
  }

  # SSH ingress
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-chatai-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "celery_worker" {
  name        = "${var.project_name}-celery-sg"
  description = "Security group for Celery Worker"
  vpc_id      = data.aws_vpc.default.id

  # SSH ingress
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-celery-sg"
    Environment = var.environment
  }
}
