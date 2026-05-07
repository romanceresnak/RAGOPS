resource "random_id" "suffix" { byte_length = 4 }

# ── Main bucket ───────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "main" {
  bucket        = "${var.prefix}-ragops-${random_id.suffix.hex}"
  force_destroy = var.force_destroy
  tags          = { Name = "${var.prefix}-ragops" }
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket                  = aws_s3_bucket.main.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Folder placeholders ───────────────────────────────────────────────────────
resource "aws_s3_object" "folders" {
  for_each = toset(["documents/", "embeddings/", "benchmark-results/", "bedrock-logs/"])
  bucket   = aws_s3_bucket.main.id
  key      = "${each.value}.keep"
  content  = ""
}

# ── Lifecycle rules ───────────────────────────────────────────────────────────
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "expire-bedrock-logs"
    status = "Enabled"
    filter { prefix = "bedrock-logs/" }
    expiration { days = var.log_expiry_days }
  }

  rule {
    id     = "expire-benchmark-results"
    status = "Enabled"
    filter { prefix = "benchmark-results/" }
    expiration { days = 90 }
  }

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}
