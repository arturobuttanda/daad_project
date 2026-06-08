#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Carga Productos.csv e Historial Precios.csv en Oracle.

El script inserta o actualiza datos en las tablas `productos` y
`historial_precios` usando `MERGE` para que el proceso sea idempotente.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import oracledb  # type: ignore[import-not-found]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def cargar_env() -> None:
    """Carga variables desde el .env del proyecto si no existen en el entorno."""
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    if not env_path.exists():
        return

    with env_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


cargar_env()


DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_LOCATION = os.environ.get("WALLET_LOCATION") or os.environ.get("WALLET_PATH")
if not WALLET_LOCATION:
    _project_root = Path(__file__).resolve().parents[2]
    _wallet_root = _project_root / "wallet"
    if _wallet_root.is_dir():
        for _child in sorted(_wallet_root.iterdir()):
            if _child.is_dir() and (_child / "tnsnames.ora").is_file():
                WALLET_LOCATION = str(_child.resolve())
                break
if not WALLET_LOCATION:
    _legacy = Path(__file__).resolve().parents[2] / "Backend" / "ConexionDB" / "Wallet"
    if (_legacy / "tnsnames.ora").is_file():
        WALLET_LOCATION = str(_legacy.resolve())
if not WALLET_LOCATION:
    raise RuntimeError(
        "WALLET_LOCATION no definido. "
        "Configúralo en .env o coloca un wallet en wallet/<carpeta>/"
    )
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

DEFAULT_PRODUCTOS = Path.home() / "Downloads" / "Productos.csv"
DEFAULT_HISTORIAL = Path.home() / "Downloads" / "Historial Precios.csv"
DEFAULT_BATCH_SIZE = 1000


SQL_MERGE_PRODUCTOS = """
MERGE INTO productos p
USING dual ON (p.id_producto = :id_producto)
WHEN MATCHED THEN
  UPDATE SET
    p.nombre = :nombre,
    p.categoria = :categoria,
    p.precio_actual = :precio_actual,
    p.fecha_actualizacion = :fecha_actualizacion
WHEN NOT MATCHED THEN
  INSERT (id_producto, nombre, categoria, precio_actual, fecha_actualizacion)
  VALUES (:id_producto, :nombre, :categoria, :precio_actual, :fecha_actualizacion)
"""


SQL_MERGE_HISTORIAL = """
MERGE INTO historial_precios h
USING dual ON (h.id_producto = :id_producto AND h.fecha = :fecha)
WHEN MATCHED THEN
  UPDATE SET h.precio_registrado = :precio_registrado
WHEN NOT MATCHED THEN
  INSERT (id_producto, fecha, precio_registrado)
  VALUES (:id_producto, :fecha, :precio_registrado)
"""


def normalizar_texto(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parsear_numero(value: Any) -> float:
    text = normalizar_texto(value)
    if not text:
        raise ValueError("Valor numerico vacio")
    return float(text)


def parsear_timestamp(value: Any) -> datetime:
    text = normalizar_texto(value)
    if not text:
        raise ValueError("Fecha vacia")

    text = text.replace("T", " ")
    if "." in text:
        head, fraction = text.split(".", 1)
        fraction = re.sub(r"\D", "", fraction)[:6]
        text = f"{head}.{fraction}" if fraction else head

    formats = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no soportado: {value}")


def parsear_fecha(value: Any) -> date:
    return parsear_timestamp(value).date()


def obtener_cadena_conexion_desde_tnsnames(tnsnames_path: str, dsn_name: str) -> str | None:
    if not os.path.exists(tnsnames_path):
        logger.warning("No se encontro tnsnames.ora en: %s", tnsnames_path)
        return None

    try:
        with open(tnsnames_path, "r", encoding="utf-8") as file:
            content = file.read()

        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(line)
        clean_content = "\n".join(lines)

        pattern = re.compile(
            r"^\s*" + re.escape(dsn_name) + r"\s*=\s*\(",
            re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(clean_content)
        if not match:
            return None

        start_pos = match.end() - 1
        paren_count = 0
        end_pos = start_pos
        for index in range(start_pos, len(clean_content)):
            char = clean_content[index]
            if char == "(":
                paren_count += 1
            elif char == ")":
                paren_count -= 1
                if paren_count == 0:
                    end_pos = index + 1
                    break

        connection_string = clean_content[start_pos:end_pos].strip()
        return " ".join(connection_string.split())
    except Exception as exc:
        logger.error("Error al parsear tnsnames.ora: %s", exc)
        return None


def obtener_conexion_oracle() -> oracledb.Connection:
    tns_path = os.path.join(WALLET_LOCATION, "tnsnames.ora")
    connection_string = obtener_cadena_conexion_desde_tnsnames(tns_path, DB_DSN)

    if connection_string:
        logger.info("DSN '%s' resuelto desde tnsnames.ora.", DB_DSN)
        return oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=connection_string,
            wallet_location=WALLET_LOCATION,
            wallet_password=WALLET_PASSWORD,
        )

    logger.info("Usando DB_DSN directamente con config_dir.")
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=WALLET_LOCATION,
        wallet_location=WALLET_LOCATION,
        wallet_password=WALLET_PASSWORD,
    )


