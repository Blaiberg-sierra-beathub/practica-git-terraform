resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

# NUEVO (paso 3): la lista de servicios, escrita directamente en el código
locals {
  services = {
    api = {
      port     = 8080
      replicas = 2
      public   = true
      tags     = ["backend", "critical"]
    }
    web = {
      port     = 3000
      replicas = 1
      public   = true
      tags     = ["frontend"]
    }
    worker = {
      port     = 9000
      replicas = 3
      public   = false
      tags     = ["backend"]
    }
  }
}

resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = "# ${local.prefix}\nResponsable: ${random_pet.owner.id}\n"
}

# NUEVO (paso 3): un archivo por cada servicio
resource "local_file" "service" {
  for_each = local.services

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content  = "port = ${each.value.port}\nreplicas = ${each.value.replicas}\n"
}