output "cluster_endpoint"     { value = aws_neptune_cluster.main.endpoint }
output "reader_endpoint"      { value = aws_neptune_cluster.main.reader_endpoint }
output "port"                 { value = aws_neptune_cluster.main.port }
output "cluster_id"           { value = aws_neptune_cluster.main.id }
output "cluster_arn"          { value = aws_neptune_cluster.main.arn }
output "cluster_resource_id"  { value = aws_neptune_cluster.main.cluster_resource_id }
