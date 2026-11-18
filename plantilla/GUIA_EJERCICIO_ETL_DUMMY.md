# Ejercicio práctico: tu primer job ETL en AWS Glue

Guía paso a paso para ingenieros de datos del Proyecto Genesis. Ambiente **dev**, cuenta `026249143253`, región `us-east-1`.

Vas a partir de un job que **ya está publicado** (`bronze_to_silver_local_source_finance`), entender cada pieza, probarlo en un notebook, copiarlo con tu propio nombre, publicarlo y ejecutarlo en Glue. Al final verás el resultado en CloudWatch, en Athena y en la consola de Glue.

**Qué aprenderás, en orden:**

| # | Paso | Qué haces |
|---|---|---|
| 0 | Mapa | Entender la arquitectura del ejercicio |
| 1 | Prerrequisitos | Instalar y verificar herramientas |
| 2 | Acceso | Primer ingreso, MFA, clave CLI, perfil y rol con MFA |
| 3 | Insumos | Ver qué datos entran (Parquet y CSV) |
| 4 | Lectura | Cómo se leen los archivos en el código |
| 5 | Lógica de negocio | Cada regla, con su código y su efecto |
| 6 | Calidad | Reglas críticas y warning, y cómo leer sus resultados |
| 7 | Notebook | Probar todo sin tocar Silver |
| 8 | Tu pipeline | Crear tu pipeline desde la plantilla (config, calidad, código y notebook) |
| 9 | Publicar | PR al repo de Glue y bootstrap de la tabla |
| 10 | Catálogo | PR que crea el job en Glue |
| 11 | Permisos | PR de Lake Formation para tu rol y el rol de sesión |
| 12 | Ejecutar | Lanzar el job en Glue |
| 13 | Verificar | CloudWatch, `run_summary.json`, Athena e idempotencia |
| 14 | Problemas | Qué hacer cuando algo falla |

> **Regla del proyecto:** nadie cambia recursos a mano en AWS. Todo cambio llega por PR, CI y pipeline. Tú puedes leer, asumir tu rol con MFA, usar notebooks, lanzar tu job y consultar su tabla.

---

## 0. Mapa del ejercicio

```
Bronze  s3://beathub-genesis-dev-s3-bronze/source=local-source/
 ├── entity=finance/year=2026/month=11/day=17/*.parquet   transacciones (180 filas, 2 archivos)
 └── entity=catalogs/year=2026/month=11/day=17/*.csv      catálogos (3 archivos, misma cabecera)
            │
            ▼  Glue Job  beathub-genesis-dev-glue-bronze-silver-local-source-finance
            │  leer → cruzar → calidad (bloqueante) → MERGE → verificar
            ▼
Silver  beathub_genesis_dev_silver_catalogo_db.beathub_genesis_silver_finance_transacciones  (Iceberg)
            │
            ▼  Athena (workgroup beathub-genesis-dev-wg) con el rol del Data Engineer
```

Cada pieza vive en un repo distinto:

| Pieza | Repo y ruta | Quién la cambia |
|---|---|---|
| Código del pipeline | `beathub-data-pipeline-whorders` → `glue/pipelines/<pipeline>/` | Tú, por PR a `development` |
| Notebook de prueba | `beathub-data-pipeline-whorders` → `notebooks/` | Tú |
| Job en el catálogo | `beathub-data-infra-whorders` → `catalog/orquestacion.yaml` | Tú, por PR a `development` |
| Permisos Lake Formation | `beathub-data-infra-whorders` → `env/dev/datalake/13-lf-*.tf` | Tú, por PR a `development` |
| Tabla Silver | la crea el bootstrap del CI/CD | Automático al publicar el pipeline |
| Datos de Bronze | `s3://beathub-genesis-dev-s3-bronze/` | Plataforma (no escribes en Bronze) |

---

## 1. Prerrequisitos

Verifica cada herramienta en PowerShell antes de seguir.

> **Shell:** todos los comandos de esta guía son **PowerShell** (Windows PowerShell 5.1 o PowerShell 7). Los bloques `python`, `sql`, `yaml`, `hcl` y `json` son código para pegar en archivos o en el notebook, no comandos de terminal.

> **Carpeta de trabajo:** cada bloque de comandos asume que estás dentro de la **carpeta raíz** del repo que indica el paso: la que contiene `scripts\` y `glue\` (pipeline), o `catalog\` (infra). Para abrir PowerShell ahí: en el Explorador de archivos entra a esa carpeta, haz clic en la barra de direcciones, escribe `powershell` y pulsa Enter. Verifica con `Get-Location`: la última parte de la ruta debe ser el nombre del repo.

| Herramienta | Versión | Comprobar |
|---|---|---|
| Python | 3.11 | `python --version` → `Python 3.11.x` |
| AWS CLI | v2 | `aws --version` → `aws-cli/2.x` |
| Git | cualquiera reciente | `git --version` |
| Acceso a GitHub | org `Tuboleta` | Abrir `https://github.com/Tuboleta/beathub-data-pipeline-whorders` en el navegador |
| VS Code | cualquiera | Extensiones *Python* y *Jupyter* instaladas |
| App de MFA | Authenticator u otra | Dispositivo MFA registrado en tu usuario (ver sección 2.2) |

**No necesitas instalar Spark ni Java.** El Spark del ejercicio corre en AWS Glue 5.1 (Spark 3.5, Python 3.11). El notebook usa **Glue Interactive Sessions**. Spark local en Windows exige `winutils.exe` y suele fallar con `loopback connection`; no lo uses para este ejercicio.

Instala el kernel del notebook en el **mismo** Python que usa VS Code:

```powershell
pip install --upgrade aws-glue-sessions
pip install pytest
$pkg = python -c "import aws_glue_interactive_sessions_kernel as k, os; print(os.path.dirname(k.__file__))"
jupyter kernelspec install --user "$pkg\glue_pyspark"
jupyter kernelspec install --user "$pkg\glue_spark"
```

**Obligatorio en Windows:** el kernel debe apuntar a tu `python.exe` completo. Obtén la ruta:

```powershell
python -c "import sys; print(sys.executable)"
```

Abre `$env:APPDATA\jupyter\kernels\glue_pyspark\kernel.json` y cambia el primer elemento de `argv` (`"python"`) por esa ruta. Si no lo cambias, VS Code no muestra el kernel *Glue PySpark*.

Clona los dos repos en tu carpeta de trabajo:

```powershell
cd C:\repo\genesis   # una sola vez: carpeta padre donde clonas los repos
git clone https://github.com/Tuboleta/beathub-data-pipeline-whorders.git
git clone https://github.com/Tuboleta/beathub-data-infra-whorders.git
git -C .\beathub-data-pipeline-whorders config user.name
git -C .\beathub-data-pipeline-whorders config user.email
```

Tu nombre y tu correo deben aparecer. Los commits llevan tu identidad, sin coautores.

---

## 2. Acceso a AWS: primer ingreso, MFA, CLI y rol

Tu administrador crea tu usuario IAM (por ejemplo `blaiberg_sierra_test`), lo añade al grupo `beathub-data-dev-dataengineer` y te entrega una contraseña temporal. Este paso te explica cómo dejarlo operativo.

### 2.1 Primer ingreso a la consola

Entra con la URL de inicio de sesión de la cuenta (la que te dio el administrador, de la forma `https://<alias>.signin.aws.amazon.com/console`), usuario y contraseña temporal. AWS te pide cambiar la contraseña. Elige una nueva y guárdala.

Después del cambio, la consola muestra **muchos errores de acceso denegado**. Es normal: la política del grupo bloquea todo lo que no sea gestionar tu propia cuenta **mientras tu sesión no tenga MFA**. Hasta que registres el MFA, solo puedes:

- Ver tu usuario y cambiar tu contraseña.
- Gestionar tu propio MFA y tus propias claves.

Para no depender del panel, ve directo a tu usuario, con esta forma de URL:

```
https://us-east-1.console.aws.amazon.com/iam/home#/user/<tu_usuario>
```

> **Ojo:** la página `Usuarios de IAM` (lista de usuarios) dará `Acceso denegado a iam:ListUsers`. Es esperado: no tienes permiso para listar usuarios. No la necesitas.

### 2.2 Registrar el MFA (obligatorio)

1. En tu usuario, pestaña **Security credentials** (Credenciales de seguridad).
2. Sección **Multi-factor authentication (MFA)** → **Assign MFA device** (Asignar dispositivo MFA).
3. Nombre del dispositivo: es libre. Recomendado `<tu_usuario>-mfa`, por ejemplo `blaiberg_sierra_test-mfa`. Anótalo; lo usa el administrador si necesita revisarlo.
4. Tipo: **Authenticator app**. Escanea el código QR con tu app (Authenticator, Google Authenticator u otra).
5. Escribe **dos códigos consecutivos** de 6 dígitos y confirma.

Verifica que el MFA quedó **Assigned** en la misma pestaña.

### 2.3 Entrar con MFA

1. **Cierra sesión** de la consola.
2. Vuelve a entrar con usuario y contraseña.
3. AWS te pide el **código MFA** de 6 dígitos. Esta vez sí debe pedirlo.

Si no te lo pide, el MFA no quedó activo: repite 2.2. Mientras la sesión no tenga MFA, seguirás viendo los errores de acceso denegado.

### 2.4 Crear tu access key para la CLI

Con la sesión ya con MFA:

1. En el panel de IAM, en **Quick Links** (Accesos rápidos), abre **Mis credenciales de seguridad** (My security credentials). Eso abre tu propio usuario.
2. Sección **Claves de acceso** (Access keys) → **Crear clave de acceso** (Create access key).
3. Caso de uso: **Interfaz de línea de comandos (CLI)**. Marca la confirmación y crea la clave.
4. Copia el **Access key ID** y el **Secret access key**, o descarga el CSV. **El secret solo se muestra una vez.**

> **Seguridad:** guarda las credenciales en tu gestor de contraseñas o en un lugar seguro. No las pegues en chats, correos, PRs ni en archivos del repo.

### 2.5 Configurar el perfil de la CLI

Configura el perfil **una vez**. Puedes ponerle **el nombre que quieras** (por ejemplo `mi-perfil-dev`). En esta guía ese nombre se guarda en la variable `$Perfil`. Defínela en la terminal antes de cualquier comando:

```powershell
$Perfil = "mi-perfil-dev"   # cambia por el nombre que elegiste
aws configure --profile $Perfil
# AWS Access Key ID: <pégalo cuando te lo pida el comando>
# AWS Secret Access Key: <pégalo cuando te lo pida el comando>
# Default region name: us-east-1
# Default output format: json
```