def leer_productos_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {csv_path}")

    registros: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"ID_PRODUCTO", "NOMBRE", "CATEGORIA", "PRECIO_ACTUAL", "FECHA_ACTUALIZACION"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Faltan columnas en {csv_path.name}: {', '.join(sorted(missing))}")

        for row in reader:
            registros.append(
                {
                    "id_producto": normalizar_texto(row["ID_PRODUCTO"]),
                    "nombre": normalizar_texto(row["NOMBRE"]),
                    "categoria": normalizar_texto(row["CATEGORIA"]),
                    "precio_actual": parsear_numero(row["PRECIO_ACTUAL"]),
                    "fecha_actualizacion": parsear_timestamp(row["FECHA_ACTUALIZACION"]),
                }
            )

    return registros


def leer_historial_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {csv_path}")

    registros: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"ID_PRODUCTO", "FECHA", "PRECIO_REGISTRADO"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Faltan columnas en {csv_path.name}: {', '.join(sorted(missing))}")

        for row in reader:
            registros.append(
                {
                    "id_producto": normalizar_texto(row["ID_PRODUCTO"]),
                    "fecha": parsear_fecha(row["FECHA"]),
                    "precio_registrado": parsear_numero(row["PRECIO_REGISTRADO"]),
                }
            )

    return registros


def ejecutar_lotes(cursor: oracledb.Cursor, sql: str, data: list[dict[str, Any]], label: str, batch_size: int) -> None:
    if not data:
        logger.info("No hay registros para insertar en %s.", label)
        return

    total = len(data)
    logger.info("Insertando %s registros en %s...", total, label)

    for index in range(0, total, batch_size):
        batch = data[index:index + batch_size]
        cursor.executemany(sql, batch)
        logger.info("%s: lote %s de %s completado (%s registros).", label, index // batch_size + 1, (total + batch_size - 1) // batch_size, len(batch))


def cargar_csvs(productos_csv: Path, historial_csv: Path, batch_size: int) -> None:
    productos = leer_productos_csv(productos_csv)
    historial = leer_historial_csv(historial_csv)

    logger.info("Archivo de productos: %s (%s filas)", productos_csv, len(productos))
    logger.info("Archivo de historial: %s (%s filas)", historial_csv, len(historial))

    connection = None
    try:
        connection = obtener_conexion_oracle()
        connection.autocommit = False
        cursor = connection.cursor()

        ejecutar_lotes(cursor, SQL_MERGE_PRODUCTOS, productos, "PRODUCTOS", batch_size)
        ejecutar_lotes(cursor, SQL_MERGE_HISTORIAL, historial, "HISTORIAL_PRECIOS", batch_size)

        connection.commit()
        logger.info("Carga finalizada con exito.")
    except Exception as exc:
        logger.error("Falló la carga: %s", exc)
        if connection:
            connection.rollback()
            logger.info("Rollback ejecutado.")
        raise
    finally:
        if connection:
            connection.close()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Carga Productos.csv e Historial Precios.csv en Oracle.")
    parser.add_argument(
        "--productos",
        default=str(DEFAULT_PRODUCTOS),
        help="Ruta del archivo Productos.csv",
    )
    parser.add_argument(
        "--historial",
        default=str(DEFAULT_HISTORIAL),
        help="Ruta del archivo Historial Precios.csv",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Tamaño del lote para executemany",
    )
    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()

    cargar_csvs(
        Path(args.productos),
        Path(args.historial),
        args.batch_size,
    )


if __name__ == "__main__":
    main()