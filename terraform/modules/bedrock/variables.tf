variable "prefix"             { type = string }
variable "aws_region"         { type = string }
variable "aws_account_id"     { type = string }
variable "s3_bucket_name"     { type = string }
variable "log_retention_days" {
  type = number
  default = 30
}