Verifica que apunta a tu usuario y a la cuenta de dev:

```powershell
aws sts get-caller-identity --profile $Perfil
# Account debe ser 026249143253 y Arn debe terminar en user/<tu_usuario>
```

**Listar los perfiles de tu máquina:**

```powershell
aws configure list-profiles
```

Te devuelve un nombre por línea (por ejemplo `default` y el que creaste). Para ver a qué cuenta y usuario apunta cada uno:

```powershell
foreach ($perfil in aws configure list-profiles) {
    Write-Host "== $perfil"
    aws sts get-caller-identity --profile $perfil --query "[Account,Arn]" --output text 2>$null
}
```

Si un perfil aparece pero el `get-caller-identity` falla, sus credenciales están vencidas o incompletas: vuelve a ejecutar `aws configure --profile <nombre>`.

Para ver en qué perfil y región trabajará la CLI en este momento:

```powershell
echo $env:AWS_PROFILE
aws configure list
```

**Cómo funcionan los perfiles:**

- Un perfil es solo un nombre que apunta a unas credenciales y a una región. El nombre **no** cambia permisos.
- Los comandos de la guía llevan `--profile $Perfil`. Si olvidas `--profile`, se usa el perfil `default`, que en algunas máquinas apunta a otra cuenta. Por eso no lo omitas.
- No hay un nombre fijo. Usa el que quieras, pero define `$Perfil` con ese mismo nombre en **la terminal donde ejecutas los comandos**. Si cierras la terminal, vuelve a definirla. Si `$Perfil` está vacía, el script `assume_dataengineer.ps1` usa el perfil `default`.
- La variable `$env:AWS_PROFILE` también afecta a los comandos si está definida. Revísala con `echo $env:AWS_PROFILE` si algo apunta a una cuenta que no esperas.

### 2.6 Asumir el rol del Data Engineer (con MFA)

El notebook, Athena y la consulta de la tabla se hacen con el **rol** `beathub-data-dev-role-dataengineer`, no con tu usuario. Para asumirlo necesitas un código MFA de tu app. Cada código vale **una sola vez** y dura unos 30 segundos. Si reintentas con el mismo código, AWS lo rechaza.

```powershell
. .\scripts\assume_dataengineer.ps1 -SourceProfile $Perfil   # ojo al punto inicial
aws sts get-caller-identity --query Arn --output text
# arn:aws:sts::026249143253:assumed-role/beathub-data-dev-role-dataengineer/<tu_usuario>
```

Las credenciales del rol duran **1 hora**. Con `ExpiredToken`, vuelve a asumir el rol con un código nuevo.

### 2.7 Qué puedes hacer con tu usuario y qué no

| Acción | Permitido |
|---|---|
| Gestionar tu contraseña, tu MFA y tus claves | Sí |
| Asumir el rol `beathub-data-dev-role-dataengineer` (con MFA) | Sí |
| Leer Glue, logs de Glue, Athena (con el rol) y KMS del proyecto | Sí |
| **Lanzar y parar cualquier job Glue de dev** (`beathub-genesis-dev-glue-*`) | Sí |
| Ver pipelines de CodePipeline y lanzar `beathub-genesis-dev-glue-*-pipeline` | Sí |
| Editar o crear jobs de Glue desde la consola o la CLI | **No**: los cambios van por PR |
| Lanzar el job de bootstrap de tablas | **No**: solo la plataforma |
| Listar usuarios de IAM | **No** |

---

## 3. Insumos, configuración y lectura: qué entra y de dónde

Esta sección te enseña **qué archivo controla cada cosa**, **qué escribir en cada uno** y **cómo saber que el job de verdad leyó tus datos**. Todo lo que ves aquí está en el pipeline publicado: puedes abrirlo mientras lees.

### 3.0 Ubicar la ETL que ya está publicada

No empiezas desde cero: la ETL ya existe. Ubícala en estos cuatro lugares.

**a) En el repo de Glue** (VS Code, carpeta `C:\repo\genesis\beathub-data-pipeline-whorders`):

```
glue\pipelines\bronze_to_silver_local_source_finance\
├── etl_glue.py          ← entrypoint: lo que ejecuta Glue (orquesta todo)
├── business_logic.py    ← transformaciones y reglas de negocio
├── schema.py            ← contrato: columnas de entrada, definición de la tabla Silver
└── config\
    ├── config.json              ← qué entradas lee y qué salida escribe
    ├── quality_rules.json       ← reglas de calidad por tabla
    └── create_tables.athena.sql ← referencia de esquema (no se ejecuta)
notebooks\bronze_to_silver_local_source_finance.ipynb   ← el notebook para probarla
```

La lectura y la escritura **no** están en esta carpeta: están en el framework compartido, `glue\framework\utils.py`.

**b) En el repo de infra** (`C:\repo\genesis\beathub-data-infra-whorders`): `catalog\orquestacion.yaml`, entrada `bronze_to_silver_local_source_finance`. Ahí se declara que el job existe y en qué ambiente.

**c) En la consola de Glue**: Glue → **ETL jobs** → `beathub-genesis-dev-glue-bronze-silver-local-source-finance`. En **Job details** ves el *Script path*, los *Job parameters* (aquí viven el bucket de Bronze, la base de Silver y el prefijo `source=local-source`) y el rol.

**d) En S3**: bucket `beathub-genesis-dev-s3-bronze`, carpeta `source=local-source/`. Son los datos de entrada.

### 3.1 Qué archivo controla qué

Antes de tocar nada, entiende qué manda cada pieza. Si cambias algo en el archivo equivocado, el job falla o no hace lo que esperas.

| Archivo | Qué controla | Si cambias algo aquí… |
|---|---|---|
| `config/config.json` | **Qué** entradas lee y **qué** tabla escribe (formato y capa) | Cambia de dónde lee y a qué tabla escribe |
| `config/quality_rules.json` | Las reglas de calidad de cada tabla de salida | Cambia qué bloquea el lote y qué solo avisa |
| `schema.py` | Columnas que espera de entrada, definición de la tabla Silver, clave del MERGE | Cambia el contrato: lo que se valida y lo que se crea |
| `business_logic.py` | Las transformaciones: cruces, signos, conversiones | Cambia el resultado de los datos |
| `etl_glue.py` | El orden de ejecución y los **nombres** con los que se conectan las entradas | Si cambias un nombre de entrada, hay que cambiarlo aquí también |
| Parámetros del job (Terraform) | El **dónde**: bucket de Bronze, base de Silver, warehouse, prefijo `source=` | No lo cambias tú: lo define la plataforma por PR |

El flujo completo es: `config.json` (qué) + parámetros del job (dónde) → lectura → `business_logic.py` (transforma) → validación con `quality_rules.json` → escritura según `config.json` y `schema.py`.

### 3.2 `config.json`, campo por campo

Este es el archivo publicado (los campos `description` se omiten aquí):

```json
{
  "pipeline": "bronze_to_silver_local_source_finance",
  "inputs": {
    "finance": {
      "layer": "bronze",
      "format": "parquet",
      "prefix": "entity=finance/"
    },
    "catalogs": {
      "layer": "bronze",
      "format": "csv",
      "prefix": "entity=catalogs/",
      "options": {
        "header": "true",
        "delimiter": ",",
        "inferSchema": "false",
        "encoding": "UTF-8"
      }
    }
  },
  "outputs": {
    "beathub_genesis_silver_finance_transacciones": {
      "layer": "silver",
      "format": "iceberg"
    }
  }
}
```

**Campo por campo:**

| Campo | Qué es | Valores válidos | Qué pasa si está mal o falta |
|---|---|---|---|
| `pipeline` | Nombre del pipeline | Debe ser **igual** al nombre de la carpeta | `pipeline='...' no coincide con '...'`: el job no arranca |
| `inputs` | Entradas que lee el job | Al menos una | Si está vacío: `inputs esta vacio` |
| `inputs.<nombre>` | El nombre con el que el código la conoce | Libre, pero `etl_glue.py` lo usa (ver 4.2) | Si cambias el nombre aquí y no en `etl_glue.py`, el job no encuentra la entrada |
| `inputs.<nombre>.layer` | Capa de origen | Debe ser `bronze` en un pipeline `bronze_to_silver` | `layer='...' pero el pipeline es ... (esperado 'bronze')` |
| `inputs.<nombre>.format` | Cómo leer los archivos | `json`, `parquet`, `csv` o `iceberg` | `format='...' no soportado (...)`. Este pipeline solo transforma **parquet y csv** |
| `inputs.<nombre>.prefix` | Carpeta dentro de Bronze, relativa a `source=` | Texto, por ejemplo `entity=finance/` | Para parquet y csv es opcional. Si no lo pones, lee **todo** el `source=` |
| `inputs.<nombre>.options` | Opciones del lector de Spark | Por ejemplo `header`, `delimiter`, `inferSchema` | Si no las pones, Spark usa sus valores por defecto. Sin `header: true`, la primera línea del CSV se toma como dato y las columnas quedan con nombres genéricos |
| `outputs` | Tablas que escribe el job | Debe ser **exactamente** la lista de `SILVER_TABLES` en `schema.py` | `outputs [...] != schema.SILVER_TABLES [...]`: el job no arranca |
| `outputs.<tabla>.layer` | Capa de destino | `silver` en un pipeline `bronze_to_silver` | `layer='...' pero el pipeline es ...` |
| `outputs.<tabla>.format` | Cómo escribir | `iceberg` | `format='...' no soportado` |

**Cómo se arma la ruta real de cada entrada.** No escribes la ruta completa: el job la arma así:

```
s3://<bucket de Bronze> / <source_prefix> / <prefix del config> /
s3://beathub-genesis-dev-s3-bronze / source=local-source / entity=finance /
```

- `<bucket de Bronze>` y `<source_prefix>` vienen de los parámetros del job, que pone la plataforma.
- `<prefix del config>` lo pones tú en `config.json`.

Por eso `finance` lee `s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=finance/`.

> **Regla práctica:** si cambias el `prefix`, cambias de carpeta en Bronze. Si cambias el `format`, cambias el lector que usa Spark. Si cambias el `layer`, el validador rechaza el pipeline.

### 3.3 `schema.py`: el contrato de columnas y de la tabla

`schema.py` define cuatro cosas, y se usan en momentos distintos:

