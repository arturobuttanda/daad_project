"""Carga Productos.csv en la tabla productos (ya migrada)."""
import csv
import os
import sys
from pathlib import Path

import oracledb

RUTA_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUTA_RAIZ))
from dotenv import load_dotenv

load_dotenv(RUTA_RAIZ / ".env")

conn = oracledb.connect(
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dsn=os.environ["DB_DSN"],
    config_dir=os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION"),
    wallet_location=os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION"),
    wallet_password=os.environ.get("WALLET_PASSWORD", ""),
)
cursor = conn.cursor()

ruta_csv = RUTA_RAIZ / "EDA" / "Productos.csv"

productos = []
with ruta_csv.open("r", encoding="utf-8-sig", newline="") as archivo:
    lector = csv.DictReader(archivo)
    for fila in lector:
        productos.append({
            "id_producto": fila["ID_PRODUCTO"].strip().upper(),
            "nombre": fila["NOMBRE"].strip(),
            "categoria": fila["CATEGORIA"].strip() or None,
            "marca": fila["MARCA"].strip() or None,
            "precio_actual": float(fila["PRECIO_ACTUAL"]) if fila["PRECIO_ACTUAL"] else None,
            "stock": int(fila["STOCK"]) if fila["STOCK"] else 0,
            "precio_fabricacion": float(fila["PRECIO_FABRICACION"]) if fila["PRECIO_FABRICACION"] else None,
        })

print(f"Leidos {len(productos)} productos del CSV.")

try:
    sql = """MERGE INTO productos p
             USING dual ON (p.id_producto = :id_producto)
             WHEN MATCHED THEN
               UPDATE SET p.nombre = :nombre, p.categoria = :categoria, p.marca = :marca,
                          p.precio_actual = :precio_actual, p.stock = :stock,
                          p.precio_fabricacion = :precio_fabricacion
             WHEN NOT MATCHED THEN
               INSERT (id_producto, nombre, categoria, marca, precio_actual, stock, precio_fabricacion)
               VALUES (:id_producto, :nombre, :categoria, :marca, :precio_actual, :stock, :precio_fabricacion)"""

    for prod in productos:
        cursor.execute(sql, prod)

    conn.commit()
    print(f"Upserted {len(productos)} productos.")

    cursor.execute("SELECT COUNT(*) FROM productos")
    print(f"Total en BD: {cursor.fetchone()[0]}")

except Exception as exc:
    conn.rollback()
    print(f"Error: {exc}")

cursor.close()
conn.close()
print("Carga completada.")
