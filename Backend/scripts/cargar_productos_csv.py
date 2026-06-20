"""Carga los datos de Productos.csv en la tabla productos.

Uso:
    python cargar_productos_csv.py

Requisitos:
    - .env configurado con credenciales de Oracle
    - La tabla productos debe existir (sin fecha_actualizacion ni fecha_caducidad)
"""

import csv
import os
import sys
from pathlib import Path

import oracledb

RUTA_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUTA_RAIZ))

from dotenv import load_dotenv

load_dotenv(RUTA_RAIZ / ".env")

USUARIO_DB = os.environ["DB_USER"]
CONTRASENA_DB = os.environ["DB_PASSWORD"]
DSN_DB = os.environ["DB_DSN"]
RUTA_WALLET = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
CONTRASENA_WALLET = os.environ.get("WALLET_PASSWORD", "")

RUTA_CSV = RUTA_RAIZ / "EDA" / "Productos.csv"


def conectar():
    return oracledb.connect(
        user=USUARIO_DB,
        password=CONTRASENA_DB,
        dsn=DSN_DB,
        config_dir=RUTA_WALLET,
        wallet_location=RUTA_WALLET,
        wallet_password=CONTRASENA_WALLET,
    )


def leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro {ruta}")

    registros = []
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas_requeridas = {"ID_PRODUCTO", "NOMBRE", "CATEGORIA", "MARCA", "PRECIO_ACTUAL", "STOCK", "PRECIO_FABRICACION"}
        faltantes = columnas_requeridas - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(f"Faltan columnas en {ruta.name}: {', '.join(sorted(faltantes))}")

        for fila in lector:
            registros.append({
                "id_producto": fila["ID_PRODUCTO"].strip().upper(),
                "nombre": fila["NOMBRE"].strip(),
                "categoria": fila["CATEGORIA"].strip() or None,
                "marca": fila["MARCA"].strip() or None,
                "precio_actual": float(fila["PRECIO_ACTUAL"]) if fila["PRECIO_ACTUAL"] else None,
                "stock": int(fila["STOCK"]) if fila["STOCK"] else 0,
                "precio_fabricacion": float(fila["PRECIO_FABRICACION"]) if fila["PRECIO_FABRICACION"] else None,
            })

    return registros


def main():
    print(f"Leyendo {RUTA_CSV}...")
    productos = leer_csv(RUTA_CSV)
    print(f"Se leyeron {len(productos)} productos.")

    print("Conectando a Oracle...")
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute("TRUNCATE TABLE productos")
        print("Tabla productos truncada.")

        sql = """INSERT INTO productos (id_producto, nombre, categoria, marca, precio_actual, stock, precio_fabricacion)
                 VALUES (:id_producto, :nombre, :categoria, :marca, :precio_actual, :stock, :precio_fabricacion)"""

        contador = 0
        for prod in productos:
            cursor.execute(sql, prod)
            contador += 1

        conn.commit()
        print(f"Insertados {contador} productos correctamente.")

    except Exception as exc:
        conn.rollback()
        print(f"Error: {exc}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
