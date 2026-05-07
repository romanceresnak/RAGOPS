output "log_group_name"  { value = aws_cloudwatch_log_group.bedrock.name }
output "log_group_arn"   { value = aws_cloudwatch_log_group.bedrock.arn }
output "logging_role_arn"{ value = aws_iam_role.bedrock_logging.arn }
output "dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home#dashboards:name=${aws_cloudwatch_dashboard.token_usage.dashboard_name}"
}
