# ── Trust policy ─────────────────────────────────────────────────────────────
data "aws_iam_policy_document" "trust" {
  # AWS services (Lambda, ECS tasks, EC2)
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com", "ecs-tasks.amazonaws.com", "ec2.amazonaws.com"]
    }
  }
  # Current account — allows `aws sts assume-role` from CLI / local dev
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${var.prefix}-app-role"
  assume_role_policy = data.aws_iam_policy_document.trust.json
  description        = "RagOps app role - Bedrock + S3 + Neptune (least-privilege)"
  tags               = { Name = "${var.prefix}-app-role" }
}

# ── Bedrock: invoke specific models only ─────────────────────────────────────
data "aws_iam_policy_document" "bedrock" {
  statement {
    sid     = "InvokeModels"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      for m in var.bedrock_model_ids :
      "arn:aws:bedrock:${var.aws_region}::foundation-model/${m}"
    ]
  }
  statement {
    sid       = "ListModels"
    effect    = "Allow"
    actions   = ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "bedrock" {
  name   = "${var.prefix}-bedrock-policy"
  policy = data.aws_iam_policy_document.bedrock.json
}
resource "aws_iam_role_policy_attachment" "bedrock" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.bedrock.arn
}

# ── S3: read/write documents bucket ──────────────────────────────────────────
data "aws_iam_policy_document" "s3" {
  statement {
    sid       = "ListBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.s3_bucket_arn]
  }
  statement {
    sid     = "ObjectRW"
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectVersion"]
    resources = ["${var.s3_bucket_arn}/*"]
  }
}

resource "aws_iam_policy" "s3" {
  name   = "${var.prefix}-s3-policy"
  policy = data.aws_iam_policy_document.s3.json
}
resource "aws_iam_role_policy_attachment" "s3" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.s3.arn
}

# ── Neptune: IAM auth (no DB passwords) ──────────────────────────────────────
data "aws_iam_policy_document" "neptune" {
  statement {
    sid    = "NeptuneIAMAuth"
    effect = "Allow"
    actions = [
      "neptune-db:connect",
      "neptune-db:ReadDataViaQuery",
      "neptune-db:WriteDataViaQuery",
      "neptune-db:DeleteDataViaQuery",
    ]
    resources = ["arn:aws:neptune-db:${var.aws_region}:${var.aws_account_id}:*/*"]
  }
}

resource "aws_iam_policy" "neptune" {
  name   = "${var.prefix}-neptune-policy"
  policy = data.aws_iam_policy_document.neptune.json
}
resource "aws_iam_role_policy_attachment" "neptune" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.neptune.arn
}

# ── CloudWatch Logs (Lambda execution) ───────────────────────────────────────
resource "aws_iam_role_policy_attachment" "cwlogs" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ── EC2 Instance Profile ──────────────────────────────────────────────────────
resource "aws_iam_instance_profile" "app" {
  name = "${var.prefix}-instance-profile"
  role = aws_iam_role.app.name
}