**a) Qué columnas debe traer la entrada Parquet** (`FINANCE_SOURCE_SCHEMA`). Antes de transformar, el código comprueba que estén todas. Si falta una, el job se detiene con:

```
La entrada finance no trae las columnas [...]
```

Si agregas una columna que `business_logic.py` necesite, debes agregarla aquí también.

**b) Qué columnas trae el CSV** (`CATALOG_SOURCE_COLUMNS`): `catalog_type, code, name, category, rate_to_cop, active`. Mismo control: si falta una, el job se detiene.

**c) Cómo es la tabla Silver** (`TABLE_DDL`). Aquí defines:

- `columns_ddl`: el nombre y el tipo de cada columna de la tabla de salida.
- `partition_expr`: la partición (`months(process_date)`).
- `match_columns`: la clave del MERGE. Con `transaction_id` y `row_hash`, una fila se inserta una sola vez aunque el job se ejecute varias veces.

**d) La lista de tablas de salida** (`SILVER_TABLES`). Debe coincidir **exactamente** con las claves de `outputs` en `config.json`.

> **Ojo:** el bootstrap crea la tabla **solo si no existe**. Si cambias las columnas de una tabla que ya existe, el bootstrap no la actualiza. Los cambios de esquema sobre una tabla existente requieren una migración, y eso lo hace la plataforma, no el ejercicio.

### 3.4 `quality_rules.json`: qué reglas aplican a cada tabla

El archivo tiene una entrada por tabla de salida, con dos listas:

```json
{
  "tables": {
    "beathub_genesis_silver_finance_transacciones": {
      "critical": ["RowCount > 0", "IsUnique \"transaction_id\""],
      "warning":  ["Completeness \"account_name\" >= 0.95"]
    }
  }
}
```

- La clave de la tabla debe ser **la misma** que en `config.json` y `schema.py`.
- `critical`: si una falla, **no se escribe nada** del lote y el job termina en error.
- `warning`: si una falla, el lote se escribe igual y el resultado queda registrado.

> **Cuidado:** si una tabla no aparece en `quality_rules.json`, el job **no** aplica ninguna regla a esa tabla y no avisa. Por eso la clave debe coincidir exactamente.

Las reglas están en el lenguaje **DQDL** de AWS Glue Data Quality. La sección 6 explica cada una.

### 3.5 Cómo el job lee cada entrada

**El enlace entre `config.json` y el código** es el nombre de la entrada. En `etl_glue.py` aparecen dos constantes:

```python
FINANCE_INPUT = "finance"
CATALOGS_INPUT = "catalogs"
```

Si en `config.json` la entrada se llama `finance`, el código la encuentra. Si la renombras a `transacciones`, debes cambiar también `FINANCE_INPUT` en `etl_glue.py`. Si no, el job no encuentra la entrada.

**Qué lector usa el framework según el formato:**

| `format` | Qué lee | Cómo |
|---|---|---|
| `parquet` | Archivos Parquet bajo el prefijo | Spark lee **todos** los archivos del prefijo, sin deducir columnas de la ruta |
| `csv` | Archivos CSV bajo el prefijo | Igual que parquet, aplicando `options` (cabecera, separador, texto) |
| `json` | Archivos JSON | Igual, con Glue Bookmarks |
| `iceberg` | Una tabla del catálogo | Lee la tabla completa (no archivos sueltos) |

Para parquet y csv, cada archivo que lee añade dos columnas técnicas:

- `source_file_path`: de qué archivo vino cada fila. Sirve para rastrear un dato hasta su archivo.
- `input_name`: el nombre de la entrada (`finance` o `catalogs`).

**Cómo saber que sí leyó tus datos.** Tienes cuatro evidencias, de la más rápida a la más completa:

1. **En el log de la ejecución** (CloudWatch), una línea por entrada:

   ```
   LECTURA | entrada=finance | format=parquet | origen=s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=finance/ | archivos_nuevos=2
   LECTURA | entrada=catalogs | format=csv | origen=s3://.../entity=catalogs/ | archivos_nuevos=3
   ```

   Si `archivos_nuevos=0` o no ves la línea, no leyó nada.

2. **En el notebook, sección 2**: `finance : 2 archivos, 180 filas` y `catalogs: 3 archivos, 13 filas`. Si los números no coinciden, la ruta o el formato están mal.

3. **En el notebook, `printSchema()`**: muestra los tipos y las columnas. Compáralas con `schema.py`.

4. **En `run_summary.json`** (sección 13): el campo `inputs_read` muestra la misma información.

**Qué pasa si no hay archivos.** Si la ruta existe pero no hay datos, el job **no falla**: termina con `SUCCESS_NO_NEW_DATA` y registra `SIN DATOS` en el log. No escribe nada. Revisa Bronze antes de dar por bueno un `SUCCEEDED`.

### 3.6 Qué entra exactamente (los datos del ejercicio)

**Transacciones (Parquet), `entity=finance/`**

| Columna | Tipo | Ejemplo | Regla |
|---|---|---|---|
| `transaction_id` | string | `TXN-0000001` | Única, 11 caracteres |
| `transaction_ts` | timestamp UTC | `2026-11-03 14:22:00` | Obligatoria |
| `account_code` | string | `4105` | Debe existir en el catálogo de cuentas |
| `cost_center_code` | string | `CC01` | Debe existir en el catálogo de centros de costo |
| `currency_code` | string | `COP` | `COP`, `USD` o `EUR` |
| `amount` | decimal(18,2) | `120000.00` | Mayor que 0 |
| `transaction_type` | string | `CREDIT` o `DEBIT` | Define el signo contable |
| `description` | string | `Venta de boleteria - movimiento dummy 1` | Informativa |

2 archivos, 180 filas: `finance_part-00000.parquet` (100) y `finance_part-00001.parquet` (80).

**Catálogos (CSV), `entity=catalogs/`**

Tres archivos con la misma cabecera, para que un solo lector los cargue juntos:

```
catalog_type,code,name,category,rate_to_cop,active
```

| Archivo | `catalog_type` | Filas | Ejemplo de línea |
|---|---|---|---|
| `catalog_accounts.csv` | `ACCOUNT` | 6 | `ACCOUNT,4105,Venta de boleteria,INGRESO,,true` |
| `catalog_cost_centers.csv` | `COST_CENTER` | 4 | `COST_CENTER,CC01,Taquilla,AREA,,true` |
| `catalog_currencies.csv` | `CURRENCY` | 3 | `CURRENCY,USD,Dolar estadounidense,MONEDA,4000.0000,true` |

Los catálogos se leen **todo como texto** (`inferSchema: false`). El código los tipa después. Si Spark infiriera los tipos, el resultado podría cambiar de un lote a otro.

### 3.7 Cómo ver los insumos (dónde mirarlos)

**Opción 1: consola de S3.** Bucket `beathub-genesis-dev-s3-bronze` → `source=local-source/` → `entity=…` → `year=2026/month=11/day=17/`. Debes ver 5 archivos.

**Opción 2: CLI con una sesión MFA de tu usuario.** La clave de acceso sola **no** basta: tu política bloquea todo lo que se haga sin MFA en la sesión (`DenyAllExceptListedIfNoMFA`), y verás `explicit deny`. Pide una sesión temporal con tu código MFA actual:

```powershell
$mfa = aws iam list-mfa-devices --profile $Perfil --query "MFADevices[0].SerialNumber" --output text
$c = aws sts get-session-token --profile $Perfil --serial-number $mfa --token-code <CODIGO_MFA> --query Credentials --output json | ConvertFrom-Json
$env:AWS_ACCESS_KEY_ID = $c.AccessKeyId
$env:AWS_SECRET_ACCESS_KEY = $c.SecretAccessKey
$env:AWS_SESSION_TOKEN = $c.SessionToken
Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue

aws s3 ls s3://beathub-genesis-dev-s3-bronze/source=local-source/ --recursive

Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY, Env:AWS_SESSION_TOKEN
```

Reemplaza `<CODIGO_MFA>` por el código de tu app en ese momento. Debes ver 5 líneas. Al terminar, el último comando borra las credenciales temporales de la terminal.

> **Ojo:** esta sesión es la de tu usuario, no la del rol. El rol del Data Engineer **no** tiene permiso para listar el bucket de Bronze; por eso no sirve para esta revisión.

**Opción 3: dentro del notebook**, con el rol asumido. Es la forma que usa el job:

```python
import boto3
s3 = boto3.client("s3")
resp = s3.list_objects_v2(Bucket="beathub-genesis-dev-s3-bronze", Prefix="source=local-source/")
for o in resp.get("Contents", []):
    print(o["Size"], o["Key"])
```

> **Por qué ves `day=17` y no una hora:** los archivos del ejercicio son de una sola fecha (17/11). El job lee todo el prefijo `source=local-source/`. Esa forma de lectura la define la plataforma en los parámetros del job; tú no la cambias.

