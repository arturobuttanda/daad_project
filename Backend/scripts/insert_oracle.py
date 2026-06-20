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
from pathlib import Path

import oracledb  # type: ignore[import-not-found]
from dotenv import load_dotenv

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

# Cargar .env automáticamente desde la raíz del proyecto
_raiz_proyecto = Path(__file__).resolve().parents[2]
load_dotenv(_raiz_proyecto / ".env")


def _buscar_directorio_wallet() -> str | None:
    raiz_wallet = _raiz_proyecto / "wallet"
    if raiz_wallet.is_dir():
        for elemento in sorted(raiz_wallet.iterdir()):
            if elemento.is_dir() and (elemento / "tnsnames.ora").is_file():
                return str(elemento.resolve())
    ruta_legado = _raiz_proyecto / "Backend" / "ConexionDB" / "Wallet"
    if (ruta_legado / "tnsnames.ora").is_file():
        return str(ruta_legado.resolve())
    return None


USUARIO_BD = os.environ["DB_USER"]
CONTRASENA_BD = os.environ["DB_PASSWORD"]
DSN_BD = os.environ["DB_DSN"]
UBICACION_WALLET = os.environ.get("WALLET_LOCATION") or _buscar_directorio_wallet()
if not UBICACION_WALLET:
    raise RuntimeError(
        "WALLET_LOCATION no definido. "
        "Configúralo en .env o coloca un wallet en wallet/<carpeta>/"
    )

# Convertir la ruta a absoluta para mayor compatibilidad (tanto en Windows como en Linux/WSL)
if not os.path.isabs(UBICACION_WALLET):
    UBICACION_WALLET = os.path.abspath(UBICACION_WALLET)

# Contraseña de la wallet (para descifrar ewallet.p12 o ewallet.pem en mutual TLS).
# Opcional: por defecto se usa cadena vacía.
CONTRASENA_WALLET = os.environ.get("WALLET_PASSWORD", "")

# Tamaño del lote para inserciones masivas
TAMANO_LOTE = 1000

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
             p.precio_actual = :precio_actual
WHEN NOT MATCHED THEN
  INSERT (id_producto, nombre, categoria, precio_actual)
  VALUES (:id_producto, :nombre, :categoria, :precio_actual)
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

def obtener_cadena_conexion_desde_tnsnames(ruta_tns, nombre_dsn):
    """
    Parsea tnsnames.ora para extraer la descripción de conexión (connection string)
    asociada al nombre_dsn, ignorando comentarios.
    """
    if not os.path.exists(ruta_tns):
        logger.warning(f"No se encontro tnsnames.ora en: {ruta_tns}")
        return None
    try:
        with open(ruta_tns, 'r', encoding='utf-8') as f:
            contenido = f.read()

        # Limpiar comentarios y normalizar líneas
        lineas = []
        for linea in contenido.splitlines():
            linea_limpia = linea.strip()
            if linea_limpia and not linea_limpia.startswith('#'):
                lineas.append(linea)
        contenido_limpio = "\n".join(lineas)

        # Buscar el DSN en el archivo
        import re
        patron = re.compile(r'^\s*' + re.escape(nombre_dsn) + r'\s*=\s*\(', re.IGNORECASE | re.MULTILINE)
        coincidencia = patron.search(contenido_limpio)
        if not coincidencia:
            return None

        # Rastrear paréntesis balanceados para extraer toda la descripción
        posicion_inicio = coincidencia.end() - 1  # Inicia en el '('
        contador_parentesis = 0
        posicion_fin = posicion_inicio
        for i in range(posicion_inicio, len(contenido_limpio)):
            caracter = contenido_limpio[i]
            if caracter == '(':
                contador_parentesis += 1
            elif caracter == ')':
                contador_parentesis -= 1
                if contador_parentesis == 0:
                    posicion_fin = i + 1
                    break

        cadena_conexion = contenido_limpio[posicion_inicio:posicion_fin].strip()
        # Eliminar saltos de línea adicionales dentro de la descripción para Oracle
        cadena_conexion = " ".join(cadena_conexion.split())
        return cadena_conexion
    except Exception as e:
        logger.error(f"Error al parsear tnsnames.ora: {e}")
        return None

