"""Ejecuta la migracion completa de la tabla productos:
1. Respaldar datos actuales
2. Crear tabla nueva sin fechas
3. Eliminar constraints de hijas
4. Eliminar tabla vieja
5. Renombrar y recrear constraints
6. Cargar datos desde Productos.csv
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


def ejecutar_sql(cursor, sql, descripcion=""):
    try:
        cursor.execute(sql)
        print(f"  OK: {descripcion or sql[:60]}...")
    except Exception as exc:
        print(f"  ERROR en {descripcion or sql[:60]}: {exc}")
        raise


def migrar_tabla(cursor):
    print("\n--- Migrando tabla productos ---")

    try:
        cursor.execute("DROP TABLE productos_backup PURGE")
    except Exception:
        pass
    ejecutar_sql(cursor, "CREATE TABLE productos_backup AS SELECT * FROM productos", "Respaldar datos")

    ejecutar_sql(
        cursor,
        """CREATE TABLE productos_nueva AS
           SELECT id_producto, nombre, categoria, marca, precio_actual, stock, precio_fabricacion
           FROM productos""",
        "Crear tabla nueva sin fechas",
    )

    for fk in [
        ("ALTER TABLE producto_vendedor DROP CONSTRAINT fk_pv_producto", "FK pv_producto"),
        ("ALTER TABLE venta_detalle DROP CONSTRAINT fk_detalle_producto", "FK detalle_producto"),
        ("ALTER TABLE historial_precios DROP CONSTRAINT fk_historial_productos", "FK historial_productos"),
    ]:
        try:
            cursor.execute(fk[0])
            print(f"  OK: Drop {fk[1]}")
        except Exception:
            print(f"  SKIP: Drop {fk[1]} (no existe)")

    ejecutar_sql(cursor, "DROP TABLE productos CASCADE CONSTRAINTS", "Eliminar tabla vieja")

    ejecutar_sql(cursor, "ALTER TABLE productos_nueva RENAME TO productos", "Renombrar tabla")

    ejecutar_sql(cursor, "ALTER TABLE productos ADD CONSTRAINT pk_productos PRIMARY KEY (id_producto)", "PK")
    ejecutar_sql(cursor, "ALTER TABLE productos ADD CONSTRAINT chk_precio_actual CHECK (precio_actual >= 0)", "CK precio")
    ejecutar_sql(cursor, "ALTER TABLE productos ADD CONSTRAINT chk_stock CHECK (stock >= 0)", "CK stock")
    ejecutar_sql(cursor, "ALTER TABLE productos ADD CONSTRAINT chk_precio_fabricacion CHECK (precio_fabricacion >= 0)", "CK costo")

    for fk in [
        ("ALTER TABLE producto_vendedor ADD CONSTRAINT fk_pv_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE", "FK pv_producto"),
        ("ALTER TABLE venta_detalle ADD CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto)", "FK detalle_producto"),
        ("ALTER TABLE historial_precios ADD CONSTRAINT fk_historial_productos FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE", "FK historial_productos"),
    ]:
        try:
            cursor.execute(fk[0])
            print(f"  OK: {fk[1]}")
        except Exception:
            print(f"  SKIP: {fk[1]} (no se pudo crear)")

    ejecutar_sql(cursor, "CREATE INDEX idx_productos_cat ON productos(categoria)", "Indice categoria")

    print("  Migracion completada exitosamente.")


def cargar_csv(cursor):
    print("\n--- Cargando Productos.csv ---")

    if not RUTA_CSV.exists():
        raise FileNotFoundError(f"No se encontro {RUTA_CSV}")

    productos = []
    with RUTA_CSV.open("r", encoding="utf-8-sig", newline="") as archivo:
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

    print(f"  Leidos {len(productos)} productos del CSV.")

    cursor.execute("TRUNCATE TABLE productos")

    sql = """INSERT INTO productos (id_producto, nombre, categoria, marca, precio_actual, stock, precio_fabricacion)
             VALUES (:id_producto, :nombre, :categoria, :marca, :precio_actual, :stock, :precio_fabricacion)"""

    for prod in productos:
        cursor.execute(sql, prod)

    print(f"  Insertados {len(productos)} productos.")


def main():
    print("=== MIGRACION DE TABLA PRODUCTOS ===")
    print(f"Conectando a Oracle (DSN: {DSN_DB})...")

    conn = conectar()
    cursor = conn.cursor()

    try:
        migrar_tabla(cursor)
        cargar_csv(cursor)
        conn.commit()
        print("\n=== MIGRACION COMPLETADA EXITOSAMENTE ===")
    except Exception as exc:
        conn.rollback()
        print(f"\n=== ERROR: {exc} ===")
        print("Todos los cambios fueron revertidos.")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