Si quieres regenerar datos de prueba **en local** (nunca los subas a Bronze):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install pyarrow==17.0.0
.venv\Scripts\python generar_datos.py
```

---

## 4. Paso a paso — Lectura en el código

### 4.1 Cómo se conecta todo al arrancar

Cuando el job arranca, `etl_glue.py` hace esto, en orden:

1. Lee los parámetros del job (bucket, base, warehouse, prefijo).
2. Lee `config.json` desde S3 y lo **valida** (tabla de 3.2). Si hay errores, se detiene con el mensaje exacto.
3. Combina `config.json` con los parámetros del job para obtener la ruta real de cada entrada y de cada salida. El log lo muestra así:

   ```
   ENTRADA finance | parquet | s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=finance/
   ENTRADA catalogs | csv | s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=catalogs/
   SALIDA  ... | iceberg
   ```

4. Crea la sesión de Spark con el catálogo `glue_catalog` (Iceberg).
5. Lee las entradas (sección 4.2).

Si una de estas líneas no aparece en el log, el problema está en el paso que falla.

### 4.2 La lectura de cada entrada

`etl_glue.py` llama a la lectura una sola vez para todas las entradas:

```python
reads = read_inputs(spark, glue_context, flow)
finance_raw, _ = reads["finance"]      # Parquet
catalogs_raw, _ = reads["catalogs"]    # CSV, todo texto
```

`read_inputs` recorre cada entrada del `config.json` y elige el lector según su `format`. Para parquet y csv, el lector hace lo siguiente:

1. **Busca las rutas que existen.** Si alguna carpeta de la ventana no existe, la omite. Así evita el error `PATH_NOT_FOUND`.
2. **Lee todos los archivos bajo esas rutas** con `recursiveFileLookup`. Sin esta opción, Spark crearía columnas falsas (`source`, `entity`, `year`...) a partir de la carpeta.
3. **Aplica las `options`** del `config.json` (cabecera, separador, texto).
4. **Añade `source_file_path` y `input_name`**.
5. **Cuenta los archivos** y lo registra en la línea `LECTURA | ... | archivos_nuevos=N`.

Si no hay archivos, devuelve `None` y el job termina con `SIN DATOS` (ver 3.5).

### 4.3 Lo que tienes que comprobar al leer

En el notebook, sección 2:

```
finance : 2 archivos, 180 filas
catalogs: 3 archivos, 13 filas
```

Y en `printSchema()`, las columnas de `schema.py`. Si algo no coincide, revisa en este orden:

1. ¿El `prefix` del `config.json` apunta a la carpeta correcta?
2. ¿El `format` coincide con el tipo de archivo?
3. ¿Las `options` del CSV (sobre todo `header`) son las correctas?
4. ¿Los nombres de columna coinciden con `schema.py`?

> Parquet y CSV **no** usan Glue Bookmarks: cada ejecución relee todo Bronze. No duplica datos porque la escritura es un MERGE por `transaction_id + row_hash`.

### 4.4 Cómo recibe la lógica de negocio los datos

`etl_glue.py` pasa los dos DataFrames a la lógica de negocio:

```python
silver_dfs = build_silver_tables(finance_raw, catalogs_raw)
```

`build_silver_tables` devuelve un diccionario **cuya clave es el nombre de la tabla de salida**. Esa clave debe ser igual a una de las claves de `outputs` en `config.json`. Si no coincide, la escritura no encuentra el DataFrame.

Dentro de `business_logic.py`, la primera acción es comprobar que las columnas que necesita existen en la entrada. Si falta alguna, se detiene con un mensaje claro.

### 4.5 Cómo sabes qué cambiar para escribir en otra tabla

La escritura usa cuatro datos, y cada uno vive en un archivo distinto:

| Qué quieres cambiar | Dónde se cambia | Qué más hay que cambiar |
|---|---|---|
| Nombre de la tabla de salida | `config.json` → clave de `outputs` | `schema.py` (`TABLE_DDL` y `SILVER_TABLES`), `business_logic.py` (`TABLE`), `quality_rules.json` (clave de `tables`) |
| Formato de salida | `config.json` → `outputs.<tabla>.format` | Solo `iceberg` está soportado en este pipeline |
| Columnas de la tabla | `schema.py` → `TABLE_DDL.columns_ddl` | `business_logic.py` debe producir esas columnas, con esos tipos |
| Clave del MERGE (no duplicar) | `schema.py` → `match_columns` | Debe identificar cada fila de forma única |

**Qué comprobar después de escribir:**

- En el log: `MERGE COMPLETADO | ... | filas_en_batch=180` y `VERIFICACION OK | ... | filas_del_lote_presentes=180`.
- En `run_summary.json`: el campo `writes` muestra la tabla, las filas escritas y las filas verificadas.
- En Athena: `SELECT count(*)` sobre la tabla nueva.

Si `VERIFICACION` no coincide con `MERGE`, la escritura quedó incompleta y el job aborta.

---

## 5. Paso a paso — Lógica de negocio

La lógica vive en `business_logic.py`. Es Spark SQL nativo, **sin UDFs**, y asume la zona horaria UTC que fija `etl_glue.py`.

### Paso 5.1 — Normalizar los datos de entrada

Los catálogos los escriben personas a mano. Un código `" 5135 "` o `debit` tiene que quedar igual que `5135` o `DEBIT`.

```python
def _code(column: str):
    return F.upper(F.trim(F.col(column)))

def prepare_finance(finance_raw):
    return finance_raw.select(
        F.trim(F.col("transaction_id")).alias("transaction_id"),
        F.col("transaction_ts").cast("timestamp").alias("transaction_ts"),
        _code("transaction_type").alias("transaction_type"),
        _code("account_code").alias("account_code"),
        _code("cost_center_code").alias("cost_center_code"),
        _code("currency_code").alias("currency_code"),
        F.col("amount").cast("decimal(18,2)").alias("amount"),
        F.col("description"),
        F.col("source_file_path"),
    )
```

**Efecto:** las 180 transacciones siguen siendo 180. Solo cambia la forma de los códigos.

### Paso 5.2 — Preparar los catálogos

Dos reglas: solo filas activas, y **un solo registro por código**.

```python
def prepare_catalogs(catalogs_raw):
    active = catalogs_raw.where(F.lower(F.trim(F.col("active"))) == "true").select(
        _code("catalog_type").alias("catalog_type"),
        _code("code").alias("code"),
        F.trim(F.col("name")).alias("name"),
        _code("category").alias("category"),
        F.col("rate_to_cop").cast("decimal(18,4)").alias("rate_to_cop"),
    )
    one_per_code = Window.partitionBy("catalog_type", "code").orderBy(F.col("name").asc())
    return (active.withColumn("_rn", F.row_number().over(one_per_code))
            .where(F.col("_rn") == 1).drop("_rn"))
```

**Por qué:** si un código aparece dos veces en el catálogo, el cruce duplicaría transacciones. Con `row_number` nos quedamos con uno.

### Paso 5.3 — Enriquecer con los catálogos (LEFT JOIN)

```python
accounts      = _catalog(catalogs, "ACCOUNT", "account_code", {"name": "account_name", "category": "account_category"})
cost_centers  = _catalog(catalogs, "COST_CENTER", "cost_center_code", {"name": "cost_center_name"})
currencies    = _catalog(catalogs, "CURRENCY", "currency_code", {"name": "currency_name", "rate_to_cop": "rate_to_cop"})

df = (finance
      .join(F.broadcast(accounts), "account_code", "left")
      .join(F.broadcast(cost_centers), "cost_center_code", "left")
      .join(F.broadcast(currencies), "currency_code", "left"))
```

- **LEFT JOIN:** una transacción nunca se pierde por el cruce. Si un código no existe en el catálogo, el nombre queda en NULL, y lo detecta una regla warning (paso 6).
- **`broadcast`:** los catálogos son pequeños, así que se copian a cada nodo y no se barajan las transacciones.

### Paso 5.4 — Signo contable

```python
sign = F.when(F.col("transaction_type") == "DEBIT", F.lit(-1)).otherwise(F.lit(1))
df = df.withColumn("amount_signed", (F.col("amount") * sign).cast("decimal(18,2)"))
```

CREDIT (ingreso) suma y DEBIT (gasto) resta.

### Paso 5.5 — Convertir a pesos

```python
df = df.withColumn("amount_cop", F.round(F.col("amount_signed") * F.col("rate_to_cop"), 2)
                   .cast("decimal(22,2)"))
```

Con la tasa de cada moneda (COP = 1, USD = 4000, EUR = 4350).

### Paso 5.6 — Partición y técnicas

```python
df = df.withColumn("operation_audit_date", F.current_timestamp())
df = df.withColumn("process_date", F.to_date(F.col("transaction_ts")))   # fecha UTC
df = add_row_hash(df, BUSINESS_COLUMNS)                                   # sha256 del contenido
return df.select(*BUSINESS_COLUMNS, "operation_audit_date", "process_date",
                 "source_file_path", "row_hash").dropDuplicates(["transaction_id", "row_hash"])
```

- `process_date` es la columna de partición (`months(process_date)` en el DDL).
- `row_hash` es la clave de idempotencia: si vuelves a ejecutar con los mismos datos, el hash es el mismo y el MERGE no inserta nada nuevo.

**Resultado esperado** (sección 3 del notebook): `180 filas` y `Esquema OK`, que compara las columnas del DataFrame con `TABLE_DDL`.

---

## 6. Paso a paso — Calidad de datos

Las reglas viven en `config/quality_rules.json` y se evalúan con **Glue Data Quality** (DQDL), sobre el DataFrame ya transformado.

### 6.1 Reglas publicadas

| Severidad | Regla | Qué protege |
|---|---|---|
| **crítica** | `RowCount > 0` | Lote vacío |
| **crítica** | `IsComplete "transaction_id"` y `IsUnique "transaction_id"` | Clave de negocio |
| **crítica** | `IsComplete "transaction_ts"`, `IsComplete "process_date"` | Fecha y partición |
| **crítica** | `IsComplete "amount"`, `ColumnValues "amount" > 0` | Importe válido |
| **crítica** | `ColumnValues "transaction_type" in ["DEBIT", "CREDIT"]` | Signo contable |
| **crítica** | `IsComplete "currency_code"` | Moneda |
| warning | `Completeness "account_name" >= 0.95` | Cruce con cuentas |
| warning | `Completeness "cost_center_name" >= 0.95` | Cruce con centros de costo |
| warning | `IsComplete "amount_cop"` | Moneda sin tasa |
| warning | `ColumnValues "currency_code" in ["COP", "USD", "EUR"]` | Dominio de monedas |
| warning | `ColumnLength "transaction_id" = 11` | Formato del ID |

**Regla de oro:** las **críticas bloquean**. Si una falla, **no se escribe nada** del lote en Silver y el job termina con error. Las **warning** solo se registran.

### 6.2 Cómo se evalúan en el código

```python
for table_name in SILVER_TABLES:
    rules = quality_config.get(table_name, {"critical": [], "warning": []})
    result = evaluate_table_quality(glue_context, silver_dfs[table_name], table_name,
                                    rules.get("critical", []), rules.get("warning", []),
                                    quality_results_path)
    gate_results[table_name] = result
    logger.info("DQ RESULTADO | tabla=%s | status=%s | criticas_fallidas=%s | warnings_fallidos=%s", ...)

blocking_tables = [name for name, r in gate_results.items() if r.is_blocking]
if blocking_tables:
    raise RuntimeError("Calidad de datos BLOQUEANTE fallida ...")