def probar_conexion():
    """Valida la conectividad a la base de datos."""
    logger.info("Probando conexion con Oracle Cloud (Thin Mode)...")
    try:
        ruta_tns = os.path.join(UBICACION_WALLET, "tnsnames.ora")
        cadena_conexion = obtener_cadena_conexion_desde_tnsnames(ruta_tns, DSN_BD)

        if cadena_conexion:
            logger.info(f"DSN '{DSN_BD}' resuelto exitosamente desde tnsnames.ora.")
            conexion = oracledb.connect(
                user=USUARIO_BD,
                password=CONTRASENA_BD,
                dsn=cadena_conexion,
                wallet_location=UBICACION_WALLET,
                wallet_password=CONTRASENA_WALLET
            )
        else:
            logger.warning(f"No se pudo resolver DSN '{DSN_BD}' en tnsnames.ora. Usando configuracion por defecto con config_dir...")
            conexion = oracledb.connect(
                user=USUARIO_BD,
                password=CONTRASENA_BD,
                dsn=DSN_BD,
                config_dir=UBICACION_WALLET,
                wallet_location=UBICACION_WALLET,
                wallet_password=CONTRASENA_WALLET
            )

        logger.info(f"Conexion exitosa. Version de la BD: {conexion.version}")
        conexion.close()
        return True
    except Exception as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return False

def rellenar_huecos_diarios(precios_observados):
    """
    Dado un dict {fecha: precio} con observaciones esporádicas,
    genera un registro por cada día calendario entre la primera y la última
    fecha observada, rellenando los huecos con el último precio conocido
    (forward-fill).
    """
    if not precios_observados:
        return {}

    fechas_ordenadas = sorted(precios_observados.keys())
    fecha_inicio = fechas_ordenadas[0]
    fecha_fin = fechas_ordenadas[-1]

    precios_diarios = {}
    precio_corriente = None
    fecha_actual = fecha_inicio

    while fecha_actual <= fecha_fin:
        if fecha_actual in precios_observados:
            precio_corriente = precios_observados[fecha_actual]
        if precio_corriente is not None:
            precios_diarios[fecha_actual] = precio_corriente
        fecha_actual += timedelta(days=1)

    return precios_diarios

