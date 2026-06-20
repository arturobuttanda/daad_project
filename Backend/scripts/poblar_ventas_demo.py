from __future__ import annotations

"""Pobla la base de datos con ventas de demostracion de los ultimos 3 meses.

Distribuye los 162 productos entre todos los vendedores,
genera ventas historicas para cada cliente y actualiza el stock.
No modifica las tablas catalogo (productos, usuarios, vendedores).
"""

import os
import random
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path

import oracledb
from dotenv import load_dotenv

RUTA_RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RUTA_RAIZ / ".env")

USUARIO_DB = os.environ["DB_USER"]
CONTRASENA_DB = os.environ["DB_PASSWORD"]
DSN_DB = os.environ["DB_DSN"]
RUTA_WALLET = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
CONTRASENA_WALLET = os.environ.get("WALLET_PASSWORD", "")

if not RUTA_WALLET:
    _raiz_wallet = RUTA_RAIZ / "wallet"
    if _raiz_wallet.is_dir():
        for _hijo in sorted(_raiz_wallet.iterdir()):
            if _hijo.is_dir() and (_hijo / "tnsnames.ora").is_file():
                RUTA_WALLET = str(_hijo)
                break

if not RUTA_WALLET:
    raise RuntimeError("RUTA_WALLET no definida en .env")

ubicacion_wallet = Path(RUTA_WALLET)
if not ubicacion_wallet.is_absolute():
    ubicacion_wallet = (RUTA_RAIZ / ubicacion_wallet).resolve()


def obtener_conexion():
    return oracledb.connect(
        user=USUARIO_DB,
        password=CONTRASENA_DB,
        dsn=DSN_DB,
        config_dir=str(ubicacion_wallet),
        wallet_location=str(ubicacion_wallet),
        wallet_password=CONTRASENA_WALLET,
    )


def consultar_productos(cursor):
    """Obtiene todos los productos con su informacion basica."""
    cursor.execute(
        "SELECT p.id_producto, p.nombre, p.precio_actual, p.stock, "
        "p.precio_fabricacion, p.marca, p.categoria "
        "FROM productos p ORDER BY p.nombre"
    )
    columnas = ["id_producto", "nombre", "precio_actual", "stock",
                "precio_fabricacion", "marca", "categoria"]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def consultar_vendedores(cursor):
    """Obtiene todos los vendedores registrados."""
    cursor.execute(
        "SELECT v.id_vendedor, u.nombre, v.codigo_vendedor "
        "FROM vendedores v "
        "JOIN usuarios u ON u.id_usuario = v.id_vendedor "
        "ORDER BY v.codigo_vendedor"
    )
    return cursor.fetchall()


def consultar_clientes(cursor):
    """Obtiene todos los clientes registrados."""
    cursor.execute(
        "SELECT id_usuario, nombre FROM usuarios "
        "WHERE tipo_usuario = 'Cliente' ORDER BY nombre"
    )
    return cursor.fetchall()


def consultar_asignaciones_existentes(cursor):
    """Verifica si hay productos ya asignados a vendedores."""
    cursor.execute("SELECT COUNT(*) FROM producto_vendedor")
    return int(cursor.fetchone()[0] or 0) > 0


def asignar_productos_si_necesario(cursor, vendedores, productos):
    """Asigna productos a vendedores si no hay asignaciones previas.
    Distribuye equitativamente los 162 productos entre los vendedores."""
    if consultar_asignaciones_existentes(cursor):
        print("Ya existen asignaciones de productos a vendedores. Saltando asignacion.")
        return

    if not vendedores or not productos:
        print("No hay vendedores o productos para asignar.")
        return

    asignados = 0
    for indice, producto in enumerate(productos):
        id_vendedor = vendedores[indice % len(vendedores)][0]
        cursor.execute(
            "INSERT INTO producto_vendedor (id_producto, id_vendedor) "
            "VALUES (:id_producto, :id_vendedor)",
            {"id_producto": producto["id_producto"], "id_vendedor": id_vendedor},
        )
        asignados += 1

    print(f"{asignados} productos asignados a {len(vendedores)} vendedores.")


def obtener_vendedor_producto(cursor, id_producto):
    """Obtiene el vendedor asignado a un producto."""
    cursor.execute(
        "SELECT id_vendedor FROM producto_vendedor "
        "WHERE id_producto = :id_producto",
        {"id_producto": id_producto},
    )
    fila = cursor.fetchone()
    return fila[0] if fila else None