```

### 6.3 Practicar: romper una regla a propósito

En el notebook (sección 4) tienes la evaluación completa. Para ver cómo reacciona el job:

1. **Warning:** quita `CC01` de tu copia local del catálogo de centros de costo. Las transacciones de ese centro quedan con `cost_center_name` NULL. La regla `Completeness "cost_center_name" >= 0.95` pasa a `Failed`, pero **el lote se escribe**.
2. **Crítica:** duplica un `transaction_id` en tu copia local del Parquet. `IsUnique "transaction_id"` falla, y el lote **no se escribe**.

Vuelve siempre a los datos originales de Bronze después de practicar. No modifiques Bronze.

---

## 7. Paso a paso — Notebook (probar sin escribir en Silver)

El notebook `notebooks/bronze_to_silver_local_source_finance.ipynb` ejecuta **el mismo código** del job, pero no escribe en Silver. Es el lugar para aprender y depurar.

**7.1 — Subir el código a la sesión.** Desde `beathub-data-pipeline-whorders`, en una terminal donde ya asumiste el rol (sección 2.6):

```powershell
python scripts\build_deps.py --pipeline bronze_to_silver_local_source_finance --env dev
```

Sube `dependencias.zip`, `config.json` y `quality_rules.json` a `s3://beathub-genesis-dev-cicd-artifacts/glue-sessions/bronze_to_silver_local_source_finance/`. **Repítelo cada vez que cambies código.**

Comprueba que el paquete quedó subido, con la misma terminal donde asumiste el rol:

```powershell
aws s3 ls s3://beathub-genesis-dev-cicd-artifacts/glue-sessions/bronze_to_silver_local_source_finance/
# debe aparecer dependencias.zip, config.json y quality_rules.json
```

Si la carpeta sale vacía, la sesión falla con `LAUNCH ERROR ... Error downloading from S3 ... dependencias.zip`. No es un problema del notebook: falta subir el paquete.

> **Sobre el mensaje final de `build_deps.py`:** al terminar dice `[OK] Subido a ... (dependencias.zip, config.json, quality_rules.json y json_muestra/)`. La parte de `json_muestra/` solo aplica a pipelines que tienen muestras JSON (los de CRM). Para este ejercicio no se sube esa carpeta, y no hace falta. Lo que debes verificar son los tres archivos del `aws s3 ls`.

**7.2 — Preparar la terminal y abrir VS Code desde ella.** El kernel de Glue no puede pedir el código MFA, así que el rol se asume **antes** de abrir VS Code, en la misma terminal:

```powershell
. .\scripts\assume_dataengineer.ps1 -SourceProfile $Perfil   # ojo al punto inicial
echo $env:GLUE_ROLE_ARN
# arn:aws:iam::026249143253:role/beathub-data-dev-role-glue-session
code .
```

- `echo $env:GLUE_ROLE_ARN` debe mostrar el ARN del rol de sesión. Si sale vacío, el script no corrió bien: repítelo.
- Si VS Code ya estaba abierto, **ciérralo por completo** (todas las ventanas) antes de ejecutar `code .`. Una ventana abierta antes no hereda las variables.
- No abras VS Code desde el menú Inicio ni desde el icono del escritorio: no hereda la terminal.

**7.2b — Abrir el notebook.** Cierra VS Code y ábrelo desde esa misma terminal con `code .`. Abre el notebook y selecciona el kernel **Glue PySpark** (no "Glue Spark", que es Scala).

**7.3 — Celdas de configuración.** `%region`, `%glue_version 5.1`, `%worker_type G.1X`, `%number_of_workers 2` y `%%configure`. El `%%configure` ya trae el catálogo `glue_catalog` con Iceberg:

```
"datalake-formats": "iceberg",
"--conf": "... spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog
            --conf spark.sql.catalog.glue_catalog.warehouse=s3://beathub-genesis-dev-s3-silver/iceberg-warehouse/ ..."
```

No lo quites. Sin él, Spark no encuentra la tabla.

**7.4 — Sección 1: contrato.** Crea la sesión (30-90 s) y valida `config.json`. Debe mostrar dos entradas (`ENTRADA`) y una salida (`SALIDA`).

**7.5 — Sección 2: lectura.** Ejecuta las celdas y compara:

```
finance : 2 archivos, 180 filas
catalogs: 3 archivos, 13 filas
```

Usa `finance_raw.printSchema()` para ver los tipos, y `finance_raw.show(5)` para mirar datos.

**7.6 — Sección 3: lógica de negocio.** Muestra la tabla enriquecida y el resumen por categoría y centro de costo. Espera `180 filas` y `Esquema OK`.

**7.7 — Sección 4: calidad.** Evalúa las mismas reglas con `EvaluateDataQuality`. Espera todas en `Passed` y `TODAS PASAN`.

**7.8 — Sección 5: cerrar.** Ejecuta `%stop_session`. Cada sesión viva consume DPUs; si no la cierras, se apaga a los 15 minutos de inactividad.

**7.9 — Consulta de práctica.** Con la sesión abierta puedes probar cualquier consulta sobre Silver:

```python
spark.sql("SELECT count(*) AS filas FROM glue_catalog.beathub_genesis_dev_silver_catalogo_db.beathub_genesis_silver_finance_transacciones").show()
```

> **Cuidado:** en la sesión solo tienes lectura. Un `INSERT` o un `DROP` fallará con permisos, y es lo correcto.

---

## 8. Paso a paso — Crear tu pipeline desde la plantilla

En esta sección creas tu propio pipeline a partir de una **plantilla**: una copia completa del job publicado, con los nombres listos para cambiar. Al final tendrás tu carpeta, tu `config.json`, tu `quality_rules.json`, tu `schema.py`, tu `business_logic.py`, tu `etl_glue.py` y tu notebook.

> **Convención de nombres.** Usa tu alias (en esta guía, `ana`) en **todos** los nombres: carpeta, `pipeline`, tabla Silver, notebook y job. Si no lo haces, chocas con el ejercicio ya publicado, que usa los nombres sin alias. El alias debe ir en minúsculas, sin espacios ni guiones bajos extra.

### 8.1 Descargar la plantilla y crear tu rama

Estando en la **raíz** de `beathub-data-pipeline-whorders`:

```powershell
git fetch origin
git switch -c feature/ejercicio-etl-ana origin/development

$alias = "ana"
$tmp = "$env:TEMP\plantilla_$alias"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive -Path "..\ejercicio-etl-dummy\plantilla\plantilla_bronze_to_silver_app_source_area.zip" -DestinationPath $tmp
Get-ChildItem -Recurse -File $tmp | Select-Object FullName
```

