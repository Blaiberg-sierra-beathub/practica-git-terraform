#!/usr/bin/env python3
"""Valida los nombres de los recursos AWS de Terraform contra el estándar de
nomenclatura del proyecto (F3, "Estándar de Nomenclatura de Recursos en AWS v1.0").

Reglas F3:
  - General: kebab-case <org>-<proyecto>-<ambiente>-<servicio>-<descripción>,
    ^[a-z][a-z0-9]*(-[a-z0-9]+){2,10}$, máximo 60 caracteres.
  - Buckets S3:
    ^[a-z]{2,10}-[a-z0-9]{2,15}-(dev|pre|pro)(-s3-(bronze|silver|gold))?(-[a-z0-9-]{1,20})?$
  - Glue Data Catalog y Athena no admiten guiones medios: bases de datos y tablas
    en snake_case (^[a-z][a-z0-9]*(_[a-z0-9]+){2,6}$ y ^[a-z][a-z0-9]*(_[a-z0-9]+)*$).
  - Rutas (log groups de CloudWatch, parámetros SSM): en minúsculas. Si la ruta
    lleva el nombre de otro recurso tras un prefijo fijo de AWS (/aws/lambda/,
    alias/...), ese nombre se valida con el patrón general.

Con --org y --env (p. ej. beathub y dev), los nombres generales y los buckets
deben llevar además esa organización y ese ambiente: <org>-<proyecto>-<env>-...
El proyecto no se fija porque los grupos IAM de equipo usan el área
(beathub-data-dev-dataengineer).

Excepciones justificadas por límites del servicio (F3 §2.2) en EXCEPTIONS;
recursos sin nombre propio o con nombre fijado por AWS, en SKIP_TYPES y
FIXED_NAMES.

Dos modos:
  1. Por defecto: escanea los .tf y valida solo los nombres LITERALES; los que se
     construyen con variables o locals se listan como omitidos. Requiere
     python-hcl2.
  2. --plan-json <archivo>: valida los nombres RESUELTOS del JSON de
     `terraform show -json tfplan`. Es el modo que usa el pipeline de Terraform
     (buildspec-terraform-plan.yml) antes del apply.

Código de salida: 0 si todo cumple, 1 si algún nombre no cumple, 2 si no se
puede leer la entrada.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_LENGTH = 60

GENERAL_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+){2,10}$")
S3_BUCKET_PATTERN = re.compile(
    r"^[a-z]{2,10}-[a-z0-9]{2,15}-(dev|pre|pro)(-s3-(bronze|silver|gold))?(-[a-z0-9-]{1,20})?$"
)
GLUE_DATABASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+){2,6}$")
GLUE_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
PATH_PATTERN = re.compile(r"^/?[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9._-]*)*$")

S3_RESOURCE_TYPES = {"aws_s3_bucket"}
GLUE_DATABASE_RESOURCE_TYPES = {"aws_glue_catalog_database"}
# Tipos cuyo nombre es el de una tabla del catálogo (atributo table_name).
GLUE_TABLE_RESOURCE_TYPES = {"aws_glue_catalog_table", "aws_glue_catalog_table_optimizer"}
PATH_RESOURCE_TYPES = {"aws_cloudwatch_log_group", "aws_ssm_parameter"}

# Prefijos fijos de AWS: lo que sigue es el nombre de otro recurso del proyecto.
AWS_PATH_PREFIXES = (
    "alias/",
    "/aws/lambda/",
    "/aws/codebuild/",
    "/aws/apigateway/",
    "/aws/cloudtrail/",
    "/aws/vendedlogs/states/",
)

# Recursos sin nombre propio (el atributo "name" o "function_name" apunta a
# otro recurso) o cuya identidad no se rige por F3.
SKIP_TYPES = {
    "aws_lambda_alias",                # alias de versión ("live"), no un recurso con nombre
    "aws_lambda_event_source_mapping", # function_name es el ARN de la Lambda destino
    "aws_lambda_permission",
    "aws_apigatewayv2_stage",          # "$default" lo fija API Gateway
    "aws_default_security_group",      # "default" lo fija la VPC
    "aws_iam_user",                    # usuarios de personas: estándar de identidades
}

# Nombres fijados por AWS que se aceptan tal cual.
FIXED_NAMES = {
    "/aws-glue/jobs/output",
    "/aws-glue/jobs/error",
    "/aws-glue/jobs/logs-v2",
}

# Excepciones justificadas por límites del servicio (F3 §2.2): (patrón, motivo).
EXCEPTIONS = [
    (
        re.compile(r"^CodeDeployHook_[a-z0-9-]+$"),
        "la política gestionada AWSCodeDeployRoleForLambda solo permite invocar "
        "hooks de CodeDeploy cuyo nombre empieza por CodeDeployHook_",
    ),
    (
        re.compile(r"^dynamodb$"),
        "nombre del catálogo de Athena que usan las consultas y Power BI "
        "(\"dynamodb\".\"default\".<tabla>); cambiarlo rompe los consumidores",
    ),
]

NAME_ATTRIBUTE_CANDIDATES = [
    "name",
    "name_prefix",
    "function_name",
    "role_name",
    "cluster_name",
    "queue_name",
    "topic_name",
    "table_name",
    "db_name",
    "identifier",
    "dashboard_name",
    "alarm_name",
    "trail_name",
    "domain_name",
    "user_profile_name",
]

# Recursos cuyo nombre propio no está en "name" (ahí va otro recurso).
NAME_ATTRIBUTE_BY_TYPE = {
    "aws_ssm_association": "association_name",  # "name" es el documento SSM (p. ej. AWS-RunPowerShellScript)
}

EXCLUDE_DIR_NAMES = {".terraform", ".git", ".build"}


def _exception_for(name: str) -> str | None:
    for pattern, reason in EXCEPTIONS:
        if pattern.match(name):
            return reason
    return None


def _check_scope(name: str, scope: tuple[str, str] | None) -> str | None:
    """Comprueba <org>-<proyecto>-<env>- si se dieron --org y --env."""
    if not scope:
        return None
    org, env = scope
    parts = name.split("-")
    if len(parts) < 3 or parts[0] != org or parts[2] != env:
        return f"no sigue <org>-<proyecto>-<ambiente> con org '{org}' y ambiente '{env}'"
    return None


def _check_general(name: str, scope: tuple[str, str] | None) -> str | None:
    """Devuelve el motivo del fallo o None si el nombre cumple."""
    if not GENERAL_PATTERN.match(name):
        return f"no cumple el patrón general {GENERAL_PATTERN.pattern}"
    if len(name) > MAX_LENGTH:
        return f"tiene {len(name)} caracteres (máximo {MAX_LENGTH})"
    return _check_scope(name, scope)


def _check(resource_type: str, get_value, scope: tuple[str, str] | None):
    """Devuelve (nombre, estado, detalle) con estado OK / EXCEPCION / FALLO / OMITIDO."""
    if resource_type in SKIP_TYPES:
        return None, "OMITIDO", "tipo sin nombre propio o fuera de F3"

    if resource_type in S3_RESOURCE_TYPES:
        name = get_value("bucket")
        if name is None:
            return None, "OMITIDO", "sin nombre resuelto"
        if not S3_BUCKET_PATTERN.match(name):
            return name, "FALLO", f"no cumple el patrón S3 {S3_BUCKET_PATTERN.pattern}"
        problem = _check_scope(name, scope)
        if problem:
            return name, "FALLO", problem
        return name, "OK", "S3"

    if resource_type in GLUE_DATABASE_RESOURCE_TYPES:
        name = get_value("name")
        if name is None:
            return None, "OMITIDO", "sin nombre resuelto"
        if GLUE_DATABASE_PATTERN.match(name):
            return name, "OK", "Glue database"
        return name, "FALLO", f"no cumple el patrón Glue database {GLUE_DATABASE_PATTERN.pattern}"

    if resource_type in GLUE_TABLE_RESOURCE_TYPES:
        name = get_value("name") if resource_type == "aws_glue_catalog_table" else get_value("table_name")
        if name is None:
            return None, "OMITIDO", "sin nombre resuelto"
        if GLUE_TABLE_PATTERN.match(name):
            return name, "OK", "Glue table"
        return name, "FALLO", f"no cumple el patrón Glue table {GLUE_TABLE_PATTERN.pattern}"

    if resource_type in NAME_ATTRIBUTE_BY_TYPE:
        name = get_value(NAME_ATTRIBUTE_BY_TYPE[resource_type])
        if name is None:
            return None, "OMITIDO", "sin nombre resuelto"
        problem = _check_general(name, scope)
        return name, ("FALLO" if problem else "OK"), problem or "nombre propio"

    # Con name_prefix, AWS añade un sufijo aleatorio al nombre: se valida el prefijo.
    name = (get_value("name_prefix") or "").rstrip("-") or None
    for candidate in NAME_ATTRIBUTE_CANDIDATES:
        if name is not None:
            break
        name = get_value(candidate)
    if name is None:
        return None, "OMITIDO", "sin atributo de nombre resuelto"

    if name in FIXED_NAMES:
        return name, "OK", "nombre fijado por AWS"

    if resource_type in PATH_RESOURCE_TYPES or name.startswith("alias/"):
        for aws_prefix in AWS_PATH_PREFIXES:
            if name.startswith(aws_prefix):
                inner = name[len(aws_prefix):]
                reason = _exception_for(inner)
                if reason:
                    return name, "EXCEPCION", reason
                problem = _check_general(inner, scope)
                return (name, "FALLO", f"'{inner}' {problem}") if problem else (name, "OK", "ruta AWS")
        if PATH_PATTERN.match(name):
            return name, "OK", "ruta"
        return name, "FALLO", f"no cumple el patrón de ruta {PATH_PATTERN.pattern}"

    reason = _exception_for(name)
    if reason:
        return name, "EXCEPCION", reason
    problem = _check_general(name, scope)
    return (name, "FALLO", problem) if problem else (name, "OK", "general")


def _report(results: list[tuple[str, str | None, str, str]]) -> int:
    counts = {s: sum(1 for r in results if r[2] == s) for s in ("OK", "EXCEPCION", "FALLO", "OMITIDO")}
    print(
        f"Recursos: {counts['OK']} OK, {counts['EXCEPCION']} excepciones, "
        f"{counts['FALLO']} fallidos, {counts['OMITIDO']} omitidos\n"
    )
    for title, status in (("Excepciones justificadas (F3 §2.2)", "EXCEPCION"), ("FALLIDOS", "FALLO")):
        rows = [r for r in results if r[2] == status]
        if rows:
            print(f"{title}:")
            for address, name, _, detail in rows:
                print(f"  - {address} -> '{name}': {detail}")
            print()

    if counts["FALLO"]:
        print(f"{counts['FALLO']} recurso(s) no cumplen el estándar de nomenclatura F3.")
        return 1
    print("Todos los nombres resueltos cumplen el estándar de nomenclatura F3.")
    return 0


# --- Modo 1: .tf (solo nombres literales) ---


def validate_from_tf_files(root: Path, scope: tuple[str, str] | None) -> int:
    try:
        import hcl2
    except ImportError:
        print("ERROR: falta la dependencia 'python-hcl2' (pip install python-hcl2).")
        return 2

    results = []
    for tf_file in sorted(root.rglob("*.tf")):
        if any(part in EXCLUDE_DIR_NAMES for part in tf_file.parts):
            continue
        try:
            with tf_file.open(encoding="utf-8") as fh:
                parsed = hcl2.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"AVISO: no se pudo parsear {tf_file}: {exc}")
            continue
        rel = tf_file.relative_to(root)
        for block in parsed.get("resource", []):
            for resource_type, named in block.items():
                for local_name, attrs in named.items():

                    def literal(key, attrs=attrs):
                        value = attrs.get(key)
                        if not isinstance(value, str) or "${" in value:
                            return None
                        if value.startswith(("var.", "local.", "module.", "data.")):
                            return None
                        return value

                    name, status, detail = _check(resource_type, literal, scope)
                    results.append((f"{rel}: {resource_type}.{local_name}", name, status, detail))
    return _report(results)


# --- Modo 2: JSON de `terraform show -json tfplan` (nombres resueltos) ---


def _planned_resources(module: dict):
    for res in module.get("resources", []):
        if res.get("mode", "managed") == "managed":
            yield res["type"], res["address"], res.get("values") or {}
    for child in module.get("child_modules", []):
        yield from _planned_resources(child)


def validate_from_plan_json(plan_path: Path, scope: tuple[str, str] | None) -> int:
    try:
        with plan_path.open(encoding="utf-8") as fh:
            plan = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se pudo leer {plan_path}: {exc}")
        return 2

    results = []
    for resource_type, address, values in _planned_resources(
        plan.get("planned_values", {}).get("root_module", {})
    ):
        name, status, detail = _check(
            resource_type,
            lambda key: values.get(key) if isinstance(values.get(key), str) else None,
            scope,
        )
        results.append((address, name, status, detail))

    if not results:
        print(f"AVISO: {plan_path} no tiene recursos en planned_values.")
    return _report(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida nombres de recursos AWS contra el estándar F3.")
    parser.add_argument("--plan-json", type=Path, metavar="ARCHIVO",
                        help="JSON de 'terraform show -json tfplan' (valida nombres resueltos).")
    parser.add_argument("--org", help="Organización obligatoria en los nombres, p. ej. beathub.")
    parser.add_argument("--env", choices=["dev", "pre", "pro"], help="Ambiente obligatorio en los nombres.")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="Directorio a escanear en el modo .tf (por defecto, el actual).")
    args = parser.parse_args()
    if bool(args.org) != bool(args.env):
        parser.error("--org y --env van juntos")
    scope = (args.org, args.env) if args.org else None

    if args.plan_json is not None:
        return validate_from_plan_json(args.plan_json, scope)
    return validate_from_tf_files(args.root, scope)


if __name__ == "__main__":
    sys.exit(main())
