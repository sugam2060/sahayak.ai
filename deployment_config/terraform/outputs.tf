output "api_gateway_public_ip" {
  value       = aws_instance.api_gateway.public_ip
  description = "Public IP of the API Gateway server"
}

output "auth_service_public_ip" {
  value       = aws_instance.auth_service.public_ip
  description = "Public IP of the Auth service server"
}

output "chatai_service_public_ip" {
  value       = aws_instance.chatai_service.public_ip
  description = "Public IP of the ChatAI service server"
}

output "celery_worker_public_ip" {
  value       = aws_instance.celery_worker.public_ip
  description = "Public IP of the Celery worker server"
}

output "api_gateway_ecr_url" {
  value       = aws_ecr_repository.api_gateway.repository_url
  description = "ECR Repository URL for API Gateway"
}

output "auth_service_ecr_url" {
  value       = aws_ecr_repository.auth_service.repository_url
  description = "ECR Repository URL for Auth Service"
}

output "chatai_service_ecr_url" {
  value       = aws_ecr_repository.chatai_service.repository_url
  description = "ECR Repository URL for ChatAI Service"
}

output "celery_worker_ecr_url" {
  value       = aws_ecr_repository.celery_worker.repository_url
  description = "ECR Repository URL for Celery Worker"
}

output "generated_private_key" {
  value       = var.key_name == "" ? tls_private_key.key[0].private_key_pem : "Pre-existing key pair was used"
  sensitive   = true
  description = "PEM encoded private key if generated dynamically by Terraform"
}