def generar_ventas_demo(cursor, clientes, productos):
    """Genera ventas historicas para los ultimos 3 meses.
    Cada cliente tiene entre 8 y 15 ventas distribuidas en el periodo.
    Cada venta contiene entre 1 y 5 productos."""
    ahora = datetime.now(UTC)
    fecha_inicio = ahora - timedelta(days=90)

    cursor.execute("SELECT COUNT(*) FROM ventas")
    total_existente = int(cursor.fetchone()[0] or 0)
    if total_existente > 50:
        print(f"Ya existen {total_existente} ventas en la base. Saltando generacion.")
        return 0
    if total_existente > 0:
        print(f"Existen {total_existente} ventas previas. Agregando mas ventas demo...")

    semilla = random.Random(20260525)
    creadas = 0

    for id_cliente, nombre_cliente in clientes:
        num_ventas = semilla.randint(8, 15)

        for _ in range(num_ventas):
            id_venta = str(uuid.uuid4())
            dias_atras = semilla.randint(0, 89)
            horas = semilla.randint(8, 20)
            minutos = semilla.randint(0, 59)
            fecha_venta = fecha_inicio + timedelta(days=dias_atras,
                                                   hours=horas, minutes=minutos)

            num_items = semilla.randint(1, 5)
            items_venta = semilla.sample(productos,
                                         k=min(num_items, len(productos)))

            # Encontrar el vendedor del primer producto
            id_vendedor = obtener_vendedor_producto(cursor,
                                                    items_venta[0]["id_producto"])

            # Crear cabecera de venta
            cursor.execute(
                "INSERT INTO ventas (id_venta, id_cliente, id_vendedor, "
                "fecha_venta, monto_total, total_unidades) "
                "VALUES (:id_venta, :id_cliente, :id_vendedor, "
                ":fecha_venta, 0, 0)",
                {
                    "id_venta": id_venta,
                    "id_cliente": id_cliente,
                    "id_vendedor": id_vendedor,
                    "fecha_venta": fecha_venta,
                },
            )

            monto_total = 0.0
            unidades_totales = 0

            for item in items_venta:
                producto_id = item["id_producto"]
                precio = float(item.get("precio_actual") or 0)
                stock = int(item.get("stock") or 0)
                costo = item.get("precio_fabricacion")
                costo_valor = float(costo) if costo is not None else None

                # Cantidad aleatoria entre 1 y min(5, stock-1)
                cantidad = semilla.randint(1, max(1, min(5, stock - 1)))
                if cantidad <= 0 or stock <= 0:
                    continue

                subtotal = round(precio * cantidad, 2)
                margen = round(precio - costo_valor, 2) if costo_valor else None

                monto_total += subtotal
                unidades_totales += cantidad

                # Insertar detalle de venta
                cursor.execute(
                    "INSERT INTO venta_detalle "
                    "(id_venta, id_producto, cantidad, precio_unitario, "
                    "costo_unitario, subtotal, margen_unitario) "
                    "VALUES (:id_venta, :id_producto, :cantidad, "
                    ":precio_unitario, :costo_unitario, :subtotal, :margen)",
                    {
                        "id_venta": id_venta,
                        "id_producto": producto_id,
                        "cantidad": cantidad,
                        "precio_unitario": precio,
                        "costo_unitario": costo_valor,
                        "subtotal": subtotal,
                        "margen": margen,
                    },
                )

                # Actualizar stock
                cursor.execute(
                    "UPDATE productos SET stock = stock - :cantidad "
                    "WHERE id_producto = :id_producto",
                    {
                        "cantidad": cantidad,
                        "fecha": fecha_venta,
                        "id_producto": producto_id,
                    },
                )

            # Actualizar montos de la cabecera
            cursor.execute(
                "UPDATE ventas SET monto_total = :monto, "
                "total_unidades = :unidades WHERE id_venta = :id_venta",
                {
                    "monto": round(monto_total, 2),
                    "unidades": unidades_totales,
                    "id_venta": id_venta,
                },
            )

            creadas += 1

    return creadas


def principal():
    print("Iniciando generacion de ventas demo (3 meses)...")
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            productos = consultar_productos(cursor)
            vendedores = consultar_vendedores(cursor)
            clientes = consultar_clientes(cursor)

            print(f"Productos encontrados: {len(productos)}")
            print(f"Vendedores encontrados: {len(vendedores)}")
            print(f"Clientes encontrados: {len(clientes)}")

            if not productos or not clientes:
                print("No hay suficientes datos para generar ventas.")
                return

            asignar_productos_si_necesario(cursor, vendedores, productos)

            if not consultar_asignaciones_existentes(cursor):
                print("No hay asignaciones de productos. Abortando.")
                return

            ventas_creadas = generar_ventas_demo(cursor, clientes, productos)
            conexion.commit()

    print(f"Generacion completada: {ventas_creadas} ventas creadas "
          f"en los ultimos 3 meses.")


if __name__ == "__main__":
    principal()
