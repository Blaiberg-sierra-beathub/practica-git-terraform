resource "random_pet" "owner" {
  length = 2
}

# NUEVO (paso 2): un valor calculado que reutilizamos en los nombres
locals {
  prefix = "${var.owner}-${var.environment}"
}

# NUEVO (paso 2): el primer archivo generado
resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = "# ${local.prefix}\nResponsable: ${random_pet.owner.id}\n"
}