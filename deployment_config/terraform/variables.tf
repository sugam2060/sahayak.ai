variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "ap-south-1"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance size for free-tier eligible prototype"
  default     = "t3.micro"
}

variable "project_name" {
  type        = string
  description = "Project name prefix for tags"
  default     = "sahayak-ai"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

# SSH Key configuration (redundant since we are using static id_ed25519, but kept for compatibility)
variable "key_name" {
  type        = string
  description = "Optional pre-existing SSH key pair name."
  default     = ""
}
