"""Limpia tablas residuales de intentos de migracion fallidos."""
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

for tabla in ["PRODUCTOS_NUEVA", "PRODUCTOS_BACKUP"]:
    cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name = '{tabla}'")
    if cursor.fetchone()[0] > 0:
        cursor.execute(f"DROP TABLE {tabla} PURGE")
        print(f"Eliminada tabla {tabla}")
    else:
        print(f"Tabla {tabla} no existe")

cursor.close()
conn.close()
print("Limpieza completada.")
