output "bucket_name"        { value = aws_s3_bucket.main.id }
output "bucket_arn"         { value = aws_s3_bucket.main.arn }
output "docs_prefix"        { value = "documents/" }
output "embeddings_prefix"  { value = "embeddings/" }
output "benchmark_prefix"   { value = "benchmark-results/" }
output "logs_prefix"        { value = "bedrock-logs/" }
