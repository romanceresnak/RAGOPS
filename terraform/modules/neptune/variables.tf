variable "prefix"                { type = string }
variable "vpc_id"                { type = string }
variable "private_subnet_ids"   { type = list(string) }
variable "app_security_group_id"{ type = string }
variable "serverless" {
  type = bool
  default = true
}
variable "min_ncu" {
  type = number
  default = 1.0
}
variable "max_ncu" {
  type = number
  default = 8.0
}
variable "instance_class" {
  type = string
  default = "db.t3.medium"
}
variable "engine_version" {
  type = string
  default = "1.3.1.0"
}
variable "backup_retention_days" {
  type = number
  default = 1
}
variable "skip_final_snapshot" {
  type = bool
  default = true
}
variable "iam_auth_enabled" {
  type = bool
  default = true
}
