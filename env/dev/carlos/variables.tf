variable "owner" {
  description = "Tu usuario (minusculas, numeros y guiones)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.owner))
    error_message = "owner debe empezar por letra y tener entre 3 y 21 caracteres: a-z, 0-9 y guion."
  }
}

variable "environment" {
  description = "Ambiente de despliegue."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "pre", "prod"], var.environment)
    error_message = "environment debe ser dev, pre o prod."
  }
}