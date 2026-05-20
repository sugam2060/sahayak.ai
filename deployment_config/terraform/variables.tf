variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "ap-south-1"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance size for free-tier eligible prototype"
  default     = "t2.micro"
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

variable "key_name" {
  type        = string
  description = "Optional pre-existing SSH key pair name. If empty, a key will be created dynamically."
  default     = ""
}

# External resource configurations passed via TF variables or tfvars

variable "external_db_url" {
  type        = string
  description = "Database URL for PostgreSQL (postgresql+asyncpg://...)"
  default     = "postgresql+asyncpg://user:password@external-db-host:5432/sahayak"
}

variable "external_redis_url" {
  type        = string
  description = "Redis URL (redis://...)"
  default     = "redis://external-redis-host:6379/0"
}

variable "jwt_secret" {
  type        = string
  description = "JWT Token Signature Secret"
  default     = "super-secret-jwt-key"
}

variable "smtp_host" {
  type        = string
  description = "SMTP Host"
  default     = "smtp.gmail.com"
}

variable "smtp_port" {
  type        = number
  description = "SMTP Port"
  default     = 587
}

variable "smtp_user" {
  type        = string
  description = "SMTP Username"
  default     = ""
}

variable "smtp_password" {
  type        = string
  description = "SMTP Password"
  sensitive   = true
  default     = ""
}

variable "mail_from" {
  type        = string
  description = "Mail from address"
  default     = "no-reply@sahayak.com"
}

variable "frontend_url" {
  type        = string
  description = "Client Web URL"
  default     = "http://localhost:3000"
}

variable "jwt_algorithm" {
  type        = string
  description = "JWT algorithm"
  default     = "HS256"
}

variable "access_token_expire_minutes" {
  type        = number
  description = "Access token lifetime in minutes"
  default     = 60
}

variable "refresh_token_expire_days" {
  type        = number
  description = "Refresh token lifetime in days"
  default     = 30
}

variable "app_env" {
  type        = string
  description = "App Environment"
  default     = "development"
}

variable "tiktok_app_id" {
  type        = string
  description = "TikTok App ID"
  default     = ""
}

variable "tiktok_app_secret" {
  type        = string
  description = "TikTok App Secret"
  sensitive   = true
  default     = ""
}

variable "tiktok_acc_holder_auth_url" {
  type        = string
  description = "TikTok Account Holder Authorization URL"
  default     = ""
}

variable "tiktok_acc_holder_redirect_url" {
  type        = string
  description = "TikTok Account Holder Redirect URL"
  default     = ""
}
