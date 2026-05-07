output "vpc_id"                  { value = aws_vpc.main.id }
output "private_subnet_ids"     { value = aws_subnet.private[*].id }
output "public_subnet_ids"      { value = aws_subnet.public[*].id }
output "app_security_group_id"  { value = aws_security_group.app.id }
output "private_route_table_id" { value = aws_route_table.private.id }
