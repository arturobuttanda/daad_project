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
    raiz_proyecto = Path(__file__).resolve().parents[2]
    ruta_env = raiz_proyecto / ".env"
    if not ruta_env.exists():
        return

    with ruta_env.open("r", encoding="utf-8") as archivo:
        for linea_cruda in archivo:
            linea = linea_cruda.strip()
            if not linea or linea.startswith("#"):
                continue
            if "=" not in linea:
                continue

            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            os.environ.setdefault(clave, valor)


cargar_env()


DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_LOCATION = os.environ.get("WALLET_LOCATION") or os.environ.get("WALLET_PATH")
if not WALLET_LOCATION:
    _raiz_proyecto = Path(__file__).resolve().parents[2]
    _raiz_wallet = _raiz_proyecto / "wallet"
    if _raiz_wallet.is_dir():
        for _hijo in sorted(_raiz_wallet.iterdir()):
            if _hijo.is_dir() and (_hijo / "tnsnames.ora").is_file():
                WALLET_LOCATION = str(_hijo.resolve())
                break
if not WALLET_LOCATION:
    _legado = Path(__file__).resolve().parents[2] / "Backend" / "ConexionDB" / "Wallet"
    if (_legado / "tnsnames.ora").is_file():
        WALLET_LOCATION = str(_legado.resolve())
if not WALLET_LOCATION:
    raise RuntimeError(
        "WALLET_LOCATION no definido. "
        "Configúralo en .env o coloca un wallet en wallet/<carpeta>/"
    )
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

DEFAULT_PRODUCTOS = Path.home() / "Downloads" / "Productos.csv"
DEFAULT_HISTORIAL = Path.home() / "Downloads" / "Historial Precios.csv"
DEFAULT_TAMANO_LOTE = 1000


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


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor)).strip()


def parsear_numero(valor: Any) -> float:
    texto = normalizar_texto(valor)
    if not texto:
        raise ValueError("Valor numerico vacio")
    return float(texto)


def parsear_timestamp(valor: Any) -> datetime:
    texto = normalizar_texto(valor)
    if not texto:
        raise ValueError("Fecha vacia")

    texto = texto.replace("T", " ")
    if "." in texto:
        cabecera, fraccion = texto.split(".", 1)
        fraccion = re.sub(r"\D", "", fraccion)[:6]
        texto = f"{cabecera}.{fraccion}" if fraccion else cabecera

    formatos = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for formato in formatos:
        try:
            parseado = datetime.strptime(texto, formato)
            return parseado
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no soportado: {valor}")


def parsear_fecha(valor: Any) -> date:
    return parsear_timestamp(valor).date()


def obtener_cadena_conexion_desde_tnsnames(ruta_tnsnames: str, nombre_dsn: str) -> str | None:
    if not os.path.exists(ruta_tnsnames):
        logger.warning("No se encontro tnsnames.ora en: %s", ruta_tnsnames)
        return None

    try:
        with open(ruta_tnsnames, "r", encoding="utf-8") as archivo:
            contenido = archivo.read()

        lineas = []
        for linea in contenido.splitlines():
            limpia = linea.strip()
            if limpia and not limpia.startswith("#"):
                lineas.append(linea)
        contenido_limpio = "\n".join(lineas)

        patron = re.compile(
            r"^\s*" + re.escape(nombre_dsn) + r"\s*=\s*\(",
            re.IGNORECASE | re.MULTILINE,
        )
        coincidencia = patron.search(contenido_limpio)
        if not coincidencia:
            return None

        pos_inicio = coincidencia.end() - 1
        contador_parentesis = 0
        pos_fin = pos_inicio
        for indice in range(pos_inicio, len(contenido_limpio)):
            caracter = contenido_limpio[indice]
            if caracter == "(":
                contador_parentesis += 1
            elif caracter == ")":
                contador_parentesis -= 1
                if contador_parentesis == 0:
                    pos_fin = indice + 1
                    break

        cadena_conexion = contenido_limpio[pos_inicio:pos_fin].strip()
        return " ".join(cadena_conexion.split())
    except Exception as exc:
        logger.error("Error al parsear tnsnames.ora: %s", exc)
        return None