def cargar_y_limpiar_datos(ruta_json):
    """
    Lee el JSON, limpia los datos, y genera registros DIARIOS de precios
    mediante forward-fill (el último precio conocido se mantiene hasta
    que aparece una nueva observación).
    """
    logger.info(f"Cargando archivo JSON desde: {ruta_json}")
    if not os.path.exists(ruta_json):
        raise FileNotFoundError(f"No se encontro el archivo JSON en: {ruta_json}")

    with open(ruta_json, 'r', encoding='utf-8') as f:
        datos = json.load(f)

    datos_productos = {}
    # Acumular observaciones por producto: {id_prod: {fecha: precio}}
    observaciones_por_producto = {}

    for producto in datos.get("productos", []):
        id_producto = producto.get("id_producto")
        if not id_producto:
            continue

        # Guardar / actualizar información del producto
        datos_productos[id_producto] = {
            "id_producto": id_producto,
            "nombre": producto.get("nombre", "")[:1000],
            "categoria": producto.get("categoria", "")[:100],
            "precio_actual": producto.get("precio_actual")
        }

        # Recopilar observaciones de precios (esporádicas)
        observados = {}
        for entrada_hist in producto.get("historial_precios", []):
            cadena_fecha = entrada_hist.get("fecha")
            if not cadena_fecha:
                continue
            try:
                fecha_dt = datetime.strptime(cadena_fecha, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Formato de fecha invalido en producto {id_producto}: {cadena_fecha}")
                continue
            observados[fecha_dt] = entrada_hist.get("precio_registrado")

        observaciones_por_producto[id_producto] = observados
        logger.info(f"Producto {id_producto}: {len(observados)} observaciones originales del scraper.")

    # Generar registros diarios con forward-fill
    datos_historial = {}
    for id_producto, observados in observaciones_por_producto.items():
        diarios = rellenar_huecos_diarios(observados)
        for fecha_dt, precio in diarios.items():
            datos_historial[(id_producto, fecha_dt)] = precio
        logger.info(f"Producto {id_producto}: {len(diarios)} registros diarios generados (forward-fill).")

    # Formatear listas de diccionarios para executemany
    lista_productos = list(datos_productos.values())
    lista_historial = [
        {
            "id_producto": clave[0],
            "fecha": clave[1],
            "precio_registrado": valor
        }
        for clave, valor in datos_historial.items()
    ]

    logger.info(f"Datos procesados: {len(lista_productos)} productos, {len(lista_historial)} registros diarios totales.")
    return lista_productos, lista_historial

def ejecutar_lotes(cursor, sql, lista_datos, nombre_lote):
    """Ejecuta inserciones por lotes de forma eficiente."""
    total_registros = len(lista_datos)
    if total_registros == 0:
        logger.info(f"No hay registros para insertar en {nombre_lote}.")
        return

    logger.info(f"Iniciando insercion por lotes en {nombre_lote} (Total: {total_registros})...")

    # Procesar en lotes
    for i in range(0, total_registros, TAMANO_LOTE):
        lote = lista_datos[i:i + TAMANO_LOTE]
        try:
            cursor.executemany(sql, lote)
            logger.info(f"Lote {i // TAMANO_LOTE + 1} completado ({len(lote)} registros).")
        except Exception as e:
            logger.error(f"Error procesando lote {i // TAMANO_LOTE + 1} para {nombre_lote}: {e}")
            raise e

def ejecutar_proceso_etl(ruta_json):
    """Ejecuta el proceso completo de ETL hacia Oracle Cloud."""
    try:
        # 1. Cargar y limpiar datos
        productos, historial = cargar_y_limpiar_datos(ruta_json)
    except Exception as e:
        logger.error(f"Error al leer/procesar archivo JSON: {e}")
        return

    # 2. Conectar e insertar en BD
    conexion = None
    try:
        logger.info("Estableciendo conexion con Oracle Cloud (Thin Mode)...")
        ruta_tns = os.path.join(UBICACION_WALLET, "tnsnames.ora")
        cadena_conexion = obtener_cadena_conexion_desde_tnsnames(ruta_tns, DSN_BD)

        if cadena_conexion:
            logger.info(f"DSN '{DSN_BD}' resuelto exitosamente desde tnsnames.ora.")
            conexion = oracledb.connect(
                user=USUARIO_BD,
                password=CONTRASENA_BD,
                dsn=cadena_conexion,
                wallet_location=UBICACION_WALLET,
                wallet_password=CONTRASENA_WALLET
            )
        else:
            logger.warning(f"No se pudo resolver DSN '{DSN_BD}' en tnsnames.ora. Usando configuracion por defecto con config_dir...")
            conexion = oracledb.connect(
                user=USUARIO_BD,
                password=CONTRASENA_BD,
                dsn=DSN_BD,
                config_dir=UBICACION_WALLET,
                wallet_location=UBICACION_WALLET,
                wallet_password=CONTRASENA_WALLET
            )

        # Desactivar autocommit para controlar la transacción
        conexion.autocommit = False
        cursor = conexion.cursor()

        # Insertar productos primero (para respetar integridad de llave foránea)
        ejecutar_lotes(cursor, SQL_MERGE_PRODUCTOS, productos, "PRODUCTOS")

        # Insertar historial de precios después
        ejecutar_lotes(cursor, SQL_MERGE_HISTORIAL, historial, "HISTORIAL_PRECIOS")

        # Confirmar transacción
        conexion.commit()
        logger.info("Pipeline finalizado con exito. Todos los cambios fueron confirmados (COMMIT).")

    except Exception as e:
        logger.error(f"Fallo critico en la ejecucion del pipeline: {e}")
        if conexion:
            logger.warning("Realizando ROLLBACK de la transaccion...")
            conexion.rollback()
    finally:
        if conexion:
            conexion.close()
            logger.info("Conexion a la base de datos cerrada.")

if __name__ == "__main__":
    analizador = argparse.ArgumentParser(description="Pipeline de datos para importar JSON a Oracle Autonomous Database.")
    analizador.add_argument(
        "--json",
        default="prueba.json",
        help="Ruta del archivo JSON de entrada."
    )
    analizador.add_argument(
        "--test",
        action="store_true",
        help="Solo probar la conexion a la base de datos sin insertar datos."
    )
    argumentos = analizador.parse_args()

    if argumentos.test:
        probar_conexion()
    else:
        ejecutar_proceso_etl(argumentos.json)
