locals {
  prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# MODULE: Networking
# VPC · subnets · IGW · route tables · security groups · VPC endpoints
# =============================================================================
module "networking" {
  source = "./modules/networking"

  prefix               = local.prefix
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs
}

# =============================================================================
# MODULE: S3
# Document store for RAG · embeddings cache · Bedrock logs
# =============================================================================
module "s3" {
  source = "./modules/s3"

  prefix                = local.prefix
  force_destroy         = var.s3_force_destroy
  versioning_enabled    = var.s3_versioning_enabled
  log_expiry_days       = var.s3_log_expiry_days
}

# =============================================================================
# MODULE: Neptune
# Knowledge Graph for KAG (Gremlin / SPARQL, IAM auth)
# =============================================================================
module "neptune" {
  source = "./modules/neptune"

  prefix                      = local.prefix
  vpc_id                      = module.networking.vpc_id
  private_subnet_ids          = module.networking.private_subnet_ids
  app_security_group_id       = module.networking.app_security_group_id
  serverless                  = var.neptune_serverless
  min_ncu                     = var.neptune_min_ncu
  max_ncu                     = var.neptune_max_ncu
  instance_class              = var.neptune_instance_class
  engine_version              = var.neptune_engine_version
  backup_retention_days       = var.neptune_backup_retention_days
  skip_final_snapshot         = var.neptune_skip_final_snapshot
  iam_auth_enabled            = var.neptune_iam_auth_enabled
}

# =============================================================================
# MODULE: IAM
# App role + least-privilege policies for Bedrock · S3 · Neptune
# =============================================================================
module "iam" {
  source = "./modules/iam"

  prefix           = local.prefix
  aws_region       = data.aws_region.current.name
  aws_account_id   = data.aws_caller_identity.current.account_id
  s3_bucket_arn    = module.s3.bucket_arn
  bedrock_model_ids = var.bedrock_model_ids
}

# =============================================================================
# MODULE: Bedrock
# Invocation logging · CloudWatch token dashboard
# =============================================================================
module "bedrock" {
  source = "./modules/bedrock"

  prefix              = local.prefix
  aws_region          = data.aws_region.current.name
  aws_account_id      = data.aws_caller_identity.current.account_id
  s3_bucket_name      = module.s3.bucket_name
  log_retention_days  = var.bedrock_log_retention_days
}
