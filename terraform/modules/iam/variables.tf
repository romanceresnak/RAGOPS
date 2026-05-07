variable "prefix"            { type = string }
variable "aws_region"        { type = string }
variable "aws_account_id"    { type = string }
variable "s3_bucket_arn"     { type = string }
variable "bedrock_model_ids" { type = list(string) }