Debes ver seis archivos: cinco dentro de `glue\pipelines\bronze_to_silver_local_source_finance\` (`config\config.json`, `config\quality_rules.json`, `schema.py`, `business_logic.py`, `etl_glue.py`) y el notebook dentro de `notebooks\`.

> **La plantilla no trae la solución.** `config.json`, `quality_rules.json`, `schema.py` y `business_logic.py` tienen marcas `TODO` y listas vacías: los completas en las secciones 8.4 a 8.7. `etl_glue.py` ya está listo, y el notebook solo necesita el nombre de tu pipeline. Si la ruta del zip no existe, pide la plantilla a tu instructor: está en `ejercicio-etl-dummy\plantilla\`.

### 8.2 Copiar la plantilla con tu nombre

Sigue en la raíz del repo, con la variable `$alias` ya definida:

```powershell
Copy-Item -Recurse "$tmp\glue\pipelines\bronze_to_silver_local_source_finance" "glue\pipelines\bronze_to_silver_local_source_finance_$alias"
Copy-Item "$tmp\notebooks\bronze_to_silver_local_source_finance.ipynb" "notebooks\bronze_to_silver_local_source_finance_$alias.ipynb"
```

Verifica:

```powershell
Get-ChildItem "glue\pipelines\bronze_to_silver_local_source_finance_$alias" -Recurse -File | Select-Object FullName
```

Ahora tienes dos carpetas: la original (no la toques) y la tuya (`..._ana`). **Solo edita la tuya.**

### 8.3 Cambiar el nombre en todos los archivos

El nombre viejo aparece en varios archivos. Busca cada ocurrencia antes de editar:

```powershell
Select-String -Path "glue\pipelines\bronze_to_silver_local_source_finance_$alias\*.py","glue\pipelines\bronze_to_silver_local_source_finance_$alias\config\*.json","notebooks\bronze_to_silver_local_source_finance_$alias.ipynb" -Pattern "bronze_to_silver_local_source_finance|beathub_genesis_silver_finance_transacciones" -SimpleMatch:$false | Select-Object Path, LineNumber, Line
```

En la plantilla el nombre de la tabla aparece como `TODO_nombre_tabla_silver`. Reemplázalo por `beathub_genesis_silver_finance_transacciones_ana` en todos los archivos donde aparezca. Cambia el resto de referencias según esta tabla:

| Archivo | Qué cambiar | Antes | Después |
|---|---|---|---|
| `config\config.json` | `"pipeline"` | `bronze_to_silver_local_source_finance` | `bronze_to_silver_local_source_finance_ana` |
| `config\config.json` | clave de `outputs` | `beathub_genesis_silver_finance_transacciones` | `beathub_genesis_silver_finance_transacciones_ana` |
| `config\quality_rules.json` | clave de `tables` | `beathub_genesis_silver_finance_transacciones` | `beathub_genesis_silver_finance_transacciones_ana` |
| `schema.py` | clave de `TABLE_DDL` y elemento de `SILVER_TABLES` | `beathub_genesis_silver_finance_transacciones` | `beathub_genesis_silver_finance_transacciones_ana` |
| `business_logic.py` | constante `TABLE` | `beathub_genesis_silver_finance_transacciones` | `beathub_genesis_silver_finance_transacciones_ana` |
| `notebooks\..._ana.ipynb` | variable `PIPELINE` (celda que carga el contrato) | `bronze_to_silver_local_source_finance` | `bronze_to_silver_local_source_finance_ana` |
| `notebooks\..._ana.ipynb` | ruta de `%extra_py_files` (celda de configuración) | `.../glue-sessions/bronze_to_silver_local_source_finance/...` | `.../glue-sessions/bronze_to_silver_local_source_finance_ana/...` |

> **Regla:** la tabla y el pipeline deben llamarse igual en `config.json`, `schema.py`, `business_logic.py` y `quality_rules.json`. Si una clave no coincide, el job no arranca o no aplica las reglas de calidad (y no te avisa).

Repite la búsqueda del `Select-String`. Lo que aún aparezca **sin** `_ana` en tu carpeta debe cambiarse.

### 8.4 `config.json`: qué entra y qué sale

> **Cómo usar los bloques de esta sección:** muestran el contenido final esperado. Úsalos para **comparar** tu archivo al terminar, no para copiarlo sin leer las explicaciones. Completa primero tus `TODO` con tus propios valores.

Este archivo dice **qué** se lee y **qué** se escribe. El **dónde** (bucket y carpeta base) lo pone la plataforma como parámetro del job.

El contenido final esperado es este (los campos `description` son opcionales):

```json
{
  "pipeline": "bronze_to_silver_local_source_finance_ana",
  "description": "Ejercicio ana: transacciones (parquet) x catalogos (csv) -> Silver",
  "inputs": {
    "finance": {
      "layer": "bronze",
      "format": "parquet",
      "prefix": "entity=finance/"
    },
    "catalogs": {
      "layer": "bronze",
      "format": "csv",
      "prefix": "entity=catalogs/",
      "options": {
        "header": "true",
        "delimiter": ",",
        "inferSchema": "false",
        "encoding": "UTF-8"
      }
    }
  },
  "outputs": {
    "beathub_genesis_silver_finance_transacciones_ana": {
      "layer": "silver",
      "format": "iceberg"
    }
  }
}
```

**La ruta que lee cada entrada** se arma así:

```
s3://<bucket de Bronze>  /  <source_prefix>  /  <prefix de la entrada>
s3://beathub-genesis-dev-s3-bronze  /  source=local-source/  /  entity=finance/
```

Por eso, con este `config.json`, el job lee:

| Entrada | Ruta que se lee en S3 | Formato |
|---|---|---|
| `finance` | `s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=finance/` | parquet |
| `catalogs` | `s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=catalogs/` | csv |

**Qué puedes modificar, y qué no:**

| Campo | ¿Lo puedes cambiar? | Efecto |
|---|---|---|
| `prefix` | Sí | Cambia la carpeta de Bronze que se lee. Si cambias `entity=finance/` por otra carpeta, esa carpeta debe existir y tener archivos. |
| `format` | Sí, solo `parquet` o `csv` en las entradas | Cambia el lector de Spark. Otro valor hace fallar la validación. |
| `options` (csv) | Sí | Por ejemplo, `"delimiter": ";"` si tu CSV usa punto y coma. Sin `"header": "true"` la primera línea se toma como dato. |
| `layer` | No: debe ser `bronze` en entradas y `silver` en salidas | El validador rechaza otro valor. |
| nombre de la salida | Solo con alias | Debe ser exactamente igual a la tabla de `SILVER_TABLES` en `schema.py`. |

> **Ojo:** los nombres de las entradas (`finance`, `catalogs`) los usa `etl_glue.py` (sección 8.8). Si los renombras aquí, cámbialos también allá.

### 8.5 `quality_rules.json`: las reglas de calidad

Este archivo define qué se valida sobre el DataFrame ya transformado. La clave de `tables` debe ser igual al nombre de la tabla de salida. El contenido final esperado es este:

```json
{
  "description": "Reglas de calidad del ejercicio ana (DQDL). critical bloquea la escritura; warning solo se registra.",
  "tables": {
    "beathub_genesis_silver_finance_transacciones_ana": {
      "critical": [
        "RowCount > 0",
        "IsComplete \"transaction_id\"",
        "IsUnique \"transaction_id\"",
        "IsComplete \"transaction_ts\"",
        "IsComplete \"process_date\"",
        "IsComplete \"amount\"",
        "ColumnValues \"amount\" > 0",
        "ColumnValues \"transaction_type\" in [\"DEBIT\", \"CREDIT\"]",
        "IsComplete \"currency_code\""
      ],
      "warning": [
        "Completeness \"account_name\" >= 0.95",
        "Completeness \"cost_center_name\" >= 0.95",
        "IsComplete \"amount_cop\"",
        "ColumnValues \"currency_code\" in [\"COP\", \"USD\", \"EUR\"]",
        "ColumnLength \"transaction_id\" = 11"
      ]
    }
  }
}
```

**Cómo funciona:**

- `critical`: si una regla falla, **no se escribe nada** del lote en Silver y el job termina en error.
- `warning`: si falla, el lote se escribe igual y el resultado queda en `run_summary.json`.

**Cómo modificarlo.** Las reglas usan el lenguaje DQDL de AWS Glue Data Quality. Las más usadas:

| Regla | Qué valida | Ejemplo |
|---|---|---|
| `RowCount > 0` | Número de filas | `"RowCount > 0"` |
| `IsComplete "col"` | Sin nulos | `"IsComplete \"amount\""` |
| `IsUnique "col"` | Sin duplicados | `"IsUnique \"transaction_id\""` |
| `ColumnValues "col" > 0` | Valor mayor que cero | `"ColumnValues \"amount\" > 0"` |
| `ColumnValues "col" in [...]` | Valor dentro de una lista | `"ColumnValues \"currency_code\" in [\"COP\", \"USD\"]"` |
| `Completeness "col" >= 0.95` | Porcentaje mínimo de no nulos | `"Completeness \"account_name\" >= 0.95"` |
| `ColumnLength "col" = 11` | Longitud exacta de texto | `"ColumnLength \"transaction_id\" = 11"` |

**Pasos para cambiar una regla:**

1. Decide la severidad: si un fallo debe **bloquear** el lote, va en `critical`; si solo debe avisar, en `warning`.
2. Escribe la regla entre comillas. Dentro de una regla, las comillas de la columna van escapadas: `\"transaction_id\"`.
3. Pon una coma entre reglas, y **ninguna coma después de la última**.
4. Valida el JSON antes de subirlo:
   ```powershell
   python -m json.tool "glue\pipelines\bronze_to_silver_local_source_finance_ana\config\quality_rules.json" > $null; if ($?) { "JSON valido" }
   ```
5. Pruébala en el notebook, sección 4 (paso 8.9). Con los datos del ejercicio, **todas** deben salir `Passed`. Si una regla que debe pasar falla, revisa la columna o el valor antes de cambiar la regla.

> **Práctica:** añade `"IsComplete \"description\""` como `warning`, ejecuta el notebook y verifica que aparece como `Passed`. Después quítala.

### 8.6 `schema.py`: el contrato de columnas

`schema.py` define cuatro cosas. Cada una se usa en un momento distinto:

| Constante | Cuándo se usa | Qué debes saber |
|---|---|---|
| `FINANCE_SOURCE_SCHEMA` | Antes de transformar | Lista las columnas que **debe traer** el Parquet. Si falta una, el job se detiene. |
| `CATALOG_SOURCE_COLUMNS` | Antes de transformar | Lista las columnas del CSV. Mismo control. |
| `TABLE_DDL` | Solo al crear la tabla (bootstrap) | `columns_ddl` define la tabla Silver; `match_columns` es la clave del MERGE. |
| `SILVER_TABLES` | Al validar el contrato | Debe ser **exactamente** la lista de `outputs` de `config.json`. |

**Ejemplo de cambio: añadir la columna `amount_abs`** (valor absoluto del importe firmado). Son tres cambios que deben coincidir en orden:

1. En `schema.py`, dentro de `columns_ddl`, después de `amount_cop DECIMAL(22,2),`:

   ```sql
   amount_abs DECIMAL(18,2),
   ```

2. En `schema.py`, la lista `BUSINESS_COLUMNS` de `business_logic.py` debe llevar la misma columna **en la misma posición** (después de `"amount_cop"`).
3. En `business_logic.py`, calcula la columna (sección 8.7).

> **Ojo con el orden:** el notebook compara las columnas en **el mismo orden** que el DDL. Si no coinciden, verás `DIFERENCIAS` en la sección 3.

> **Ojo con la tabla existente:** el bootstrap crea la tabla **solo si no existe**. Si cambias las columnas de una tabla que ya existe, no se actualiza. Por eso tu tabla lleva el alias: se crea nueva con tu esquema. Si cambias el esquema después de publicar, pide a la plataforma una migración.

### 8.7 `business_logic.py`: las transformaciones

Este archivo es el que transforma los datos. La plantilla trae estas funciones con `NotImplementedError` (cada una se implementa con el código de la sección 5 correspondiente): `_code` (5.1), `prepare_finance` (5.1), `prepare_catalogs` (5.2), `_catalog` (5.3) y `build_transacciones` (5.3 a 5.6). La función principal es `build_transacciones(finance, catalogs)`, y sus pasos son estos:

1. `prepare_finance`: limpia los códigos (sin espacios, en mayúsculas).
2. `prepare_catalogs`: deja solo catálogos activos y un registro por código.
3. El cruce (`LEFT JOIN`) con cuentas, centros de costo y monedas.
4. El signo contable (`amount_signed`).
5. La conversión a pesos (`amount_cop`).
6. La partición (`process_date`) y el hash (`row_hash`).

**Ejemplo de cambio: calcular `amount_abs`.** Después de la línea de `amount_cop` dentro de `build_transacciones`:

```python
df = df.withColumn("amount_abs", F.abs(F.col("amount_signed")).cast("decimal(18,2)"))
```

Y en la lista `BUSINESS_COLUMNS`, después de `"amount_cop"`:

```python
BUSINESS_COLUMNS = [
    "transaction_id", "transaction_ts", "transaction_type", "account_code",
    "account_name", "account_category", "cost_center_code", "cost_center_name",
    "currency_code", "currency_name", "rate_to_cop", "amount", "amount_signed",
    "amount_cop", "amount_abs", "description",
]
```

Así `amount_abs` entra en la salida. Recuerda que también debes añadirla al `columns_ddl` de `schema.py` (sección 8.6).

**Reglas de estilo del archivo:**

- Usa solo funciones de Spark SQL (`F.col`, `F.when`, `F.round`, etc.). **No uses UDFs**: son lentas y el proyecto no las permite.
- Si usas un join, usa `LEFT JOIN` cuando una fila no deba perderse, y `F.broadcast` solo para catálogos pequeños.
- Si cambias un tipo, usa `cast` explícito (por ejemplo `.cast("decimal(18,2)")`).

### 8.8 `etl_glue.py`: el entrypoint

Este archivo orquesta el job: lee la configuración, lee las entradas, llama a `business_logic`, valida la calidad, escribe y verifica. **Casi nunca necesitas cambiarlo.** Lo que sí debes revisar:

| Qué | Dónde | Cuándo cambiarlo |
|---|---|---|
| Nombres de entrada | `FINANCE_INPUT = "finance"` y `CATALOGS_INPUT = "catalogs"` | Solo si renombraste `finance` o `catalogs` en `config.json`. Deben coincidir exactamente. |
| Argumentos del job | `REQUIRED_ARGS` y `OPTIONAL_ARGS_DEFAULTS` | No los cambies: los inyecta la plataforma. |
| Lógica de orquestación | `main()` | No la cambies para un ejercicio normal. |

> **Ejemplo:** si en `config.json` cambias la entrada `finance` por `transacciones`, en `etl_glue.py` debes cambiar `FINANCE_INPUT = "transacciones"`. Si no lo haces, el job no encuentra la entrada.

