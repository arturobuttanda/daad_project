"""Verifica las columnas actuales de la tabla productos en Oracle."""
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
cursor.execute("SELECT column_name, data_type FROM user_tab_columns WHERE table_name = 'PRODUCTOS' ORDER BY column_id")
for fila in cursor.fetchall():
    print(fila[0], "->", fila[1])
cursor.close()
conn.close()
