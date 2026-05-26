#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline de Carga de Datos en Oracle Cloud (Autonomous Database) en Thin Mode.
Este script lee un archivo JSON con productos de Amazon e inserta/actualiza
la información en las tablas PRODUCTOS y HISTORIAL_PRECIOS de forma eficiente.
"""

import os
import json
import logging
import argparse
from datetime import datetime, timedelta
import oracledb  # type: ignore[import-not-found]

# Configuración de Logging para producción
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN DE ACCESO Y CREDENCIALES
# ==============================================================================
# Configura las variables de entorno en un archivo .env (ver .env.example).
# NUNCA edites valores por defecto con credenciales reales.
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_LOCATION = os.environ["WALLET_LOCATION"]

# Convertir la ruta a absoluta para mayor compatibilidad (tanto en Windows como en Linux/WSL)
if not os.path.isabs(WALLET_LOCATION):
    WALLET_LOCATION = os.path.abspath(WALLET_LOCATION)

# Contraseña de la wallet (para descifrar ewallet.p12 o ewallet.pem en mutual TLS).
# Opcional: si no se define, se usa cadena vacía.
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

# Tamaño del lote para inserciones masivas
BATCH_SIZE = 1000

# ==============================================================================
# SENTENCIAS SQL (UPSERT CON MERGE)
# ==============================================================================
# Upsert para la tabla PRODUCTOS
SQL_MERGE_PRODUCTOS = """
MERGE INTO productos p
USING dual ON (p.id_producto = :id_producto)
WHEN MATCHED THEN
  UPDATE SET p.nombre = :nombre, 
             p.categoria = :categoria, 
             p.precio_actual = :precio_actual, 
             p.fecha_actualizacion = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN
  INSERT (id_producto, nombre, categoria, precio_actual, fecha_actualizacion)
  VALUES (:id_producto, :nombre, :categoria, :precio_actual, CURRENT_TIMESTAMP)
"""

# Upsert para la tabla HISTORIAL_PRECIOS
# Se usa MERGE para evitar duplicados si se procesan los mismos días
SQL_MERGE_HISTORIAL = """
MERGE INTO historial_precios h
USING dual ON (h.id_producto = :id_producto AND h.fecha = :fecha)
WHEN MATCHED THEN
  UPDATE SET h.precio_registrado = :precio_registrado
WHEN NOT MATCHED THEN
  INSERT (id_producto, fecha, precio_registrado)
  VALUES (:id_producto, :fecha, :precio_registrado)