### 8.9 Notebook: cómo probar tu pipeline

El notebook `notebooks\bronze_to_silver_local_source_finance_ana.ipynb` ejecuta **el mismo código** del job, pero no escribe en Silver. Úsalo cada vez que cambies algo.

**Antes de abrirlo, sube tu código a la sesión** (con el rol asumido, en la raíz del repo):

```powershell
python scripts\build_deps.py --pipeline bronze_to_silver_local_source_finance_ana --env dev
aws s3 ls s3://beathub-genesis-dev-cicd-artifacts/glue-sessions/bronze_to_silver_local_source_finance_ana/ --profile $Perfil
```

Debes ver `dependencias.zip`, `config.json` y `quality_rules.json`. Luego sigue la sección 7.2 (la terminal con el rol asumido y `code .`) y ejecuta las celdas en orden con el kernel **Glue PySpark**:

| Celda | Qué hace | Qué debes ver |
|---|---|---|
| Configuración (`%region`, `%glue_version`, `%%configure`) | Sin error. No cambies `%%configure`. |
| Carga del contrato (`PIPELINE`, `config.json`) | `ENTRADA finance`, `ENTRADA catalogs`, `SALIDA` |
| Lectura de Bronze (sección 2) | `finance : 2 archivos, 180 filas` y `catalogs: 3 archivos, 13 filas` |
| Lógica de negocio y comparación de esquema (sección 3) | `180 filas` y `Esquema OK` |
| Muestra de la tabla enriquecida (sección 3) | Columnas con nombres de cuentas y centros de costo |
| Calidad con tu `quality_rules.json` (sección 4) | Todas `Passed` y `TODAS PASAN` |
| Cierre (`%stop_session`, sección 5) | Sesión detenida |

**Cuando cambies código**, repite el ciclo: edita el archivo, ejecuta `build_deps.py` otra vez y **reinicia el kernel** (menú del notebook → *Restart*) para que cargue el zip nuevo. Si no reinicias, verás el código anterior.

**Validación local** (no necesita AWS):

```powershell
python scripts\pipeline_config.py bronze_to_silver_local_source_finance_ana
python -m pytest glue\framework\tests -m "not spark" -q
```

Ambos deben terminar sin errores antes de abrir el PR (paso 9.1).

### 8.10 Lista de archivos que debes tener al terminar

- [ ] `glue\pipelines\bronze_to_silver_local_source_finance_ana\config\config.json` con `pipeline` y la salida con `_ana`.
- [ ] `config\quality_rules.json` con la clave `_ana` y JSON válido.
- [ ] `schema.py` con `TABLE_DDL`, `SILVER_TABLES` y `match_columns` con `_ana`.
- [ ] `business_logic.py` con `TABLE` en `_ana` y tus cambios de columnas.
- [ ] `etl_glue.py` sin cambios, o con los nombres de entrada ajustados.
- [ ] `notebooks\bronze_to_silver_local_source_finance_ana.ipynb` con `PIPELINE` en `_ana` y la ruta de `%extra_py_files` ajustada.
- [ ] Notebook: secciones 1 a 4 sin errores.

---

## 9. Paso a paso — Publicar el pipeline (PR al repo de Glue)

**9.1 — Validar el contrato en local** (no necesita AWS):

```powershell
python scripts\pipeline_config.py bronze_to_silver_local_source_finance_ana
python -m pytest glue\framework\tests -m "not spark" -q
```

Ambos deben terminar sin errores.

**9.2 — Commit y push:**

```powershell
git add glue\pipelines\bronze_to_silver_local_source_finance_ana notebooks\bronze_to_silver_local_source_finance_ana.ipynb
git commit -m "[Feature]: Pipeline de formación local-source finance (ana)"
git push -u origin feature/ejercicio-etl-ana
```

**9.3 — Abrir el PR en GitHub.** Al terminar el `git push`, la terminal muestra un enlace `https://github.com/Tuboleta/beathub-data-pipeline-whorders/pull/new/feature/ejercicio-etl-ana`. Ábrelo, elige la base **`development`**, pon título y descripción, y crea el PR.

**9.4 — Esperar el CI.** En la pestaña **Checks** verás `ci/lint`, `ci/tests`, `ci/security-scan`, `ci/dependency-audit` y `ci/secret-scan`. Todos deben pasar.

**9.5 — Merge.** El administrador de plataforma aprueba y mergea. Al mergear, el pipeline **`beathub-genesis-dev-glue-bronze-to-silver-pipeline`** publica tu carpeta en `s3://beathub-genesis-dev-cicd-artifacts/glue-scripts/bronze_to_silver_local_source_finance_ana/` y lanza el **bootstrap**, que crea la tabla Silver si no existe.

**9.6 — Verificar la publicación y la tabla:**

```powershell
aws s3 ls s3://beathub-genesis-dev-cicd-artifacts/glue-scripts/bronze_to_silver_local_source_finance_ana/ --profile $Perfil
aws glue get-table --profile $Perfil --region us-east-1 --database-name beathub_genesis_dev_silver_catalogo_db --name beathub_genesis_silver_finance_transacciones_ana --query "Table.Name" --output text
```

En la consola de **CodePipeline**, `beathub-genesis-dev-glue-bronze-to-silver-pipeline` muestra cada etapa. En la de **Glue → Jobs**, el bootstrap aparece con sus ejecuciones.

---

## 10. Paso a paso — Catálogo: crear el job (PR a infra)

Un job existe en AWS porque está en `catalog/orquestacion.yaml`. Añadir el tuyo es una entrada:

```powershell
git fetch origin
git switch -c feature/job-ejercicio-ana origin/development
```

Edita `catalog/orquestacion.yaml` y añade, en la sección `jobs`, después de los de CRM:

```yaml
  bronze_to_silver_local_source_finance_ana:
    source: local-source
    environments: [dev]
```

Reglas del catálogo, validadas por CI:

- El nombre sigue `<origen>_to_<destino>_<fuente>_<dominio>`. Debe coincidir con la carpeta del pipeline.
- `source` solo admite minúsculas y guiones medios: `local-source`, no `local_source`.
- `environments: [dev]` limita el job a dev.
- Sin entrada en `flows`, el job solo se ejecuta a mano.

```powershell
git add catalog\orquestacion.yaml
git commit -m "feature: Add new job local source finance ana"
git push -u origin feature/job-ejercicio-ana
```

Abre el PR desde el enlace que muestra el `git push`, con base `development`. El CI valida el catálogo en `ci/terraform`. Al mergear, el pipeline de Terraform de dev crea el job `beathub-genesis-dev-glue-bronze-silver-local-source-finance-ana`.

Confírmalo:

```powershell
aws glue get-job --profile $Perfil --region us-east-1 --job-name beathub-genesis-dev-glue-bronze-silver-local-source-finance-ana --query "Job.Name" --output text
```

---

## 11. Paso a paso — Permisos: Lake Formation y sesión (PR a infra)

Lake Formation es estricto: IAM no basta. Hay que dar permisos a **dos** roles sobre tu tabla:

- **El rol del Data Engineer**, para consultar desde Athena.
- **El rol de sesión de Glue**, para leer desde el notebook y para que el job lea la tabla.

Crea `env/dev/datalake/13-lf-ana.tf` (mismo contenido que el ejercicio, cambiando el nombre de la tabla):

```hcl
# ##############################################################################
# Permisos Lake Formation del ejercicio (ana) sobre la tabla Silver.
# La tabla la crea el bootstrap; si no existe, este apply falla.
# ##############################################################################

locals {
  dataengineer_role_arn = try(data.terraform_remote_state.security.outputs.dataengineer_role_arn, null)
  glue_session_role_arn = try(data.terraform_remote_state.security.outputs.glue_session_role_arn, null)
  ejercicio_table_name  = "beathub_genesis_silver_finance_transacciones_ana"
}

resource "aws_lakeformation_permissions" "ana_de_database" {
  count       = local.dataengineer_role_arn != null ? 1 : 0
  principal   = local.dataengineer_role_arn
  permissions = ["DESCRIBE"]
  database {
    name = aws_glue_catalog_database.silver.name
  }
}

resource "aws_lakeformation_permissions" "ana_de_table" {
  count       = local.dataengineer_role_arn != null ? 1 : 0
  principal   = local.dataengineer_role_arn
  permissions = ["SELECT", "DESCRIBE"]
  table {
    database_name = aws_glue_catalog_database.silver.name
    name          = local.ejercicio_table_name
  }
}

resource "aws_lakeformation_permissions" "ana_session_database" {
  count       = local.glue_session_role_arn != null ? 1 : 0
  principal   = local.glue_session_role_arn
  permissions = ["DESCRIBE"]
  database {
    name = aws_glue_catalog_database.silver.name
  }
}

resource "aws_lakeformation_permissions" "ana_session_table" {
  count       = local.glue_session_role_arn != null ? 1 : 0
  principal   = local.glue_session_role_arn
  permissions = ["SELECT", "DESCRIBE"]
  table {
    database_name = aws_glue_catalog_database.silver.name
    name          = local.ejercicio_table_name
  }
}
```

**Orden:** este PR va **después** de que exista la tabla (paso 9.6). Si lo mergeas antes, el `apply` falla.

Haz el PR como en el paso 10 (rama `feature/lf-ejercicio-ana`, base `development`). Abre el PR y espera el CI. El administrador aprueba y mergea.

> **Permiso de S3 del rol de sesión.** El rol de sesión también necesita leer los archivos Iceberg de tu tabla en S3. Ese permiso está en la política de sesiones (`env/dev/security/09-dataengineer-sesiones.tf`) y lo gestiona el administrador. Si el notebook falla con `s3:GetObject ... iceberg-warehouse/...`, pídele que lo aplique para tu tabla.

---

## 12. Paso a paso — Ejecutar el job en Glue

Cuando el PR del catálogo y el de permisos están mergeados, lanza tu job. Tu grupo puede lanzar y parar cualquier job `beathub-genesis-dev-glue-*`, así que tu copia se ejecuta sin problema. Para **modificar** un job, el cambio va por PR, no por la consola:

```powershell
$job = "beathub-genesis-dev-glue-bronze-silver-local-source-finance-ana"
$run = aws glue start-job-run --profile $Perfil --region us-east-1 --job-name $job --query JobRunId --output text
Write-Host "JobRunId = $run"
```

Consulta el estado cada 30 segundos:

```powershell
aws glue get-job-run --profile $Perfil --region us-east-1 --job-name $job --run-id $run --query JobRun.JobRunState --output text
```

