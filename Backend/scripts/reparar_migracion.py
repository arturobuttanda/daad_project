"""Repara la migracion: corrige datos y recrea constraints faltantes."""
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

# Verificar datos
cursor.execute("SELECT COUNT(*) FROM productos_backup")
total = cursor.fetchone()[0]
print(f"Registros en backup: {total}")

cursor.execute("SELECT id_producto, stock, precio_actual, precio_fabricacion FROM productos_backup WHERE stock < 0 OR stock IS NULL OR precio_actual < 0 OR precio_fabricacion < 0")
malos = cursor.fetchall()
print(f"Registros con valores invalidos: {len(malos)}")
for m in malos:
    print(f"  {m[0]}: stock={m[1]}, precio={m[2]}, costo={m[3]}")

# Corregir datos en productos_nueva
if len(malos) > 0:
    cursor.execute("UPDATE productos SET stock = 0 WHERE stock < 0 OR stock IS NULL")
    cursor.execute("UPDATE productos SET precio_actual = 0 WHERE precio_actual < 0")
    cursor.execute("UPDATE productos SET precio_fabricacion = 0 WHERE precio_fabricacion < 0")
    conn.commit()
    print("Datos corregidos.")

# Recrear constraints faltantes
for sql, nombre in [
    ("ALTER TABLE productos ADD CONSTRAINT chk_stock CHECK (stock >= 0)", "CK stock"),
    ("ALTER TABLE productos ADD CONSTRAINT chk_precio_fabricacion CHECK (precio_fabricacion >= 0)", "CK costo"),
]:
    try:
        cursor.execute(sql)
        print(f"OK: {nombre}")
    except Exception as exc:
        print(f"ERROR: {nombre}: {exc}")

# Recrear FK (si existian antes)
for sql, nombre in [
    ("ALTER TABLE producto_vendedor ADD CONSTRAINT fk_pv_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE", "FK pv_producto"),
    ("ALTER TABLE venta_detalle ADD CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto)", "FK detalle_producto"),
    ("ALTER TABLE historial_precios ADD CONSTRAINT fk_historial_productos FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE", "FK historial_productos"),
]:
    try:
        cursor.execute(sql)
        print(f"OK: {nombre}")
    except Exception:
        print(f"SKIP: {nombre} (no aplica)")

try:
    cursor.execute("CREATE INDEX idx_productos_cat ON productos(categoria)")
    print("OK: indice categoria")
except Exception:
    print("SKIP: indice categoria")

# Verificar columnas finales
cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'PRODUCTOS' ORDER BY column_id")
print("\nColumnas finales:")
for f in cursor.fetchall():
    print(f"  - {f[0]}")

cursor.close()
conn.close()
print("\nReparacion completada.")