def obtener_conexion_oracle() -> oracledb.Connection:
    ruta_tns = os.path.join(WALLET_LOCATION, "tnsnames.ora")
    cadena_conexion = obtener_cadena_conexion_desde_tnsnames(ruta_tns, DB_DSN)

    if cadena_conexion:
        logger.info("DSN '%s' resuelto desde tnsnames.ora.", DB_DSN)
        return oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=cadena_conexion,
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


def leer_productos_csv(ruta_csv: Path) -> list[dict[str, Any]]:
    if not ruta_csv.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {ruta_csv}")

    registros: list[dict[str, Any]] = []
    with ruta_csv.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas_requeridas = {"ID_PRODUCTO", "NOMBRE", "CATEGORIA", "PRECIO_ACTUAL", "FECHA_ACTUALIZACION"}
        faltantes = columnas_requeridas - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(f"Faltan columnas en {ruta_csv.name}: {', '.join(sorted(faltantes))}")

        for fila in lector:
            registros.append(
                {
                    "id_producto": normalizar_texto(fila["ID_PRODUCTO"]),
                    "nombre": normalizar_texto(fila["NOMBRE"]),
                    "categoria": normalizar_texto(fila["CATEGORIA"]),
                    "precio_actual": parsear_numero(fila["PRECIO_ACTUAL"]),
                    "fecha_actualizacion": parsear_timestamp(fila["FECHA_ACTUALIZACION"]),
                }
            )

    return registros


def leer_historial_csv(ruta_csv: Path) -> list[dict[str, Any]]:
    if not ruta_csv.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {ruta_csv}")

    registros: list[dict[str, Any]] = []
    with ruta_csv.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas_requeridas = {"ID_PRODUCTO", "FECHA", "PRECIO_REGISTRADO"}
        faltantes = columnas_requeridas - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(f"Faltan columnas en {ruta_csv.name}: {', '.join(sorted(faltantes))}")

        for fila in lector:
            registros.append(
                {
                    "id_producto": normalizar_texto(fila["ID_PRODUCTO"]),
                    "fecha": parsear_fecha(fila["FECHA"]),
                    "precio_registrado": parsear_numero(fila["PRECIO_REGISTRADO"]),
                }
            )

    return registros


def ejecutar_lotes(cursor: oracledb.Cursor, sql: str, datos: list[dict[str, Any]], etiqueta: str, tamano_lote: int) -> None:
    if not datos:
        logger.info("No hay registros para insertar en %s.", etiqueta)
        return

    total = len(datos)
    logger.info("Insertando %s registros en %s...", total, etiqueta)

    for indice in range(0, total, tamano_lote):
        lote = datos[indice:indice + tamano_lote]
        cursor.executemany(sql, lote)
        logger.info("%s: lote %s de %s completado (%s registros).", etiqueta, indice // tamano_lote + 1, (total + tamano_lote - 1) // tamano_lote, len(lote))


def cargar_csvs(productos_csv: Path, historial_csv: Path, tamano_lote: int) -> None:
    productos = leer_productos_csv(productos_csv)
    historial = leer_historial_csv(historial_csv)

    logger.info("Archivo de productos: %s (%s filas)", productos_csv, len(productos))
    logger.info("Archivo de historial: %s (%s filas)", historial_csv, len(historial))

    conexion = None
    try:
        conexion = obtener_conexion_oracle()
        conexion.autocommit = False
        cursor = conexion.cursor()

        ejecutar_lotes(cursor, SQL_MERGE_PRODUCTOS, productos, "PRODUCTOS", tamano_lote)
        ejecutar_lotes(cursor, SQL_MERGE_HISTORIAL, historial, "HISTORIAL_PRECIOS", tamano_lote)

        conexion.commit()
        logger.info("Carga finalizada con exito.")
    except Exception as exc:
        logger.error("Falló la carga: %s", exc)
        if conexion:
            conexion.rollback()
            logger.info("Rollback ejecutado.")
        raise
    finally:
        if conexion:
            conexion.close()


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
        default=DEFAULT_TAMANO_LOTE,
        dest="tamano_lote",
        help="Tamaño del lote para executemany",
    )
    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()

    cargar_csvs(
        Path(args.productos),
        Path(args.historial),
        args.tamano_lote,
    )


if __name__ == "__main__":
    main()