Estados posibles: `STARTING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMEOUT`. Espera `SUCCEEDED` (unos 2 minutos).

**También desde la consola:** AWS Glue → *ETL jobs* → tu job → pestaña *Runs* → selecciona la ejecución. Ahí ves la duración, los workers y los enlaces a los logs.

---

## 13. Paso a paso — Verificar que todo quedó bien

Una ejecución `SUCCEEDED` no basta. Verifica cuatro cosas: el log, el resumen de calidad, la tabla y la idempotencia.

### 13.1 CloudWatch: el log de la ejecución

Los logs del job van al grupo `/aws-glue/jobs/output` (salida normal) y `/aws-glue/jobs/error` (errores). El nombre del stream es el `JobRunId`.

**En la consola:** CloudWatch → *Log groups* → `/aws-glue/jobs/output` → busca el stream que empieza con tu `JobRunId`.

**Desde PowerShell:**

```powershell
aws logs filter-log-events --profile $Perfil --region us-east-1 `
  --log-group-name /aws-glue/jobs/output --log-stream-names $run `
  --query "events[].message" --output text | Select-String -Pattern "ENTRADA|DQ|MERGE|VERIFICACION|FINALIZADO|ERROR"
```

**Qué debes ver, en este orden:**

```
ENTRADA finance | parquet | s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=finance/
ENTRADA catalogs | csv | s3://beathub-genesis-dev-s3-bronze/source=local-source/entity=catalogs/
DQ | tabla=beathub_genesis_silver_finance_transacciones_ana | filas=180 | reglas_criticas=9 | reglas_warning=5
DQ RESULTADO | tabla=... | status=PASSED | criticas_fallidas=0 | warnings_fallidos=0
MERGE COMPLETADO | ... | filas_en_batch=180
VERIFICACION OK | ... | filas_del_lote_presentes=180
PIPELINE FINALIZADO CORRECTAMENTE | execution_id=<uuid>
```

Si ves `ERROR`, `Traceback` o `PIPELINE ABORTADO`, el mensaje explica la causa. Revisa también `/aws-glue/jobs/error`.

Para buscar en varias ejecuciones a la vez, CloudWatch Logs Insights funciona bien con esta consulta sobre `/aws-glue/jobs/output`:

```
fields @timestamp, @message
| filter @message like /PIPELINE|DQ RESULTADO|MERGE|VERIFICACION|ERROR/
| sort @timestamp asc
```

### 13.2 Resumen de calidad y de ejecución (S3)

Cada ejecución escribe `run_summary.json`. El `execution_id` está en la última línea del log:

```powershell
aws s3 cp "s3://beathub-genesis-dev-cicd-artifacts/quality-results/environment=dev/execution_id=<execution_id>/run_summary.json" - --profile $Perfil
```

Busca estos campos:

- `"pipeline_status": "SUCCESS"`: la ejecución terminó bien.
- `"silver_written": true`: se escribió en Silver.
- `"records_read": 180`: filas leídas.
- `"quality_gates"`: una entrada por tabla, con las reglas que pasaron y las que fallaron.

### 13.3 La tabla Silver en Athena

Lake Formation es estricto: tu usuario no ve la tabla. Usa el **rol** del Data Engineer:

1. Consola de AWS → menú de la cuenta → **Switch role**: cuenta `026249143253`, rol `beathub-data-dev-role-dataengineer`.
2. **Athena** → workgroup `beathub-genesis-dev-wg` → catálogo `AwsDataCatalog` → base `beathub_genesis_dev_silver_catalogo_db`.

```sql
-- 1. ¿Cuántas filas y cuántos IDs distintos?
SELECT count(*) AS filas, count(DISTINCT transaction_id) AS ids
FROM beathub_genesis_silver_finance_transacciones_ana;

-- 2. Muestra enriquecida
SELECT transaction_id, transaction_type, account_name, cost_center_name,
       currency_code, amount, amount_signed, amount_cop, process_date, source
FROM beathub_genesis_silver_finance_transacciones_ana
ORDER BY transaction_id
LIMIT 20;

-- 3. Resumen de negocio
SELECT account_category, cost_center_name, count(*) AS transacciones, sum(amount_cop) AS total_cop
FROM beathub_genesis_silver_finance_transacciones_ana
GROUP BY 1, 2 ORDER BY 1, 2;

-- 4. Historial Iceberg: cada ejecución que escribió es un snapshot
SELECT committed_at, snapshot_id, operation, summary
FROM "beathub_genesis_silver_finance_transacciones_ana$snapshots";
```

**Resultado esperado:** 180 filas, 180 IDs distintos, `source = local-source`, y ninguna cuenta, centro de costo ni moneda en NULL.

### 13.4 Idempotencia: volver a ejecutar

Lanza el job otra vez (paso 12). Debe terminar `SUCCEEDED`, el log debe mostrar `MERGE COMPLETADO` sin filas nuevas, y el `count(*)` sigue en 180. Si el conteo sube, algo falla en la clave `transaction_id + row_hash`.

### 13.5 Tu checklist final

- [ ] El log muestra `PIPELINE FINALIZADO CORRECTAMENTE`.
- [ ] `run_summary.json` tiene `pipeline_status: SUCCESS`.
- [ ] Athena devuelve 180 filas y 180 IDs distintos.
- [ ] La segunda ejecución no duplica filas.
- [ ] El notebook con el rol de sesión lee la tabla (paso 7.9).

---

## 14. Problemas frecuentes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `explicit deny ... aws:MultiFactorAuthPresent` | Comando sin MFA | Asume el rol con `assume_dataengineer.ps1` (paso 2) |
| Todo aparece como `Acceso denegado` al entrar a la consola | La sesión no tiene MFA | Registra el MFA (2.2) y vuelve a entrar con el código (2.3) |
| `Acceso denegado a iam:ListUsers` | Normal: no puedes listar usuarios | Ve a tu usuario directo o a *Mis credenciales de seguridad* (2.4) |
| No aparece la opción de crear la clave CLI | La sesión no tiene MFA | Haz 2.2 y 2.3 y luego 2.4 |
| `The config profile (<tu_perfil>) could not be found` | El perfil no se creó | Ejecuta `$Perfil = "mi-perfil-dev"   # cambia por el nombre que elegiste
aws configure --profile $Perfil` (2.5) |
| `AccessDenied ... start-job-run` | Estás usando un perfil o cuenta distinta | Revisa `aws sts get-caller-identity --profile $Perfil` (2.5) |
| `explicit deny` al listar Bronze o al leer S3 con tu clave de acceso | Falta MFA en la sesión: la política lo bloquea | Usa la sesión con MFA del paso 3.7 (opción 2) |
| `AccessDenied ... glue:StartJobRun` sobre un job de bootstrap | El job de bootstrap solo es de la plataforma | No lo lances; usa tu job de ejecución |
| `MultiFactorAuthentication failed` al asumir el rol | Código ya usado o vencido | Usa un código nuevo |
| `ExpiredToken` | Pasaron 60 minutos | Vuelve a asumir el rol |
| `Glue Role ARN not provided` al ejecutar la primera celda | `GLUE_ROLE_ARN` vacía: VS Code no se abrió desde la terminal donde corrió el script | Ejecuta el script en la terminal (paso 7.2), verifica `echo $env:GLUE_ROLE_ARN` y abre VS Code con `code .` |
| `AccessDenied ... glue:CreateSession` con tu usuario | VS Code no heredó el rol | Cierra VS Code y ábrelo con `code .` desde la terminal del paso 7 |
| `LAUNCH ERROR ... Error downloading from S3 ... dependencias.zip` (la sesión queda en `FAILED`) | No corriste `build_deps.py`, o la carpeta de S3 está vacía | Paso 7.1: ejecuta `build_deps.py`, verifica con `aws s3 ls`, ejecuta `%stop_session` y vuelve a crear la sesión |
| `ModuleNotFoundError: business_logic` | Zip viejo | Vuelve a correr `build_deps.py` y reinicia el kernel |
| `TABLE_OR_VIEW_NOT_FOUND` en el notebook | Consulta sin `glue_catalog.` o sin permiso LF de sesión | Usa `glue_catalog.<base>.<tabla>`. Si persiste, paso 11 |
| `s3:GetObject ... iceberg-warehouse/...` | Falta el permiso S3 del rol de sesión | Pide al administrador el permiso de sesión (paso 11) |
| `La tabla Iceberg ... no existe` en el job | El bootstrap no corrió | Revisa CodePipeline (paso 9.6) |
| `Calidad de datos BLOQUEANTE fallida` | Falló una regla crítica | Abre `run_summary.json` y mira `quality_gates` |
| `PATH_NOT_FOUND` o `SIN DATOS` | No hay archivos en el prefijo | Revisa Bronze (paso 3.3) |
| Athena: `Insufficient Lake Formation permission(s)` | Consultas con tu usuario | *Switch role* (paso 13.3) |
| `terraform fmt -check` falla en el CI | Formato del HCL | `terraform fmt <archivo>` y sube el cambio |
| Spark local: `loopback connection` | Spark en Windows sin `winutils` | Usa el notebook de Glue (paso 7) |

---

## 15. Limpieza (solo administrador, al terminar la formación)

Los alumnos no hacen esto. Un administrador de plataforma, con aprobación explícita:

1. `DROP TABLE beathub_genesis_dev_silver_catalogo_db.beathub_genesis_silver_finance_transacciones_ana PURGE` (borra los datos).
2. PR que quita la entrada del job de `catalog/orquestacion.yaml` y el fichero `13-lf-ana.tf`.
3. Bronze: no se borra; los datos de entrada son compartidos.
4. Usuarios de prueba: quitar del grupo, desactivar MFA y access keys, y borrar el usuario.

---

## Anexo — Validación del ejercicio

- [ ] Prerrequisitos y `aws sts get-caller-identity` correctos
- [ ] Insumos: 5 archivos, 180 transacciones y 13 filas de catálogo
- [ ] Notebook: secciones 1 a 4 sin errores
- [ ] PR del pipeline mergeado y tabla creada por el bootstrap
- [ ] PR del catálogo mergeado y job creado
- [ ] PR de permisos LF mergeado
- [ ] Job `SUCCEEDED` con `PIPELINE FINALIZADO CORRECTAMENTE` en CloudWatch
- [ ] Athena con el rol: 180 filas
- [ ] Segunda ejecución sin duplicados
- [ ] Notebook con el rol de sesión: `count(*)` = 180
