# =============================================================================
# GLOBAL
# =============================================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project prefix used in every resource name"
  type        = string
  default     = "ragops"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be: dev | staging | prod"
  }
}

variable "owner" {
  description = "Owner tag (name / team)"
  type        = string
  default     = "roman"
}

# =============================================================================
# NETWORKING
# =============================================================================

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread subnets across (min 2 for Neptune)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "private_subnet_cidrs" {
  description = "CIDRs for private subnets (Neptune + VPC endpoints)"
  type        = list(string)
  default     = ["10.10.1.0/24", "10.10.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDRs for public subnets (future bastion / Lambda)"
  type        = list(string)
  default     = ["10.10.101.0/24", "10.10.102.0/24"]
}

# =============================================================================
# S3
# =============================================================================

variable "s3_force_destroy" {
  description = "Allow non-empty bucket deletion (dev only)"
  type        = bool
  default     = true
}

variable "s3_versioning_enabled" {
  description = "Enable S3 object versioning"
  type        = bool
  default     = true
}

variable "s3_log_expiry_days" {
  description = "Days before Bedrock log objects expire"
  type        = number
  default     = 90
}

# =============================================================================
# NEPTUNE
# =============================================================================

variable "neptune_serverless" {
  description = "Use Neptune Serverless v2 (scales to 0 when idle)"
  type        = bool
  default     = true
}

variable "neptune_min_ncu" {
  description = "Minimum Neptune Capacity Units (0.5 – 128)"
  type        = number
  default     = 1.0
}

variable "neptune_max_ncu" {
  description = "Maximum Neptune Capacity Units"
  type        = number
  default     = 8.0
}

variable "neptune_instance_class" {
  description = "Instance class used when serverless = false"
  type        = string
  default     = "db.t3.medium"
}

variable "neptune_engine_version" {
  description = "Neptune engine version"
  type        = string
  default     = "1.3.1.0"
}

variable "neptune_backup_retention_days" {
  description = "Automated backup retention in days"
  type        = number
  default     = 1
}

variable "neptune_skip_final_snapshot" {
  description = "Skip final snapshot on cluster deletion"
  type        = bool
  default     = true
}

variable "neptune_iam_auth_enabled" {
  description = "Enforce IAM database authentication (no passwords)"
  type        = bool
  default     = true
}

# =============================================================================
# BEDROCK
# =============================================================================

variable "bedrock_model_ids" {
  description = "Foundation model ARN suffixes the app role may invoke"
  type        = list(string)
  default = [
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "amazon.titan-embed-text-v2:0",
  ]
}

variable "bedrock_log_retention_days" {
  description = "CloudWatch retention for Bedrock invocation logs"
  type        = number
  default     = 30
}
