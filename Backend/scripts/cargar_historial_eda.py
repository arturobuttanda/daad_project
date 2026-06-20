"""Carga HistorialPrecios_EDA.csv a Oracle:
1. Renombra historial_precios -> historial_precios_raw
2. Crea nueva tabla historial_precios con misma estructura
3. Carga datos desde CSV

Uso: python cargar_historial_eda.py
"""
import csv
import os
import sys
from pathlib import Path

import oracledb

r = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(r))
from dotenv import load_dotenv

load_dotenv(r / ".env")

CSV_PATH = r / "EDA" / "HistorialPrecios_EDA.csv"
COLUMNS = ["ID_PRODUCTO", "FECHA", "PRECIO_REGISTRADO"]
TABLE_OLD = "historial_precios"
TABLE_BACKUP = "historial_precios_raw"
TABLE_NEW = "historial_precios"


def conectar():
    return oracledb.connect(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dsn=os.environ.get("DB_DSN"),
        config_dir=os.environ.get("WALLET_PATH"),
        wallet_location=os.environ.get("WALLET_PATH"),
        wallet_password=os.environ.get("WALLET_PASSWORD", ""),
    )


def main():
    print("=== Migracion HistorialPrecios EDA ===\n")
    conn = conectar()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Paso 1: Renombrar tabla actual si existe
        print("1. Renombrando tabla actual...")
        cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = :t", {"t": TABLE_OLD.upper()})
        existe = cursor.fetchone()[0] > 0

        if not existe:
            print(f"  La tabla {TABLE_OLD} no existe. Nada que renombrar.")
        else:
            # Si ya existe el backup, lo eliminamos
            cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = :t", {"t": TABLE_BACKUP.upper()})
            if cursor.fetchone()[0] > 0:
                print(f"  Eliminando tabla existente {TABLE_BACKUP}...")
                cursor.execute(f"DROP TABLE {TABLE_BACKUP} CASCADE CONSTRAINTS PURGE")
                conn.commit()
            print(f"  Renombrando {TABLE_OLD} -> {TABLE_BACKUP}...")
            cursor.execute(f"ALTER TABLE {TABLE_OLD} RENAME TO {TABLE_BACKUP}")
            # Eliminar FK antigua que se arrastra con el rename para evitar conflicto de nombre
            try:
                cursor.execute(f"ALTER TABLE {TABLE_BACKUP} DROP CONSTRAINT fk_historial_productos")
            except oracledb.DatabaseError:
                pass  # puede que no exista o tenga otro nombre
            conn.commit()
            print(f"  OK")

        # Paso 2: Crear nueva tabla historial_precios
        print("\n2. Creando nueva tabla historial_precios...")
        cursor.execute(
            f"""CREATE TABLE {TABLE_NEW} (
                id_producto    VARCHAR2(50)   NOT NULL,
                fecha          DATE           NOT NULL,
                precio_registrado NUMBER(10,2) NOT NULL
            )"""
        )
        conn.commit()
        print(f"  Tabla {TABLE_NEW} creada")

        # FK a productos (si no existe ya)
        try:
            cursor.execute(
                f"""ALTER TABLE {TABLE_NEW}
                    ADD CONSTRAINT fk_historial_productos
                    FOREIGN KEY (id_producto)
                    REFERENCES productos(id_producto)
                    ON DELETE CASCADE"""
            )
            conn.commit()
            print(f"  FK fk_historial_productos agregada")
        except oracledb.DatabaseError as e:
            error, = e.args
            if error.code == 2275:  # ORA-02275: constraint name already exists
                print(f"  FK fk_historial_productos ya existe (ok)")
            else:
                raise

        # Paso 3: Cargar CSV
        print(f"\n3. Cargando datos desde {CSV_PATH}...")
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            lector = csv.DictReader(f)
            filas = list(lector)

        total = len(filas)
        print(f"  Total filas: {total}")

        BATCH = 5000
        insertados = 0
        for i in range(0, total, BATCH):
            lote = filas[i : i + BATCH]
            valores = []
            for fila in lote:
                id_prod = fila["ID_PRODUCTO"].strip().strip('"')
                fecha = fila["FECHA"].strip().strip('"')
                precio = fila["PRECIO_REGISTRADO"].strip().strip('"')
                valores.append((id_prod, fecha, precio))

            cursor.executemany(
                f"""INSERT INTO {TABLE_NEW} (id_producto, fecha, precio_registrado)
                    VALUES (:1, TO_DATE(:2, 'YYYY-MM-DD HH24:MI:SS'), :3)""",
                valores,
            )
            conn.commit()
            insertados += len(lote)
            print(f"  Progreso: {insertados}/{total} ({insertados*100//total}%)")

        print(f"  Carga completada: {insertados} registros")

        # Verificacion
        print(f"\n4. Verificando...")
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NEW}")
        print(f"  Registros en {TABLE_NEW}: {cursor.fetchone()[0]}")
        cursor.execute(f"SELECT MIN(fecha), MAX(fecha) FROM {TABLE_NEW}")
        r = cursor.fetchone()
        print(f"  Rango fechas: {r[0]} a {r[1]}")
        cursor.execute(f"SELECT COUNT(DISTINCT id_producto) FROM {TABLE_NEW}")
        print(f"  Productos distintos: {cursor.fetchone()[0]}")

        if existe:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_BACKUP}")
            print(f"  Registros en {TABLE_BACKUP}: {cursor.fetchone()[0]}")

        print(f"\nMigracion completada exitosamente.")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