"""

def get_connection_string_from_tnsnames(tnsnames_path, dsn_name):
    """
    Parsea tnsnames.ora para extraer la descripción de conexión (connection string)
    asociada al dsn_name, ignorando comentarios.
    """
    if not os.path.exists(tnsnames_path):
        logger.warning(f"No se encontro tnsnames.ora en: {tnsnames_path}")
        return None
    try:
        with open(tnsnames_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Limpiar comentarios y normalizar líneas
        lines = []
        for line in content.splitlines():
            line_strip = line.strip()
            if line_strip and not line_strip.startswith('#'):
                lines.append(line)
        clean_content = "\n".join(lines)
        
        # Buscar el DSN en el archivo
        import re
        pattern = re.compile(r'^\s*' + re.escape(dsn_name) + r'\s*=\s*\(', re.IGNORECASE | re.MULTILINE)
        match = pattern.search(clean_content)
        if not match:
            return None
        
        # Rastrear paréntesis balanceados para extraer toda la descripción
        start_pos = match.end() - 1  # Inicia en el '('
        paren_count = 0
        end_pos = start_pos
        for i in range(start_pos, len(clean_content)):
            char = clean_content[i]
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                if paren_count == 0:
                    end_pos = i + 1
                    break
        
        connection_string = clean_content[start_pos:end_pos].strip()
        # Eliminar saltos de línea adicionales dentro de la descripción para Oracle
        connection_string = " ".join(connection_string.split())
        return connection_string
    except Exception as e:
        logger.error(f"Error al parsear tnsnames.ora: {e}")
        return None

def test_connection():
    """Valida la conectividad a la base de datos."""
    logger.info("Probando conexion con Oracle Cloud (Thin Mode)...")
    try:
        tns_path = os.path.join(WALLET_LOCATION, "tnsnames.ora")
        connection_string = get_connection_string_from_tnsnames(tns_path, DB_DSN)
        
        if connection_string:
            logger.info(f"DSN '{DB_DSN}' resuelto exitosamente desde tnsnames.ora.")
            connection = oracledb.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dsn=connection_string,
                wallet_location=WALLET_LOCATION,
                wallet_password=WALLET_PASSWORD
            )
        else:
            logger.warning(f"No se pudo resolver DSN '{DB_DSN}' en tnsnames.ora. Usando configuracion por defecto con config_dir...")
            connection = oracledb.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dsn=DB_DSN,
                config_dir=WALLET_LOCATION,
                wallet_location=WALLET_LOCATION,
                wallet_password=WALLET_PASSWORD
            )
            
        logger.info(f"Conexion exitosa. Version de la BD: {connection.version}")
        connection.close()
        return True
    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return False

def forward_fill_daily(observed_prices):
    """
    Dado un dict {date: precio} con observaciones esporádicas,
    genera un registro por cada día calendario entre la primera y la última
    fecha observada, rellenando los huecos con el último precio conocido
    (forward-fill).
    """
    if not observed_prices:
        return {}

    sorted_dates = sorted(observed_prices.keys())
    start_date = sorted_dates[0]
    end_date = sorted_dates[-1]

    daily_prices = {}
    current_price = None
    current_date = start_date

    while current_date <= end_date:
        if current_date in observed_prices:
            current_price = observed_prices[current_date]
        if current_price is not None:
            daily_prices[current_date] = current_price
        current_date += timedelta(days=1)

    return daily_prices

def load_and_clean_data(json_path):
    """
    Lee el JSON, limpia los datos, y genera registros DIARIOS de precios
    mediante forward-fill (el último precio conocido se mantiene hasta
    que aparece una nueva observación).
    """
    logger.info(f"Cargando archivo JSON desde: {json_path}")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"No se encontro el archivo JSON en: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    productos_data = {}
    # Acumular observaciones por producto: {id_prod: {date: precio}}
    observaciones_por_producto = {}

    for prod in data.get("productos", []):
        id_prod = prod.get("id_producto")
        if not id_prod:
            continue
        
        # Guardar / actualizar información del producto
        productos_data[id_prod] = {
            "id_producto": id_prod,
            "nombre": prod.get("nombre", "")[:1000],
            "categoria": prod.get("categoria", "")[:100],
            "precio_actual": prod.get("precio_actual")
        }

        # Recopilar observaciones de precios (esporádicas)
        observed = {}
        for hist in prod.get("historial_precios", []):
            fecha_str = hist.get("fecha")
            if not fecha_str:
                continue
            try:
                fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Formato de fecha invalido en producto {id_prod}: {fecha_str}")
                continue
            observed[fecha_dt] = hist.get("precio_registrado")

        observaciones_por_producto[id_prod] = observed
        logger.info(f"Producto {id_prod}: {len(observed)} observaciones originales del scraper.")

    # Generar registros diarios con forward-fill
    historial_data = {}
    for id_prod, observed in observaciones_por_producto.items():
        daily = forward_fill_daily(observed)
        for fecha_dt, precio in daily.items():
            historial_data[(id_prod, fecha_dt)] = precio
        logger.info(f"Producto {id_prod}: {len(daily)} registros diarios generados (forward-fill).")

    # Formatear listas de dicts para executemany
    list_productos = list(productos_data.values())
    list_historial = [
        {
            "id_producto": k[0],
            "fecha": k[1],
            "precio_registrado": v
        }
        for k, v in historial_data.items()
    ]

    logger.info(f"Datos procesados: {len(list_productos)} productos, {len(list_historial)} registros diarios totales.")
    return list_productos, list_historial

def execute_batch(cursor, sql, data_list, batch_name):
    """Ejecuta inserciones por lotes de forma eficiente."""
    total_records = len(data_list)
    if total_records == 0:
        logger.info(f"No hay registros para insertar en {batch_name}.")
        return

    logger.info(f"Iniciando insercion por lotes en {batch_name} (Total: {total_records})...")
    
    # Procesar en lotes (batching)
    for i in range(0, total_records, BATCH_SIZE):
        batch = data_list[i:i + BATCH_SIZE]
        try:
            cursor.executemany(sql, batch)
            logger.info(f"Lote {i // BATCH_SIZE + 1} completado ({len(batch)} registros).")
        except Exception as e:
            logger.error(f"Error procesando lote {i // BATCH_SIZE + 1} para {batch_name}: {e}")
            raise e

def run_pipeline(json_path):
    """Ejecuta el pipeline completo de ETL hacia Oracle Cloud."""
    try:
        # 1. Cargar y limpiar datos
        productos, historial = load_and_clean_data(json_path)
    except Exception as e:
        logger.error(f"Error al leer/procesar archivo JSON: {e}")
        return

    # 2. Conectar e insertar en BD
    connection = None
    try:
        logger.info("Estableciendo conexion con Oracle Cloud (Thin Mode)...")
        tns_path = os.path.join(WALLET_LOCATION, "tnsnames.ora")
        connection_string = get_connection_string_from_tnsnames(tns_path, DB_DSN)
        
        if connection_string:
            logger.info(f"DSN '{DB_DSN}' resuelto exitosamente desde tnsnames.ora.")
            connection = oracledb.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dsn=connection_string,
                wallet_location=WALLET_LOCATION,
                wallet_password=WALLET_PASSWORD
            )
        else:
            logger.warning(f"No se pudo resolver DSN '{DB_DSN}' en tnsnames.ora. Usando configuracion por defecto con config_dir...")
            connection = oracledb.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dsn=DB_DSN,
                config_dir=WALLET_LOCATION,
                wallet_location=WALLET_LOCATION,
                wallet_password=WALLET_PASSWORD
            )
        
        # Desactivar autocommit para controlar la transaccion
        connection.autocommit = False
        cursor = connection.cursor()

        # Insertar productos primero (para respetar integridad de llave foranea)
        execute_batch(cursor, SQL_MERGE_PRODUCTOS, productos, "PRODUCTOS")

        # Insertar historial de precios despues
        execute_batch(cursor, SQL_MERGE_HISTORIAL, historial, "HISTORIAL_PRECIOS")

        # Confirmar transaccion
        connection.commit()
        logger.info("Pipeline finalizado con exito. Todos los cambios fueron confirmados (COMMIT).")

    except Exception as e:
        logger.error(f"Fallo critico en la ejecucion del pipeline: {e}")
        if connection:
            logger.warning("Realizando ROLLBACK de la transaccion...")
            connection.rollback()
    finally:
        if connection:
            connection.close()
            logger.info("Conexion a la base de datos cerrada.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de datos para importar JSON a Oracle Autonomous Database.")
    parser.add_argument(
        "--json",
        default="prueba.json",
        help="Ruta del archivo JSON de entrada."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Solo probar la conexion a la base de datos sin insertar datos."
    )
    args = parser.parse_args()

    if args.test:
        test_connection()
    else:
        run_pipeline(args.json)
