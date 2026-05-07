data "aws_region" "current" {}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.prefix}-vpc" }
}

# ── Internet Gateway ──────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.prefix}-igw" }
}

# ── Public subnets ────────────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.prefix}-public-${var.availability_zones[count.index]}" }
}

# ── Private subnets (Neptune + VPC endpoints) ─────────────────────────────────
resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags              = { Name = "${var.prefix}-private-${var.availability_zones[count.index]}" }
}

# ── Route tables ──────────────────────────────────────────────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.prefix}-rt-public" }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.prefix}-rt-private" }
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── VPC Gateway Endpoint — S3 (free, no NAT needed) ──────────────────────────
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = { Name = "${var.prefix}-vpce-s3" }
}

# ── VPC Interface Endpoint — Bedrock Runtime (private Bedrock calls) ──────────
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.prefix}-vpce-bedrock-runtime" }
}

# ── Security Groups ───────────────────────────────────────────────────────────

# App layer (Lambda / local dev / ECS task)
resource "aws_security_group" "app" {
  name        = "${var.prefix}-sg-app"
  description = "App layer - outbound to Neptune:8182 and AWS endpoints:443"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Neptune Gremlin WebSocket"
    from_port   = 8182
    to_port = 8182
    protocol = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    description = "HTTPS to AWS services via VPC endpoints"
    from_port   = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.prefix}-sg-app" }
}

# VPC endpoint interfaces
resource "aws_security_group" "vpce" {
  name        = "${var.prefix}-sg-vpce"
  description = "VPC endpoint interfaces - allow HTTPS from VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  tags = { Name = "${var.prefix}-sg-vpce" }
}
