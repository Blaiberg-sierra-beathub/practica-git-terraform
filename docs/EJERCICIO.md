# Ejercicio guiado: Git + Terraform local (40 minutos)

Nivel: principiante. No necesitas cuenta de nube ni conocimientos previos.

En este ejercicio vas a:
1. Descargar un repositorio de GitHub y trabajar en tu propia rama.
2. Escribir código de Terraform poco a poco (9 pasos pequeños).
3. Subir tu trabajo con un Pull Request y ver cómo lo revisa el CI (revisión automática).
4. Practicar los errores y conflictos que se dan cuando varias personas trabajan en el mismo repositorio.

Todo se ejecuta en tu computador, **en Git Bash**. Terraform no crea nada en la nube: genera archivos de texto en tu máquina. Así practicas el flujo completo sin riesgo ni costo.

Repositorio común para todos: https://github.com/Blaiberg-sierra-beathub/practica-git-terraform.git

## Contenido

1. [Antes de empezar: cómo leer esta guía](#antes-de-empezar-cómo-leer-esta-guía)
2. [Reglas del equipo](#reglas-del-equipo)
3. [Parte 1. Preparación del entorno](#parte-1-preparación-del-entorno-6-min)
4. [Parte 2. Clonar el repo y crear tu rama](#parte-2-clonar-el-repo-y-crear-tu-rama-4-min)
5. [Parte 3. Terraform paso a paso](#parte-3-terraform-paso-a-paso-16-min)
6. [Parte 4. Commit y push](#parte-4-commit-y-push-2-min)
7. [Parte 5. Pull Request y CI](#parte-5-pull-request-y-ci-4-min)
8. [Parte 6. Escenarios de error y conflictos](#parte-6-escenarios-de-error-y-conflictos-6-min)
9. [Parte 7. Limpieza y cierre](#parte-7-limpieza-y-cierre-2-min)
10. [Errores comunes y cómo resolverlos](#errores-comunes-y-cómo-resolverlos)

## Cronograma

| Min | Parte |
|---|---|
| 0-6 | 1. Preparación del entorno |
| 6-10 | 2. Clonar el repo y crear tu rama |
| 10-26 | 3. Terraform paso a paso (9 pasos, con `plan`/`apply` en cada uno) |
| 26-28 | 4. Commit y push |
| 28-32 | 5. Pull Request y CI |
| 32-38 | 6. Escenarios de error y conflictos |
| 38-40 | 7. Limpieza y cierre |

## Qué vas a aprender

| Área | Temas |
|---|---|
| Git | clonar, ramas, commits, push, Pull Request, conflictos, deshacer errores, `.gitignore` |
| Terraform | providers, variables, validaciones, `locals`, `for_each`, YAML, `templatefile`, `for`, `count`, `precondition`, outputs, `plan`/`apply`/`destroy`, drift |
| Equipo | convenciones de ramas y commits, CI, revisión de código, resolución de conflictos |

---

## Antes de empezar: cómo leer esta guía

**Parejas.** Trabajas con otra persona: **Persona A** y **Persona B**. Cada uno usa su computador y su carpeta, pero ambos trabajan sobre el mismo repositorio. Como varias personas tocan el repo a la vez, aparecerán conflictos. Es intencional: así se aprende a resolverlos.

**Tu usuario.** En los comandos verás `<usuario>`. Reemplázalo (incluidos los símbolos `<` y `>`) por tu usuario de GitHub en minúsculas, sin espacios. Si tu usuario es `ana-lopez`:

| Dice la guía | Tú escribes |
|---|---|
| `mkdir -p env/dev/<usuario>` | `mkdir -p env/dev/ana-lopez` |
| `feature/<usuario>-capa-dev` | `feature/ana-lopez-capa-dev` |

Usa siempre el mismo valor.

**Los comandos.** Todos son para **Git Bash** (no PowerShell ni CMD). Se abre desde el menú Inicio, buscando "Git Bash".
- Escribe lo que está dentro de los bloques de código. No escribas el símbolo `$` si lo ves al inicio de una línea.
- Todo lo que está después de un `#` es un comentario: es una explicación, no hay que escribirlo (aunque no pasa nada si lo copias).
- Después de cada comando pulsa Enter y **lee el resultado**. Si dice `Error`, para y revisa la sección [Errores comunes](#errores-comunes-y-cómo-resolverlos).

**Dónde estás.** Muchos errores vienen de ejecutar un comando en la carpeta equivocada. Hay dos comandos que te ayudan siempre:

```bash
pwd     # muestra la carpeta actual
ls      # muestra los archivos de la carpeta actual
```

En el prompt de Git Bash también ves la carpeta y la rama, por ejemplo: `~/practica-git-terraform/env/dev/ana-lopez (feature/ana-lopez-capa-dev)`.

**Crear y guardar archivos.** Tienes dos opciones desde Git Bash. Recomendada (VS Code):

```bash
code versions.tf      # abre (o crea) el archivo en VS Code
```

Pega el contenido y guarda con `Ctrl+S`. Sin VS Code, usa nano:

```bash
nano versions.tf      # pega el contenido; guarda con Ctrl+O y Enter; sal con Ctrl+X
```

Después de crear un archivo, compruébalo con `ls -la`: debe aparecer con un tamaño mayor que 0. El archivo se crea **en la carpeta donde ejecutaste el comando**, así que revisa `pwd` antes.

**Qué construirás.** Al final de la Parte 3 tu carpeta se verá así:

```
env/dev/<usuario>/
├── versions.tf          # versiones de Terraform y de los providers
├── variables.tf         # datos de entrada (owner, environment)
├── main.tf              # los recursos: el código principal
├── outputs.tf           # lo que se muestra al terminar
├── services.yaml        # los datos: qué servicios existen
├── templates/
│   └── service.tftpl    # plantilla del archivo de cada servicio
├── .terraform.lock.hcl  # (se genera) versiones exactas de los providers  → SE SUBE a Git
├── terraform.tfstate    # (se genera) memoria de Terraform               → NO se sube
├── .terraform/          # (se genera) providers descargados              → NO se sube
└── generated/           # (se genera) los archivos que crea Terraform    → NO se sube
```

---

## Reglas del equipo

Léelas antes de empezar. Cada regla evita un problema real.

1. **Nunca** hagas commit ni push directo a `main`, `development` ni `preproduction`. Todo entra por Pull Request.
2. Nombre de rama: `feature/<usuario>-<tema>`, en minúsculas y con guiones. Ejemplo: `feature/ana-lopez-capa-dev`.
3. Mensaje de commit: `tipo: descripción corta`, con tipo `feature`, `fix`, `docs` o `chore`. Ejemplo: `feature: add dev layer`.
4. **Nunca** subas a Git: `*.tfstate`, `.terraform/`, `*.tfvars`, claves, contraseñas ni tokens. Pueden exponer secretos.
5. **Sí** sube `.terraform.lock.hcl`: fija las versiones exactas de los providers para todo el equipo.
6. Trabaja **solo dentro de tu carpeta** `env/dev/<usuario>/`. Los únicos archivos compartidos que se editan son los que indique la guía.
7. Antes de cada commit: `terraform fmt` y `terraform validate`.
8. Prohibido `git push --force`: puede borrar el trabajo de otras personas. Si crees que lo necesitas, pregunta primero.
9. Fija versiones de providers (`~> 2.5`), nunca uses rangos abiertos.
10. Un commit = un cambio con sentido. No mezcles formato, funcionalidad y documentación.
11. Antes de abrir un PR, trae lo último de `development` (`git merge origin/development`).
12. No hagas merge de un PR con el CI en rojo: el CI revisa las carpetas de **todos**, y un error tuyo bloquea a los demás.

---

## Parte 1. Preparación del entorno (6 min)

### 1.1 Instalar Git (incluye Git Bash)

Descarga el instalador de https://git-scm.com/download/win y ejecútalo. Deja **todas las opciones por defecto** (siguiente, siguiente...). Al terminar, abre "Git Bash" desde el menú Inicio.

### 1.2 Instalar Terraform

Opción A, con winget (desde Git Bash):

```bash
winget install --id Hashicorp.Terraform -e
```

Opción B, manual:
1. Descarga el zip "Windows AMD64" de https://developer.hashicorp.com/terraform/install
2. Extrae `terraform.exe` en `C:\terraform\`
3. Añade `C:\terraform` al PATH: menú Inicio, "Editar las variables de entorno del sistema", Variables de entorno, selecciona `Path`, Nuevo, y pega la ruta.

**Cierra y vuelve a abrir Git Bash** para que reconozca la instalación.

Opcional pero recomendado: instala VS Code (https://code.visualstudio.com) como editor.

### 1.3 Verificar la instalación

```bash
git --version        # esperado: git version 2.x
terraform version    # esperado: Terraform v1.5 o superior
```

Si dice `command not found`: no reiniciaste Git Bash o el PATH está mal. Repite el paso 1.2.

### 1.4 Configurar Git (una sola vez por computador)

Git necesita saber quién eres para firmar tus commits:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@empresa.com"
git config --global init.defaultBranch main
git config --global --list                 # revisa lo que quedó
```

Usa el mismo correo de tu cuenta de GitHub.

### 1.5 Acceso a GitHub

1. Acepta la invitación como colaborador que llegó a tu correo (o en https://github.com/notifications). Sin esto no podrás subir cambios.
2. La primera vez que hagas `clone` o `push`, se abrirá el navegador para que inicies sesión en GitHub. Autoriza y listo (es el Git Credential Manager, que ya viene incluido).
3. Si no abre el navegador y te pide usuario y contraseña: la contraseña **no** es la de GitHub, es un token. Créalo en GitHub: Settings, Developer settings, Personal access tokens, con permiso `repo`. Pégalo como contraseña.

---

## Parte 2. Clonar el repo y crear tu rama (4 min)

Una **rama** es una copia paralela del código donde puedes trabajar sin afectar a los demás. Todo tu trabajo va en tu rama; al final se une con `development` mediante un Pull Request.

### 2.1 Clonar el repositorio

Clonar es descargar una copia del repositorio a tu computador.

```bash
cd ~                                # ~ es tu carpeta de usuario
git clone https://github.com/Blaiberg-sierra-beathub/practica-git-terraform.git
cd practica-git-terraform
```

### 2.2 Revisar qué tienes

```bash
git status                       # esperado: On branch main ... nothing to commit, working tree clean
git branch -a                    # ramas locales y remotas (las remotas empiezan por remotes/origin)
git log --oneline --graph --all  # historial de commits
ls -a
```

Debes ver las carpetas `.github/`, `docs/`, `env/`, `modules/`, `scripts/` y el archivo `.gitignore`.

### 2.3 Crear tu rama desde `development`

```bash
git switch development                       # cambia a development (Git la descarga de origin la primera vez)
git pull                                     # trae lo último
git switch -c feature/<usuario>-capa-dev     # crea tu rama y cambia a ella
git branch --show-current                    # esperado: feature/<usuario>-capa-dev
```

Si `git switch development` dice `invalid reference`, ejecuta antes `git fetch origin`.

---

## Parte 3. Terraform paso a paso (16 min)

Vas a construir tu propia carpeta `env/dev/<usuario>/` **en 9 pasos pequeños**. En cada paso:

1. Lees el concepto nuevo.
2. Reemplazas el contenido del archivo indicado (a partir del Paso 2, siempre `main.tf` completo: **no editas pedazos**, así nunca se borra ni se repite algo por error).
3. Ejecutas los comandos y comparas con el resultado esperado.
4. Haces un experimento corto.

**No avances al siguiente paso si el actual no da el resultado esperado.**

### Preparación

```bash
mkdir -p env/dev/<usuario>/templates     # crea tu carpeta y la subcarpeta de plantillas
cd env/dev/<usuario>                     # entra a tu carpeta
pwd                                      # debe terminar en .../env/dev/<usuario>
export TF_VAR_owner=<usuario>            # define la variable "owner" para Terraform
```

Qué hace el `export`: crea una variable de entorno en esta ventana de Git Bash. Terraform lee cualquier variable llamada `TF_VAR_<nombre>` y la usa como valor de la variable `<nombre>` (aquí `owner`). Dura solo mientras la ventana siga abierta: **si abres una ventana nueva, repítelo**. Si no lo haces, Terraform te preguntará `var.owner` en pantalla.

**Todos los comandos `terraform` se ejecutan dentro de `env/dev/<usuario>`**, nunca en la raíz del repo ni en la subcarpeta `templates`.

### El ciclo que repetirás

```bash
terraform fmt         # ordena el formato del código (no cambia lo que hace)
terraform validate    # revisa que la sintaxis sea correcta
terraform plan        # simula: muestra qué cambiaría, sin cambiar nada
terraform apply       # ejecuta los cambios; pide confirmación: escribe yes
```

Cómo leer un `plan`:

| Símbolo | Significa |
|---|---|
| `+` | se va a crear |
| `-` | se va a destruir |
| `~` | se va a modificar |
| `-/+` | se destruye y se vuelve a crear |

La última línea resume: `Plan: 3 to add, 0 to change, 1 to destroy`.

> `terraform validate` dice "valid" incluso en una carpeta vacía. Que diga "valid" no prueba que tengas el código: revisa con `ls`.

---

### Paso 1. Providers, un recurso y un output (2 min)

**Concepto.** Un *provider* es el plugin que le enseña a Terraform a crear un tipo de cosas (aquí archivos y nombres aleatorios). Un *resource* es una cosa que Terraform crea y administra. Un *output* es un dato que Terraform muestra al terminar.

Crea `versions.tf`:

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
```

Crea `main.tf`:

```hcl
# Genera un nombre aleatorio de dos palabras (por ejemplo "happy-otter")
resource "random_pet" "owner" {
  length = 2
}
```

Crea `outputs.tf`:

```hcl
output "responsable" {
  description = "Nombre aleatorio asignado."
  value       = random_pet.owner.id
}
```

Ejecuta:

```bash
ls                    # deben aparecer main.tf, outputs.tf, versions.tf y templates
terraform init        # descarga los providers; solo hace falta la primera vez
terraform apply       # escribe yes
```

**Esperado:** `Apply complete! Resources: 1 added`, y al final `responsable = "algo-asi"`.

**Qué pasó:** Terraform creó un nombre aleatorio y lo guardó en `terraform.tfstate`. Ese archivo es su memoria: sabe qué ha creado.

**Experimento:** ejecuta `terraform apply` otra vez. Dice `No changes`, porque ya existe lo que pedías. A esto se le llama *idempotencia*.

---

### Paso 2. Variables y locals (2 min)

**Concepto.** Una *variable* es un dato de entrada (cambia entre ejecuciones). Un *local* es un valor calculado que reutilizas dentro del código. La `validation` rechaza valores incorrectos antes de hacer nada.

Crea `variables.tf`:

```hcl
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
```

**Reemplaza todo el contenido de `main.tf`** (borra lo que había y pega esto):

```hcl
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
```

Ejecuta:

```bash
terraform fmt
terraform validate
terraform plan
terraform apply       # escribe yes
```

**Esperado:** `Plan: 1 to add` y luego `Apply complete! Resources: 1 added`. Se crea el archivo `generated/<usuario>-dev/SUMMARY.md`.

**Experimentos:**
- `cat generated/<usuario>-dev/SUMMARY.md` muestra el contenido generado.
- `terraform plan -var environment=pre`: propone `-/+` (cambia el nombre de la carpeta, así que reemplaza el archivo). **No lo apliques.**
- `terraform plan -var environment=qa`: falla con tu mensaje de validación, antes de tocar nada.

---

### Paso 3. `for_each` sobre un mapa (2 min)

**Concepto.** `for_each` crea **un recurso por cada elemento** de un mapa. Aquí, un archivo `.conf` por cada servicio. Cada recurso se identifica por su clave: `local_file.service["api"]`.

**Reemplaza todo el contenido de `main.tf`:**

```hcl
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
```

Ejecuta `terraform fmt`, `terraform validate`, `terraform plan` y `terraform apply`.

**Esperado:** `Plan: 3 to add` y `Apply complete! Resources: 3 added`. Se crean `api.conf`, `web.conf` y `worker.conf`.

**Experimentos** (después vuelve al código original):
- Añade un cuarto servicio `db` (con `port`, `replicas`, `public` y `tags`) y haz `terraform plan`: `1 to add`. Quítalo y verás `1 to destroy`.
- `terraform state list` muestra cada recurso con su clave, por ejemplo `local_file.service["api"]`.

**Primer commit de control.** Un commit es una "foto" de tu trabajo. Hacerlos a menudo te permite volver atrás si algo sale mal:

```bash
cd ../../..                         # vuelve a la raíz del repo
git status                          # deben aparecer archivos en env/dev/<usuario>
git add env/dev/<usuario>
git status                          # NO deben aparecer terraform.tfstate, .terraform ni generated
git commit -m "feature: add base resources and for_each services"
cd env/dev/<usuario>                # vuelve a tu carpeta de trabajo
```

---

### Paso 4. Sacar los datos a un YAML (2 min)

**Concepto.** Es buena práctica separar **los datos** (qué servicios hay) del **código** (cómo se crean). Los datos viven en un archivo `.yaml` versionado en Git. `yamldecode` lee el YAML y `try` da un valor por defecto si falta un campo.

Crea `services.yaml`:

```yaml
services:
  api:
    port: 8080
    replicas: 2
    public: true
    tags: [backend, critical]
  web:
    port: 3000
    public: true
    tags: [frontend]
  worker:
    port: 9000
    replicas: 3
    tags: [backend]
```

Fíjate: `web` no declara `replicas` y `worker` no declara `public`. El código les pondrá valores por defecto.

**Reemplaza todo el contenido de `main.tf`:**

```hcl
resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

# CAMBIA (paso 4): los servicios ya no están escritos aquí, se leen del YAML
locals {
  # yamldecode + file: la configuracion vive en un archivo versionado
  services_raw = yamldecode(file("${path.module}/services.yaml")).services

  # for con valores por defecto: completa los campos opcionales
  services = {
    for name, s in local.services_raw : name => {
      port     = s.port
      replicas = try(s.replicas, 1)
      public   = try(s.public, false)
      tags     = try(s.tags, [])
    }
  }
}

resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = "# ${local.prefix}\nResponsable: ${random_pet.owner.id}\n"
}

resource "local_file" "service" {
  for_each = local.services

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content  = "port = ${each.value.port}\nreplicas = ${each.value.replicas}\n"
}
```

Ejecuta `terraform fmt`, `terraform validate` y `terraform plan`.

**Esperado: `No changes`.** Cambiaste el origen de los datos pero el resultado es idéntico. Es la señal de que el cambio de estructura (refactor) salió bien. No hace falta `apply`.

**Experimento:** añade en `services.yaml` un servicio `db` con `port: 5432` y haz `terraform plan` (`1 to add`). Bórralo del YAML para volver a `No changes`.

---

### Paso 5. Plantillas con `templatefile` (2 min)

**Concepto.** Una plantilla es un texto con huecos y bucles. `templatefile` la rellena con tus datos. Así cada `.conf` tendrá un formato completo y una línea por cada tag.

Crea `templates/service.tftpl` (dentro de la subcarpeta `templates`; desde tu carpeta: `code templates/service.tftpl`):

```
# ${prefix}/${name}
environment = ${environment}
port        = ${service.port}
replicas    = ${service.replicas}
public      = ${service.public}
%{ for tag in service.tags ~}
tag         = ${tag}
%{ endfor ~}
```

**Reemplaza todo el contenido de `main.tf`:**

```hcl
resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

locals {
  # yamldecode + file: la configuracion vive en un archivo versionado
  services_raw = yamldecode(file("${path.module}/services.yaml")).services

  # for con valores por defecto: completa los campos opcionales
  services = {
    for name, s in local.services_raw : name => {
      port     = s.port
      replicas = try(s.replicas, 1)
      public   = try(s.public, false)
      tags     = try(s.tags, [])
    }
  }
}

resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = "# ${local.prefix}\nResponsable: ${random_pet.owner.id}\n"
}

# CAMBIA (paso 5): el contenido ahora sale de una plantilla
resource "local_file" "service" {
  for_each = local.services

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content = templatefile("${path.module}/templates/service.tftpl", {
    name        = each.key
    prefix      = local.prefix
    environment = var.environment
    service     = each.value
  })
}
```

Ejecuta `terraform fmt`, `terraform validate`, `terraform plan` y `terraform apply`.

**Esperado:** `Plan: 3 to add, 0 to change, 3 to destroy`. El contenido cambió y el provider reemplaza cada archivo. Luego `Apply complete! Resources: 3 added, 0 changed, 3 destroyed.`

**Comprueba:** `cat generated/<usuario>-dev/api.conf` debe mostrar una línea `tag` por cada tag (`backend` y `critical`).

---

### Paso 6. Expresiones `for`, filtros y `count` (3 min)

**Concepto.** `for` transforma colecciones (como un bucle que devuelve una lista nueva). `if` dentro de un `for` filtra elementos. `count` con una condición decide si un recurso existe (1) o no (0).

**Reemplaza todo el contenido de `main.tf`.** Lo nuevo está marcado con `# NUEVO (paso 6)`:

```hcl
resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

locals {
  # yamldecode + file: la configuracion vive en un archivo versionado
  services_raw = yamldecode(file("${path.module}/services.yaml")).services

  # for con valores por defecto: completa los campos opcionales
  services = {
    for name, s in local.services_raw : name => {
      port     = s.port
      replicas = try(s.replicas, 1)
      public   = try(s.public, false)
      tags     = try(s.tags, [])
    }
  }
}

resource "local_file" "service" {
  for_each = local.services

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content = templatefile("${path.module}/templates/service.tftpl", {
    name        = each.key
    prefix      = local.prefix
    environment = var.environment
    service     = each.value
  })
}

# NUEVO (paso 6): expresiones for
locals {
  # for con filtro: solo los servicios publicos
  public_services = { for name, s in local.services : name => s if s.public }

  # for + flatten + distinct: lista unica de tags
  all_tags = sort(distinct(flatten([for s in local.services : s.tags])))
}

# NUEVO (paso 6): count + condicional, solo se crea si hay servicios publicos
resource "local_file" "public_index" {
  count = length(local.public_services) > 0 ? 1 : 0

  filename = "${path.module}/generated/${local.prefix}/public.txt"
  content  = join("\n", [for name, s in local.public_services : "${name} -> :${s.port}"])
}

# CAMBIA (paso 6): el resumen ahora lista servicios y tags
resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = <<-EOT
    # ${local.prefix}
    Responsable: ${random_pet.owner.id}
    Servicios: ${join(", ", sort(keys(local.services)))}
    Tags: ${join(", ", local.all_tags)}
  EOT
}
```

Ejecuta:

```bash
terraform fmt
terraform validate        # Success!
terraform plan
terraform apply           # escribe yes
```

**Esperado:**
- En el `plan`: `public.txt` se crea (`+`) y `SUMMARY.md` se reemplaza (`-/+`).
- Los 3 `.conf` **no** deben cambiar. Si aparecen para destruir, se perdió algo del `main.tf`: vuelve a pegar el bloque completo.
- Al final: `Apply complete! Resources: 2 added, 0 changed, 1 destroyed.`

**Comprueba:**

```bash
cat generated/<usuario>-dev/public.txt      # solo api y web
cat generated/<usuario>-dev/SUMMARY.md      # tags sin repetir
```

**Experimento 1: la consola de Terraform.** Sirve para probar expresiones sin cambiar nada.

```bash
terraform console
```

Terraform muestra su propio prompt `>`. **No escribas el `>`**: escribe solo la expresión y pulsa Enter. Prueba estas, una por una:

| Escribe | Esperado (con el YAML de la guía) |
|---|---|
| `local.public_services` | un mapa con `api` y `web` |
| `[for n, s in local.services : n if s.replicas > 1]` | `["api", "worker"]` |
| `length(local.all_tags)` | `3` |

Para salir: escribe `exit` o pulsa `Ctrl+D`. Si se queda sin responder, pulsa `Ctrl+C`.

**Experimento 2: el `count`.** Pon `public: false` a `api` y `web` en el YAML y haz `terraform plan`: `public.txt` se destruye porque ya no hay servicios públicos. Revierte el cambio.

**Commit de control:**

```bash
cd ../../..
git add env/dev/<usuario>
git commit -m "feature: add for expressions and conditional file"
cd env/dev/<usuario>
```

---

### Paso 7. `for` anidado y `for_each` calculado (2 min)

**Concepto.** Un `for` dentro de otro `for` permite crear una instancia por cada réplica de cada servicio (por ejemplo `worker-1`, `worker-2`, `worker-3`). `for_each` puede recorrer un mapa que tú mismo calculas.

**Reemplaza todo el contenido de `main.tf`.** Lo nuevo está marcado con `# NUEVO (paso 7)`:

```hcl
resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

locals {
  # yamldecode + file: la configuracion vive en un archivo versionado
  services_raw = yamldecode(file("${path.module}/services.yaml")).services

  # for con valores por defecto: completa los campos opcionales
  services = {
    for name, s in local.services_raw : name => {
      port     = s.port
      replicas = try(s.replicas, 1)
      public   = try(s.public, false)
      tags     = try(s.tags, [])
    }
  }
}

resource "local_file" "service" {
  for_each = local.services

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content = templatefile("${path.module}/templates/service.tftpl", {
    name        = each.key
    prefix      = local.prefix
    environment = var.environment
    service     = each.value
  })
}

locals {
  # for con filtro: solo los servicios publicos
  public_services = { for name, s in local.services : name => s if s.public }

  # for + flatten + distinct: lista unica de tags
  all_tags = sort(distinct(flatten([for s in local.services : s.tags])))
}

resource "local_file" "public_index" {
  count = length(local.public_services) > 0 ? 1 : 0

  filename = "${path.module}/generated/${local.prefix}/public.txt"
  content  = join("\n", [for name, s in local.public_services : "${name} -> :${s.port}"])
}

# NUEVO (paso 7): for anidado, una instancia por replica (nombre-1, nombre-2, ...)
locals {
  instances = merge([
    for name, s in local.services : {
      for i in range(s.replicas) : "${name}-${i + 1}" => {
        service = name
        index   = i + 1
        port    = s.port + i
      }
    }
  ]...)
}

# NUEVO (paso 7): un archivo .json por cada instancia
resource "local_file" "instance" {
  for_each = local.instances

  filename = "${path.module}/generated/${local.prefix}/instances/${each.key}.json"
  content = jsonencode({
    id          = each.key
    service     = each.value.service
    port        = each.value.port
    environment = var.environment
  })
}

# CAMBIA (paso 7): el resumen agrega el total de instancias
resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = <<-EOT
    # ${local.prefix}
    Responsable: ${random_pet.owner.id}
    Servicios: ${join(", ", sort(keys(local.services)))}
    Tags: ${join(", ", local.all_tags)}
    Instancias: ${length(local.instances)}
  EOT
}
```

Ejecuta `terraform fmt`, `terraform validate`, `terraform plan` y `terraform apply`.

**Esperado:** `Apply complete! Resources: 7 added, 0 changed, 1 destroyed.` (6 archivos `.json` y el resumen reemplazado).

**Comprueba:** `ls generated/<usuario>-dev/instances` muestra `api-1.json`, `api-2.json`, `web-1.json`, `worker-1.json`, `worker-2.json` y `worker-3.json`.

**Experimento:** cambia `replicas` de `worker` a `2` en el YAML y haz `terraform plan`: solo se destruye `worker-3`. Así escala Terraform: cambias un dato y solo se ajusta la diferencia. Revierte el cambio.

---

### Paso 8. Reglas de validación con `precondition` (1 min)

**Concepto.** Una `precondition` detiene el `plan`/`apply` si los datos no cumplen una regla, antes de crear nada. Las validaciones de `variable` solo ven la variable; para validar datos calculados (como lo que viene del YAML) se usa `precondition`.

**Reemplaza todo el contenido de `main.tf`.** Lo nuevo está marcado con `# NUEVO (paso 8)`:

```hcl
resource "random_pet" "owner" {
  length = 2
}

locals {
  prefix = "${var.owner}-${var.environment}"
}

locals {
  # yamldecode + file: la configuracion vive en un archivo versionado
  services_raw = yamldecode(file("${path.module}/services.yaml")).services

  # for con valores por defecto: completa los campos opcionales
  services = {
    for name, s in local.services_raw : name => {
      port     = s.port
      replicas = try(s.replicas, 1)
      public   = try(s.public, false)
      tags     = try(s.tags, [])
    }
  }
}

# NUEVO (paso 8): reglas que deben cumplirse antes de crear los servicios
resource "terraform_data" "reglas" {
  lifecycle {
    precondition {
      condition     = alltrue([for s in local.services : s.port >= 1024 && s.port <= 65000])
      error_message = "Todos los puertos deben estar entre 1024 y 65000."
    }

    precondition {
      condition     = length(distinct([for s in local.services : s.port])) == length(local.services)
      error_message = "Dos servicios no pueden usar el mismo puerto."
    }
  }
}

# CAMBIA (paso 8): depends_on hace que los servicios esperen a las reglas
resource "local_file" "service" {
  for_each   = local.services
  depends_on = [terraform_data.reglas]

  filename = "${path.module}/generated/${local.prefix}/${each.key}.conf"
  content = templatefile("${path.module}/templates/service.tftpl", {
    name        = each.key
    prefix      = local.prefix
    environment = var.environment
    service     = each.value
  })
}

locals {
  # for con filtro: solo los servicios publicos
  public_services = { for name, s in local.services : name => s if s.public }

  # for + flatten + distinct: lista unica de tags
  all_tags = sort(distinct(flatten([for s in local.services : s.tags])))
}

resource "local_file" "public_index" {
  count = length(local.public_services) > 0 ? 1 : 0

  filename = "${path.module}/generated/${local.prefix}/public.txt"
  content  = join("\n", [for name, s in local.public_services : "${name} -> :${s.port}"])
}

locals {
  # for anidado: una instancia por replica (nombre-1, nombre-2, ...)
  instances = merge([
    for name, s in local.services : {
      for i in range(s.replicas) : "${name}-${i + 1}" => {
        service = name
        index   = i + 1
        port    = s.port + i
      }
    }
  ]...)
}

resource "local_file" "instance" {
  for_each = local.instances

  filename = "${path.module}/generated/${local.prefix}/instances/${each.key}.json"
  content = jsonencode({
    id          = each.key
    service     = each.value.service
    port        = each.value.port
    environment = var.environment
  })
}

resource "local_file" "summary" {
  filename = "${path.module}/generated/${local.prefix}/SUMMARY.md"
  content  = <<-EOT
    # ${local.prefix}
    Responsable: ${random_pet.owner.id}
    Servicios: ${join(", ", sort(keys(local.services)))}
    Tags: ${join(", ", local.all_tags)}
    Instancias: ${length(local.instances)}
  EOT
}
```

Ejecuta `terraform fmt`, `terraform validate`, `terraform plan` y `terraform apply`.

**Esperado:** `Apply complete! Resources: 1 added, 0 changed, 0 destroyed.` (solo `terraform_data.reglas`).

**Experimento:** en `services.yaml` pon el mismo puerto en dos servicios (por ejemplo `8080` en `web`) y ejecuta `terraform plan`:

```
Error: Resource precondition failed
Dos servicios no pueden usar el mismo puerto.
```

Terraform se detuvo antes de crear o cambiar nada. Revierte el cambio en el YAML.

---

### Paso 9. Más outputs (1 min)

**Concepto.** Los outputs resumen lo importante al terminar. Aquí usas un `for` también dentro de un output.

**Reemplaza todo el contenido de `outputs.tf`:**

```hcl
output "responsable" {
  description = "Nombre aleatorio asignado."
  value       = random_pet.owner.id
}

output "instancias" {
  description = "Lista ordenada de instancias."
  value       = sort(keys(local.instances))
}

output "servicios_publicos" {
  description = "Servicios publicos y su puerto."
  value       = { for name, s in local.public_services : name => s.port }
}
```

Ejecuta `terraform apply` y luego `terraform output`.

**Esperado:** `Apply complete! Resources: 0 added, 0 changed, 0 destroyed.` y `terraform output` muestra `responsable`, la lista de 6 instancias y los servicios públicos `api = 8080` y `web = 3000`.

---

### Verificación final de la Parte 3

```bash
terraform fmt -check     # sin salida = formato correcto
terraform validate       # Success! The configuration is valid.
terraform plan           # No changes
terraform state list     # debe listar 13 recursos
```

Registra los hashes del lock para todos los sistemas operativos (el CI corre en Linux y tú en Windows):

```bash
terraform providers lock -platform=linux_amd64 -platform=windows_amd64 -platform=darwin_arm64 -platform=darwin_amd64
```

### Mapa de conceptos

| Concepto | Paso | Dónde |
|---|---|---|
| Providers, resource, output | 1 | `versions.tf`, `main.tf`, `outputs.tf` |
| Variables y validaciones, `locals` | 2 | `variables.tf`, `locals` |
| `for_each` | 3, 7 | `local_file.service`, `local_file.instance` |
| Datos como código, `yamldecode`, `try` | 4 | `services.yaml` |
| `templatefile` con bucle | 5 | `templates/service.tftpl` |
| `for` con filtro, `flatten`, `distinct`, `count` | 6 | `public_services`, `all_tags`, `public_index` |
| `for` anidado | 7 | `instances` |
| `precondition`, `depends_on` | 8 | `terraform_data.reglas` |
| Outputs con `for` | 9 | `outputs.tf` |

---

## Parte 4. Commit y push (2 min)

Un **commit** guarda tus cambios localmente. Un **push** los sube a GitHub para que otros los vean.

```bash
cd ../../..                     # vuelve a la raíz del repo
git status                      # deben aparecer env/dev/<usuario>; NO tfstate, .terraform ni generated
git add env/dev/<usuario>
git commit -m "feature: complete dev layer for <usuario>"
git push -u origin feature/<usuario>-capa-dev
```

El `-u` solo se usa la primera vez que subes una rama: enlaza tu rama local con la de GitHub. La primera vez puede abrirse el navegador para que inicies sesión.

Si `git status` muestra `terraform.tfstate` o `generated/` como pendientes, detente: revisa el `.gitignore`.

Buena práctica: haz un commit por paso (o por grupo de pasos), no uno solo gigante. Así, si algo sale mal, `git log --oneline` te muestra dónde volver.

---

## Parte 5. Pull Request y CI (4 min)

Un **Pull Request (PR)** es una solicitud para que tu rama se una con `development`. Otra persona la revisa y el CI (un robot) la comprueba automáticamente.

### 5.1 Crear el PR (desde la web)

1. Después del `git push`, Git imprime un enlace del tipo `https://github.com/.../pull/new/<rama>`: ábrelo. Si no lo ves, entra al repo en GitHub: aparece un banner amarillo **"Compare & pull request"**.
2. Cambia **base** a `development` (nunca `main`). La rama de comparación (compare) es la tuya.
3. Pon un título con la convención: `feature: add dev layer for <usuario>`, y una breve descripción.
4. Pulsa **Create pull request**.

### 5.2 Ver el resultado del CI

En el PR, baja hasta la sección de checks (o abre la pestaña **Checks**). Cada línea verde o roja es un job. En uno rojo pulsa **Details** para leer el log y busca el primer `Error`.

| Job | Qué verifica | Si falla |
|---|---|---|
| `ci/terraform` | `terraform fmt -check` y `validate` en `env/dev/*` y `env/pre/*` | ejecuta `terraform fmt` y `terraform validate` en tu carpeta |
| `ci/security-scan` | Checkov revisa problemas de seguridad en `env/` | lee el mensaje del check y corrige el recurso |
| `ci/secret-scan` | Gitleaks busca secretos en los commits | rota el secreto y limpia el historial |
| `ci/meta-lint` | `actionlint` revisa la sintaxis de los workflows | corrige el YAML del workflow |

**Forzar un fallo de formato (opcional).** En `main.tf` añade espacios de más en una línea, haz commit y push, y mira cómo falla `ci/terraform`. Arréglalo con:

```bash
terraform fmt
git commit -am "fix: terraform fmt"
git push
```

El PR se actualiza solo con cada push y el CI vuelve a correr.

### 5.3 Revisión cruzada y merge

Cada persona revisa el PR de su pareja:
1. Pestaña **Files changed**.
2. Botón **Review changes**, elige **Approve** y comenta qué revisaste.
3. Con el CI en verde y aprobado, pulsa **Merge pull request**.

Qué revisar: que no haya secretos, que solo toque su carpeta, que `fmt` y `validate` pasen y que el `.terraform.lock.hcl` esté incluido.

Después de integrar, actualiza tu computador:

```bash
git switch development
git pull
```

---

## Parte 6. Escenarios de error y conflictos (6 min)

Un **conflicto** ocurre cuando dos personas cambian las mismas líneas de un archivo y Git no sabe cuál conservar. No es un error grave: Git te pide que decidas. Haz los escenarios que alcances; **el 1 y el 2 son los más importantes**. Cada uno tiene síntoma, causa y solución.

### Escenario 1. Conflicto en un archivo compartido (todos)

Todos agregan una fila al final de `docs/participantes.md`. Es un archivo compartido, así que los cambios chocarán.

```bash
git switch development && git pull
git switch -c docs/<usuario>-participante
```

Añade al **final** de `docs/participantes.md` una fila con tus datos:

```
| <usuario> | Tu Nombre | A o B de la pareja X |
```

```bash
git add docs/participantes.md
git commit -m "docs: add <usuario> to participants"
git push -u origin docs/<usuario>-participante
```

Abre el PR hacia `development` (como en 5.1). El primero en integrar no tendrá problemas. Los siguientes verán en el PR el mensaje **"This branch has conflicts that must be resolved"**. Se resuelve en tu computador:

```bash
git fetch origin
git merge origin/development --no-edit
```

Salida esperada:

```
CONFLICT (content): Merge conflict in docs/participantes.md
Automatic merge failed; fix conflicts and then commit the result.
```

```bash
git status                    # lista el archivo como "both modified"
```

Abre el archivo (`code docs/participantes.md`). Git dejó marcas dentro del texto:

```
<<<<<<< HEAD
| ana | Ana Lopez | A de la pareja 1 |
=======
| luis | Luis Perez | B de la pareja 1 |
>>>>>>> origin/development
```

- Entre `<<<<<<< HEAD` y `=======` está **tu** versión.
- Entre `=======` y `>>>>>>>` está la versión que viene de `development`.

Para una lista, conserva **ambas** filas y borra las tres líneas marcadoras (`<<<<<<<`, `=======` y `>>>>>>>`):

```
| ana | Ana Lopez | A de la pareja 1 |
| luis | Luis Perez | B de la pareja 1 |
```

Guarda el archivo y termina el merge:

```bash
git add docs/participantes.md
git commit -m "fix: resolve merge conflict in participantes.md"
git push
```

Comprobación: este comando no debe imprimir nada (significa que no quedaron marcas):

```bash
grep -n '<<<<\|>>>>\|====' docs/participantes.md
```

Si te enredas, puedes cancelar el merge y empezar de nuevo: `git merge --abort`.

### Escenario 2. Conflicto en la misma línea (en pareja)

Persona A es la dueña de la carpeta `env/dev/<usuarioA>`. Persona B también modifica esa carpeta. Ambos parten del mismo punto de `development` (después de que A haya integrado su PR de la Parte 5).

**Persona A:**

```bash
git switch development && git pull
git switch -c feature/<usuarioA>-puerto-api
```

En `env/dev/<usuarioA>/services.yaml` cambia el puerto de `api` a `8081`, y luego:

```bash
git commit -am "feature: change api port to 8081"
git push -u origin feature/<usuarioA>-puerto-api
```

**Persona B** (desde el mismo punto, en su propia rama):

```bash
git switch development && git pull
git switch -c feature/<usuarioB>-puerto-api
```

En el mismo archivo de A cambia el puerto de `api` a `8082`, y luego:

```bash
git commit -am "feature: change api port to 8082"
git push -u origin feature/<usuarioB>-puerto-api
```

A integra su PR primero. Cuando B intente integrar el suyo, tendrá un conflicto sobre la **misma línea** y deben decidir hablando cuál valor queda. Se resuelve como en el Escenario 1, dejando una sola línea `port:`.

Después de resolver, **valida siempre** que quedó bien:

```bash
terraform -chdir=env/dev/<usuarioA> validate
terraform -chdir=env/dev/<usuarioA> plan
```

(`-chdir` ejecuta Terraform dentro de esa carpeta sin tener que entrar a ella.) Un conflicto mal resuelto puede dejar el YAML o el código roto aunque Git no se queje. Por eso `validate` es obligatorio.

### Escenario 3. Push rechazado

Síntoma:

```
! [rejected]  feature/... -> feature/... (fetch first)
error: failed to push some refs
```

Causa: alguien subió commits a esa rama antes que tú (por ejemplo tu pareja), y tu copia está desactualizada.

```bash
git pull
git push
```

Nunca lo resuelvas con `--force`: borrarías el trabajo de la otra persona.

### Escenario 4. Error de validación en Terraform

En tu `services.yaml` añade un servicio con un puerto repetido:

```yaml
  admin:
    port: 8080
```

```bash
terraform plan
```

Salida esperada:

```
Error: Resource precondition failed
Dos servicios no pueden usar el mismo puerto.
```

Corrige el puerto, o descarta el cambio con `git restore env/dev/<usuario>/services.yaml`. Prueba también `TF_VAR_owner=A terraform plan` y lee el error de la validación de la variable `owner`.

### Escenario 5. Hiciste commit en la rama equivocada

Hiciste un commit directo en `development` o `main` (local), y todavía **no** hiciste push.

```bash
git branch --show-current              # confirma que estás en la rama equivocada
git branch feature/<usuario>-rescate   # guarda tu commit en una rama nueva
git reset --hard origin/development    # deja la rama local igual que la remota
git switch feature/<usuario>-rescate   # vuelve a tu trabajo, que sigue ahí
```

`reset --hard` descarta cambios que no estén guardados. Úsalo solo cuando tu trabajo ya está a salvo en la rama de rescate. Si intentas `git push` a una rama protegida, GitHub lo rechaza con un mensaje de regla de repositorio. Es el comportamiento esperado.

### Escenario 6. Casi subes un archivo que no debías

Simulemos un archivo con una contraseña falsa:

```bash
echo 'password = "no-real"' > env/dev/<usuario>/secreto.tfvars
git status               # no aparece: *.tfvars está en .gitignore. Así funciona la protección
git add -f env/dev/<usuario>/secreto.tfvars    # -f ignora el .gitignore. NO lo hagas en la vida real
git commit -m "chore: test"
```

Cómo deshacerlo **antes del push**:

```bash
git reset --soft HEAD~1                              # deshace el commit y conserva los cambios
git restore --staged env/dev/<usuario>/secreto.tfvars
rm env/dev/<usuario>/secreto.tfvars
```

Si ya hiciste push de un secreto real: considéralo comprometido. Cámbialo (genera uno nuevo) de inmediato y avisa al equipo. Borrar el archivo en un commit nuevo no basta, porque queda en el historial, y el job `ci/secret-scan` lo detectará.

Si subiste el estado por error: `git rm --cached env/dev/<usuario>/terraform.tfstate` y confirma que `*.tfstate` sigue en `.gitignore`.

### Escenario 7. Drift: alguien cambia algo a mano

*Drift* es la diferencia entre lo que Terraform cree que existe y lo que existe de verdad.

```bash
rm env/dev/<usuario>/generated/<usuario>-dev/web.conf
terraform -chdir=env/dev/<usuario> plan
```

Terraform detecta que falta y propone recrearlo. Aplícalo con `terraform apply` dentro de tu carpeta. Ahora cambia a mano el contenido de `api.conf` y repite `plan`: propone reemplazarlo. Lección: **lo que se cambia a mano se pierde en el siguiente `apply`**. Todo cambio debe hacerse en el código y pasar por Git.

### Escenario 8. Conflicto en `.terraform.lock.hcl`

Si dos ramas cambian el lock de la misma carpeta, no lo edites a mano:

```bash
git checkout --theirs env/dev/<usuario>/.terraform.lock.hcl     # toma la versión del otro lado
terraform -chdir=env/dev/<usuario> init -upgrade                # regenera el lock con las versiones permitidas
git add env/dev/<usuario>/.terraform.lock.hcl
git commit --no-edit
```

### Escenario 9. El estado es local y no se comparte

Compara con tu pareja el `terraform output responsable` de la misma carpeta: serán distintos, porque cada uno tiene su propio `terraform.tfstate`. En un equipo real se usa un *backend remoto* (S3, Azure Storage, Terraform Cloud) con bloqueo, para que dos personas no apliquen a la vez. Aquí es solo una demostración: no uses estado local en entornos compartidos.

---

## Parte 7. Limpieza y cierre (2 min)

```bash
terraform -chdir=env/dev/<usuario> destroy     # escribe yes; borra los archivos generados
git switch development
git pull
git branch -d feature/<usuario>-capa-dev       # borra la rama local ya integrada
git push origin --delete feature/<usuario>-capa-dev    # borra la rama remota
git fetch --prune
git log --oneline --graph --all -n 15
```

`git branch -d` solo borra ramas ya integradas. Si Git se queja, revisa antes de usar `-D` (que sí puede perder trabajo). GitHub también ofrece el botón **Delete branch** después del merge.

## Checklist final

- [ ] `terraform fmt -check` sin diferencias.
- [ ] `terraform validate` correcto.
- [ ] `terraform plan` sin cambios pendientes después del `apply`.
- [ ] `git status` limpio, y sin `tfstate`, `.terraform/`, `generated/` ni `*.tfvars` en el historial.
- [ ] PR revisado por tu pareja y con CI en verde.
- [ ] Rama de trabajo borrada.

## Reto extra (si sobra tiempo)

1. Convertir tu capa en un módulo reutilizable en `modules/` y llamarlo desde `env/dev/<usuario>` con un bloque `module`.
2. Crear `env/pre/<usuario>/` con su propio YAML y `environment = "pre"`. El CI también valida esa carpeta.
3. Añadir un `output` con un mapa `tag -> lista de servicios` usando un `for` con agrupación (`...`).
4. Añadir una `precondition` que exija que los servicios con `public: true` tengan el tag `frontend` o `backend`.
5. Usar `terraform_data` con `triggers_replace` para regenerar `SUMMARY.md` cuando cambie `services.yaml`.

---

## Errores comunes y cómo resolverlos

| Mensaje | Qué significa | Solución |
|---|---|---|
| `Error: No configuration files` | Estás en una carpeta sin archivos `.tf` (la raíz del repo o `templates`). | `pwd` y `ls *.tf`. Entra a tu carpeta: `cd env/dev/<usuario>`. Recuerda que `validate` no lo detecta. |
| `Reference to undeclared local value ... "services"` | Falta el bloque `locals` que define `services`. | Vuelve a pegar el `main.tf` completo del paso en el que estás. |
| `Duplicate resource "local_file" configuration` | Hay dos recursos con el mismo nombre en `main.tf`. | Reemplaza todo `main.tf` por el del paso, no lo edites por partes. |
| Terraform pregunta `var.owner` | Falta la variable de entorno (por ejemplo, abriste otra ventana). | `export TF_VAR_owner=<usuario>` |
| `Error: Inconsistent dependency lock file` o `Missing required provider` | Falta descargar los providers. | `terraform init` |
| `Invalid value for variable` | Tu `owner` o `environment` no cumple la validación. | Revisa el mensaje: `owner` solo admite minúsculas, números y guiones (3 a 21). |
| `Resource precondition failed` | Puertos repetidos o fuera de rango en `services.yaml`. | Corrige el puerto en el YAML. |
| `terraform: command not found` | Terraform no está instalado o Git Bash no se reinició. | Repite el paso 1.2 y reabre Git Bash. |
| `terraform console` no responde | Escribiste el `>` como parte del comando, y Terraform espera más texto. | `Ctrl+C`, abre la consola otra vez y escribe solo la expresión. |
| `Permission denied` o `403` al hacer push | No aceptaste la invitación de colaborador, o usas otra cuenta. | Acepta la invitación (1.5) o inicia sesión con la cuenta correcta. |
| `! [rejected] ... (fetch first)` | La rama remota tiene commits que no tienes. | `git pull` y luego `git push` (Escenario 3). |
| `CONFLICT (content): Merge conflict in ...` | Dos cambios chocan en las mismas líneas. | Escenario 1. Para cancelar: `git merge --abort`. |
| `fatal: not a git repository` | No estás dentro de la carpeta del repo. | `cd ~/practica-git-terraform` |
| `error: pathspec '...' did not match` | Escribiste mal la rama o la ruta. | Revisa con `git branch -a` y `ls`. |
| `git status` muestra `terraform.tfstate`, `.terraform` o `generated` | El `.gitignore` no está aplicando. | Actualiza `development` (`git pull`) y revisa que `.gitignore` incluya `generated/`. |
| Un check del PR falla en `ci/terraform` | Formato o sintaxis. | `terraform fmt` y `terraform validate` en tu carpeta, y vuelve a hacer push. |

Para cualquier error, la rutina de revisión es:
1. Lee el mensaje completo, de arriba abajo. Normalmente la causa está en las primeras líneas.
2. `pwd` y `ls`: ¿estás en la carpeta correcta, y existen los archivos?
3. `git status`: ¿en qué rama estás y qué cambió?
4. Si no logras avanzar, pega el mensaje completo a tu pareja o al instructor.

## Glosario rápido

- **Repositorio (repo)**: carpeta de código con todo su historial.
- **Rama (branch)**: línea de trabajo paralela. **Commit**: foto del código en un momento.
- **Merge**: unir dos ramas. **Conflicto**: Git no sabe cuál de dos cambios en las mismas líneas conservar.
- **PR (Pull Request)**: solicitud para integrar tu rama, con revisión y CI.
- **CI**: comprobaciones automáticas que corren en cada PR.
- **Provider**: plugin de Terraform que sabe crear un tipo de recurso. **Resource**: algo que Terraform crea.
- **State (`terraform.tfstate`)**: archivo donde Terraform recuerda qué creó. **Drift**: diferencia entre el estado y la realidad.
- **Plan**: simulación de cambios. **Apply**: ejecución real. **Idempotencia**: repetir el `apply` no cambia nada.
- **Variable**: dato de entrada. **Local**: valor calculado interno. **Output**: dato que se muestra al terminar.


