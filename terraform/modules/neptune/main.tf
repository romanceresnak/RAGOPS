# ── Subnet group ──────────────────────────────────────────────────────────────
resource "aws_neptune_subnet_group" "main" {
  name       = "${var.prefix}-neptune-sng"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.prefix}-neptune-sng" }
}

# ── Cluster parameter group ───────────────────────────────────────────────────
resource "aws_neptune_cluster_parameter_group" "main" {
  family      = "neptune1.3"
  name        = "${var.prefix}-neptune-cpg"
  description = "RagOps Neptune cluster parameters"

  parameter {
    name  = "neptune_enable_audit_log"
    value = "1"
  }
  tags = { Name = "${var.prefix}-neptune-cpg" }
}

# ── Security group (separate from networking module for encapsulation) ────────
resource "aws_security_group" "neptune" {
  name        = "${var.prefix}-sg-neptune"
  description = "Neptune: accept Gremlin/SPARQL from app layer only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Gremlin WebSocket port"
    from_port       = 8182
    to_port         = 8182
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }
  egress {
    from_port   = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.prefix}-sg-neptune" }
}

# ── Cluster ───────────────────────────────────────────────────────────────────
resource "aws_neptune_cluster" "main" {
  cluster_identifier                   = "${var.prefix}-neptune"
  engine                               = "neptune"
  engine_version                       = var.engine_version
  neptune_subnet_group_name            = aws_neptune_subnet_group.main.name
  neptune_cluster_parameter_group_name = aws_neptune_cluster_parameter_group.main.name
  vpc_security_group_ids               = [aws_security_group.neptune.id]
  port                                 = 8182

  iam_database_authentication_enabled = var.iam_auth_enabled
  storage_encrypted                   = true
  backup_retention_period             = var.backup_retention_days
  skip_final_snapshot                 = var.skip_final_snapshot

  dynamic "serverless_v2_scaling_configuration" {
    for_each = var.serverless ? [1] : []
    content {
      min_capacity = var.min_ncu
      max_capacity = var.max_ncu
    }
  }

  tags = { Name = "${var.prefix}-neptune" }
}

# ── Writer instance (required even for Serverless) ────────────────────────────
resource "aws_neptune_cluster_instance" "writer" {
  identifier                   = "${var.prefix}-neptune-writer"
  cluster_identifier           = aws_neptune_cluster.main.id
  engine                       = "neptune"
  instance_class               = var.serverless ? "db.serverless" : var.instance_class
  neptune_subnet_group_name    = aws_neptune_subnet_group.main.name
  publicly_accessible          = false
  auto_minor_version_upgrade   = true
  tags                         = { Name = "${var.prefix}-neptune-writer", Role = "writer" }
}

# ── CloudWatch alarm: CPU > 80% ───────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "neptune_cpu" {
  alarm_name          = "${var.prefix}-neptune-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/Neptune"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    DBClusterIdentifier = aws_neptune_cluster.main.cluster_identifier
  }
  tags = { Name = "${var.prefix}-neptune-cpu-alarm" }
}
