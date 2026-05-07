variable "prefix" {
  type = string
}
variable "force_destroy" {
  type = bool
  default = true
}
variable "versioning_enabled" {
  type = bool
  default = true
}
variable "log_expiry_days" {
  type = number
  default = 90
}
