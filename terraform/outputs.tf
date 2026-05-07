# =============================================================================
# NETWORKING
# =============================================================================
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (Neptune resides here)"
  value       = module.networking.private_subnet_ids
}

output "app_security_group_id" {
  description = "SG attached to the application layer"
  value       = module.networking.app_security_group_id
}

# =============================================================================
# S3
# =============================================================================
output "s3_bucket_name" {
  description = "Documents bucket name → S3_BUCKET_NAME in .env"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  value = module.s3.bucket_arn
}

# =============================================================================
# NEPTUNE
# =============================================================================
output "neptune_endpoint" {
  description = "Neptune writer endpoint → NEPTUNE_ENDPOINT in .env"
  value       = module.neptune.cluster_endpoint
}

output "neptune_reader_endpoint" {
  description = "Neptune reader endpoint (load-balanced)"
  value       = module.neptune.reader_endpoint
}

output "neptune_port" {
  description = "Neptune port (8182) → NEPTUNE_PORT in .env"
  value       = module.neptune.port
}

output "neptune_cluster_resource_id" {
  description = "Required for Neptune IAM auth policy"
  value       = module.neptune.cluster_resource_id
}

# =============================================================================
# IAM
# =============================================================================
output "app_role_arn" {
  description = "App IAM role ARN → APP_ROLE_ARN in .env"
  value       = module.iam.app_role_arn
}

output "app_role_name" {
  value = module.iam.app_role_name
}

# =============================================================================
# BEDROCK
# =============================================================================
output "bedrock_log_group" {
  description = "CloudWatch log group for Bedrock invocations"
  value       = module.bedrock.log_group_name
}

output "bedrock_dashboard_url" {
  description = "CloudWatch dashboard — token usage in real-time"
  value       = module.bedrock.dashboard_url
}

# =============================================================================
# .env SUMMARY — paste directly into your .env file
# =============================================================================
output "dotenv_block" {
  description = "Ready-to-paste .env values"
  sensitive   = false
  value       = <<-EOT

    # ── terraform output dotenv_block ─────────────────────────
    AWS_REGION=${data.aws_region.current.name}
    S3_BUCKET_NAME=${module.s3.bucket_name}
    NEPTUNE_ENDPOINT=${module.neptune.cluster_endpoint}
    NEPTUNE_PORT=${module.neptune.port}
    APP_ROLE_ARN=${module.iam.app_role_arn}
    BEDROCK_LOG_GROUP=${module.bedrock.log_group_name}
    # ──────────────────────────────────────────────────────────

  EOT
}
