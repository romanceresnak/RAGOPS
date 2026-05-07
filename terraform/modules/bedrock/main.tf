# ── CloudWatch Log Group for Bedrock invocation logs ─────────────────────────
resource "aws_cloudwatch_log_group" "bedrock" {
  name              = "/aws/bedrock/${var.prefix}/invocations"
  retention_in_days = var.log_retention_days
  tags              = { Name = "${var.prefix}-bedrock-logs" }
}

# ── IAM role that allows Bedrock to push logs ─────────────────────────────────
resource "aws_iam_role" "bedrock_logging" {
  name        = "${var.prefix}-bedrock-logging-role"
  description = "Allows Bedrock to write invocation logs to CW + S3"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock:${var.aws_region}:${var.aws_account_id}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_logging" {
  name = "${var.prefix}-bedrock-logging-policy"
  role = aws_iam_role.bedrock_logging.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.bedrock.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${var.s3_bucket_name}/bedrock-logs/*"
      }
    ]
  })
}

# ── Enable Model Invocation Logging ───────────────────────────────────────────
resource "aws_bedrock_model_invocation_logging_configuration" "main" {
  logging_config {
    cloudwatch_config {
      log_group_name = aws_cloudwatch_log_group.bedrock.name
      role_arn       = aws_iam_role.bedrock_logging.arn
    }
    embedding_data_delivery_enabled = true
    image_data_delivery_enabled     = false
    text_data_delivery_enabled      = true
  }
}

# ── CloudWatch Dashboard — token usage (Input · Output · Cache · Latency) ─────
resource "aws_cloudwatch_dashboard" "token_usage" {
  dashboard_name = "${var.prefix}-bedrock-tokens"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x = 0
        y = 0
        width = 12
        height = 6
        properties = {
          title   = "Input Tokens - by Model"
          region  = var.aws_region
          period  = 300
          stat = "Sum"
          view = "timeSeries"
          metrics = [
            ["AWS/Bedrock", "InputTokenCount", "ModelId", "us.anthropic.claude-sonnet-4-6"],
          ]
        }
      },
      {
        type = "metric"
        x = 12
        y = 0
        width = 12
        height = 6
        properties = {
          title   = "Output Tokens - by Model"
          region  = var.aws_region
          period  = 300
          stat = "Sum"
          view = "timeSeries"
          metrics = [
            ["AWS/Bedrock", "OutputTokenCount", "ModelId", "us.anthropic.claude-sonnet-4-6"],
          ]
        }
      },
      {
        type = "metric"
        x = 0
        y = 6
        width = 12
        height = 6
        properties = {
          title   = "Cache Read Tokens - CAG Savings"
          region  = var.aws_region
          period  = 300
          stat = "Sum"
          view = "timeSeries"
          metrics = [
            ["AWS/Bedrock", "CacheReadInputTokenCount", "ModelId", "us.anthropic.claude-sonnet-4-6"],
          ]
        }
      },
      {
        type = "metric"
        x = 12
        y = 6
        width = 12
        height = 6
        properties = {
          title   = "Invocation Latency p99 (ms)"
          region  = var.aws_region
          period  = 300
          stat = "p99"
          view = "timeSeries"
          metrics = [
            ["AWS/Bedrock", "InvocationLatency", "ModelId", "us.anthropic.claude-sonnet-4-6"],
          ]
        }
      },
      {
        type = "metric"
        x = 0
        y = 12
        width = 24
        height = 6
        properties = {
          title   = "Invocation Count - all models"
          region  = var.aws_region
          period  = 300
          stat = "Sum"
          view = "timeSeries"
          metrics = [
            ["AWS/Bedrock", "Invocations", "ModelId", "us.anthropic.claude-sonnet-4-6"],
            ["AWS/Bedrock", "Invocations", "ModelId", "amazon.titan-embed-text-v2:0"],
          ]
        }
      }
    ]
  })
}
