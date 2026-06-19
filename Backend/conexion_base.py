from __future__ import annotations

"""Capa de persistencia para Oracle.

Expone la clase BaseOracle con operaciones de lectura y escritura en la
base de datos. La logica de negocio de cliente/vendedor debe residir en la
logica de dominio POO (Backend.modelo_poo), mientras que aqui solo se deben
manejar consultas, inserciones, actualizaciones y eliminaciones de datos.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import oracledb
try:
    oracledb.defaults.connect_timeout = 5
except AttributeError:
    pass
from dotenv import load_dotenv

from Backend.modelo_poo import Cliente, Persona, Producto, Venta, Vendedor, crear_usuario_desde_fila_usuario, crear_venta_por_item

RUTA_RAIZ = Path(__file__).resolve().parents[1]
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

COLUMNAS_BASE_PRODUCTO = ["id_producto", "nombre", "categoria", "precio_actual"]
COLUMNAS_OPCIONALES_PRODUCTO = ["marca", "stock", "precio_fabricacion", "fecha_caducidad", "imagen_url", "fecha_actualizacion"]


class BaseDatosNoEncontrada(Exception):
    pass


class ConflictoBaseDatosError(Exception):
    pass


class ValidacionBaseDatosError(Exception):
    pass


class BaseOracle:
    """Conexion y operaciones con Oracle Autonomous Database usando connection pool."""

    def __init__(self):
        self._columnas_producto: tuple[str, ...] | None = None
        self._pool = None
        self._dsn = self._resolver_dsn()

    def _resolver_dsn(self) -> str:
        ruta_tns = ubicacion_wallet / "tnsnames.ora"
        cadena_conexion = self._analizar_tnsnames(ruta_tns, DSN_DB)
        return cadena_conexion or DSN_DB

    def _analizar_tnsnames(self, ruta_tns: Path, nombre_dsn: str) -> str | None:
        if not ruta_tns.exists():
            return None

        try:
            contenido = ruta_tns.read_text(encoding="utf-8")
            lineas: list[str] = []
            for linea in contenido.splitlines():
                limpia = linea.strip()
                if limpia and not limpia.startswith("#"):
                    lineas.append(linea)
            texto_limpio = "\n".join(lineas)

            patron = re.compile(r"^\s*" + re.escape(nombre_dsn) + r"\s*=\s*\(", re.IGNORECASE | re.MULTILINE)
            coincidencia = patron.search(texto_limpio)
            if not coincidencia:
                return None

            inicio = coincidencia.end() - 1
            cuenta_paren = 0
            fin = inicio
            for indice in range(inicio, len(texto_limpio)):
                caracter = texto_limpio[indice]
                if caracter == "(":
                    cuenta_paren += 1
                elif caracter == ")":
                    cuenta_paren -= 1
                    if cuenta_paren == 0:
                        fin = indice + 1
                        break
            return " ".join(texto_limpio[inicio:fin].split())
        except Exception:
            return None

    def _obtener_pool(self):
        if self._pool is None:
            self._pool = oracledb.create_pool(
                user=USUARIO_DB,
                password=CONTRASENA_DB,
                dsn=self._dsn,
                config_dir=str(ubicacion_wallet),
                wallet_location=str(ubicacion_wallet),
                wallet_password=CONTRASENA_WALLET,
                min=1,
                max=10,
                increment=1,
                timeout=5,
            )
        return self._pool

    def conectar(self):
        """Obtiene conexion del pool. Al cerrar, se reusa automaticamente."""
        return self._obtener_pool().acquire()

    def obtener_columnas_producto(self) -> tuple[str, ...]:
        """Obtiene las columnas disponibles de la tabla productos."""
        if self._columnas_producto is None:
            with self.conectar() as conexion:
                with conexion.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'PRODUCTOS'")
                    filas = cursor.fetchall()
            self._columnas_producto = tuple(fila[0].lower() for fila in filas)
        return self._columnas_producto

    def construir_columnas_seleccion_producto(self) -> list[str]:
        """Construye la lista de columnas disponibles para SELECT."""
        disponibles = set(self.obtener_columnas_producto())
        columnas = [col for col in COLUMNAS_BASE_PRODUCTO if col in disponibles]
        for col in COLUMNAS_OPCIONALES_PRODUCTO:
            if col in disponibles:
                columnas.append(col)
        return columnas

    def consultar_producto_por_id(self, id_producto: str) -> Producto | None:
        """Busca un producto por su ID. Retorna None si no existe."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                columnas_seleccion = self.construir_columnas_seleccion_producto()
                cursor.execute(
                    f"SELECT {', '.join(columnas_seleccion)} FROM productos WHERE id_producto = :id_producto",
                    {"id_producto": id_producto},
                )
                fila = cursor.fetchone()
        if not fila:
            return None
        return Producto.desde_fila(fila, columnas_seleccion)

    def listar_productos(self, pagina: int, tamano_pagina: int) -> tuple[list[Producto], int]:
        """Lista todos los productos con paginacion."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                columnas_seleccion = self.construir_columnas_seleccion_producto()
                cursor.execute("SELECT COUNT(*) FROM productos")
                total_items = int(cursor.fetchone()[0] or 0)
                total_paginas = max(1, (total_items + tamano_pagina - 1) // tamano_pagina) if total_items else 1
                pagina_actual = min(pagina, total_paginas)
                offset = (pagina_actual - 1) * tamano_pagina
                cursor.execute(
                    f"SELECT {', '.join(columnas_seleccion)} FROM productos "
                    f"ORDER BY fecha_actualizacion DESC, nombre ASC OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY",
                    {"offset": offset, "tamano": tamano_pagina},
                )
                filas = cursor.fetchall()
        return [Producto.desde_fila(fila, columnas_seleccion) for fila in filas], total_items

    def listar_productos_vendedor(self, id_vendedor: str, pagina: int, tamano_pagina: int) -> tuple[list[Producto], int]:
        """Lista productos asignados a un vendedor especifico."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                columnas_seleccion = self.construir_columnas_seleccion_producto()
                columnas_sql = ", ".join(f"p.{col}" for col in columnas_seleccion)
                cursor.execute(
                    "SELECT COUNT(*) FROM productos p INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                    "WHERE pv.id_vendedor = :id_vendedor",
                    {"id_vendedor": id_vendedor},
                )
                total_items = int(cursor.fetchone()[0] or 0)
                total_paginas = max(1, (total_items + tamano_pagina - 1) // tamano_pagina) if total_items else 1
                pagina_actual = min(pagina, total_paginas)
                offset = (pagina_actual - 1) * tamano_pagina
                cursor.execute(
                    f"SELECT {columnas_sql} FROM productos p "
                    "INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                    "WHERE pv.id_vendedor = :id_vendedor "
                    "ORDER BY p.fecha_actualizacion DESC, p.nombre ASC OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY",
                    {"id_vendedor": id_vendedor, "offset": offset, "tamano": tamano_pagina},
                )
                filas = cursor.fetchall()
        return [Producto.desde_fila(fila, columnas_seleccion) for fila in filas], total_items

    def crear_producto(self, producto: Producto, id_vendedor: str | None = None) -> None:
        """Inserta un nuevo producto en la base de datos."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                columnas_seleccion = self.construir_columnas_seleccion_producto()
                columnas_insert = [col for col in [
                    "id_producto", "nombre", "marca", "categoria", "precio_actual",
                    "stock", "precio_fabricacion", "imagen_url"
                ] if col in columnas_seleccion]

                placeholders = ", ".join(f":{col}" for col in columnas_insert)
                valores = {col: getattr(producto, col, None) for col in columnas_insert}
                # Asegurar valores por defecto
                if "stock" in valores and valores.get("stock") is None:
                    valores["stock"] = 0
                if "nombre" in valores:
                    valores["nombre"] = producto.nombre

                cursor.execute(
                    f"INSERT INTO productos ({', '.join(columnas_insert)}) VALUES ({placeholders})",
                    valores,
                )

                if id_vendedor:
                    # Verificar si ya existe una asignacion
                    cursor.execute(
                        "SELECT COUNT(*) FROM producto_vendedor WHERE id_producto = :id_producto",
                        {"id_producto": producto.id_producto},
                    )
                    if int(cursor.fetchone()[0] or 0) == 0:
                        cursor.execute(
                            "INSERT INTO producto_vendedor (id_producto, id_vendedor) VALUES (:id_producto, :id_vendedor)",
                            {"id_producto": producto.id_producto, "id_vendedor": id_vendedor},
                        )
            conexion.commit()

    def actualizar_producto(self, id_producto: str, producto: Producto, campos_proporcionados: set[str]) -> None:
        """Actualiza un producto existente en la base de datos."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                columnas_seleccion = self.construir_columnas_seleccion_producto()
                # Mapeo de nombres de atributos a columnas de BD
                mapa_atributos = {
                    "id_producto": "id_producto",
                    "nombre": "nombre",
                    "marca": "marca",
                    "categoria": "categoria",
                    "precio_actual": "precio_actual",
                    "stock": "stock",
                    "precio_fabricacion": "precio_fabricacion",
                    "imagen_url": "imagen_url",
                }

                if campos_proporcionados:
                    # Usar solo los campos proporcionados en la solicitud
                    columnas_actualizar = []
                    for campo in campos_proporcionados:
                        columna = mapa_atributos.get(campo)
                        if columna and columna in columnas_seleccion:
                            columnas_actualizar.append(columna)
                else:
                    columnas_actualizar = [col for col in columnas_seleccion if col != "id_producto"]

                if not columnas_actualizar:
                    return

                sets = ", ".join(f"{col} = :{col}" for col in columnas_actualizar)
                valores = {}
                for col in columnas_actualizar:
                    if col == "stock":
                        valores[col] = producto.stock
                    elif col == "precio_actual":
                        valores[col] = producto.precio_actual
                    elif col == "precio_fabricacion":
                        valores[col] = producto.precio_fabricacion
                    elif col == "imagen_url":
                        valores[col] = producto.imagen_url
                    elif col == "marca":
                        valores[col] = producto.marca
                    elif col == "categoria":
                        valores[col] = producto.categoria
                    elif col == "nombre":
                        valores[col] = producto.nombre
                    elif col == "id_producto":
                        valores[col] = producto.id_producto

                valores["id_producto"] = id_producto
                cursor.execute(
                    f"UPDATE productos SET {sets} WHERE id_producto = :id_producto",
                    valores,
                )
            conexion.commit()

    def eliminar_producto(self, id_producto: str) -> None:
        """Elimina un producto por su ID."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM producto_vendedor WHERE id_producto = :id_producto",
                    {"id_producto": id_producto},
                )
                cursor.execute(
                    "DELETE FROM productos WHERE id_producto = :id_producto",
                    {"id_producto": id_producto},
                )
            conexion.commit()

    def obtener_vendedor_producto(self, id_producto: str) -> dict[str, object | None] | None:
        """Obtiene el vendedor asignado a un producto."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id_usuario, u.nombre, v.codigo_vendedor, v.especialidad "
                    "FROM producto_vendedor pv "
                    "JOIN vendedores v ON v.id_vendedor = pv.id_vendedor "
                    "JOIN usuarios u ON u.id_usuario = v.id_vendedor "
                    "WHERE pv.id_producto = :id_producto",
                    {"id_producto": id_producto},
                )
                fila = cursor.fetchone()
        if not fila:
            return None
        return {
            "id_vendedor": fila[0],
            "nombre": fila[1],
            "codigo_vendedor": fila[2],
            "especialidad": fila[3],
        }

    def obtener_historial_precios(self, id_producto: str, limite: int = 12) -> list[dict[str, object]]:
        """Obtiene el historial de precios de un producto."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT fecha, precio_registrado FROM historial_precios "
                    "WHERE id_producto = :id_producto "
                    "ORDER BY fecha DESC FETCH NEXT :limite ROWS ONLY",
                    {"id_producto": id_producto, "limite": limite},
                )
                filas = cursor.fetchall()
        return [{"fecha": fila[0].isoformat() if fila[0] else None, "precio": float(fila[1])} for fila in filas]



    def obtener_firma_catalogo_similitud(self) -> tuple[int, str]:
        """Obtiene la firma del catalogo (conteo + fecha) para cache de similitud."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT COUNT(*), MAX(fecha_actualizacion) FROM productos")
                fila = cursor.fetchone()
        return int(fila[0] or 0), str((fila[1] or datetime.utcnow()).isoformat())

    def cargar_catalogo_similitud(self, firma: tuple[int, str]) -> list[dict[str, object | None]]:
        """Carga todo el catalogo de productos para calculos de similitud."""
        columnas_seleccion = self.construir_columnas_seleccion_producto()
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    f"SELECT {', '.join(columnas_seleccion)} FROM productos ORDER BY nombre"
                )
                filas = cursor.fetchall()
        return [dict(zip(columnas_seleccion, fila)) for fila in filas]

    def obtener_persona_por_id(self, id_usuario: str) -> Persona | None:
        """Obtiene un usuario (Cliente o Vendedor) por su ID."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario FROM usuarios WHERE id_usuario = :id_usuario",
                    {"id_usuario": id_usuario},
                )
                fila = cursor.fetchone()
        if not fila:
            return None
        return crear_usuario_desde_fila_usuario(fila)

    def registrar_usuario(self, persona: Persona) -> None:
        """Registra un nuevo usuario (Cliente o Vendedor) en la base de datos."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE correo = :correo",
                    {"correo": persona.correo},
                )
                if int(cursor.fetchone()[0] or 0) > 0:
                    raise ConflictoBaseDatosError("El correo ya esta registrado.")

                datos = persona.a_fila()
                columnas_usuarios = {"id_usuario", "nombre", "telefono", "correo", "tipo_usuario", "password_hash"}
                datos_filtrados = {k: v for k, v in datos.items() if k in columnas_usuarios}
                cursor.execute(
                    "INSERT INTO usuarios (id_usuario, nombre, telefono, correo, tipo_usuario, password_hash) "
                    "VALUES (:id_usuario, :nombre, :telefono, :correo, :tipo_usuario, :password_hash)",
                    datos_filtrados,
                )

                if persona.tipo_usuario.strip().lower() == "vendedor":
                    cursor.execute(
                        "SELECT COUNT(*) FROM vendedores WHERE id_vendedor = :id_vendedor",
                        {"id_vendedor": persona.id},
                    )
                    if int(cursor.fetchone()[0] or 0) == 0:
                        import random
                        cursor.execute(
                            "INSERT INTO vendedores (id_vendedor, codigo_vendedor, especialidad, objetivo_ventas) "
                            "VALUES (:id_vendedor, :codigo_vendedor, :especialidad, :objetivo_ventas)",
                            {
                                "id_vendedor": persona.id,
                                "codigo_vendedor": persona.id[:20],
                                "especialidad": random.choice(["General", "Tecnologia", "Hogar", "Belleza"]),
                                "objetivo_ventas": 100000,
                            },
                        )
            conexion.commit()

    def actualizar_perfil_usuario(self, persona: Persona, contrasena_hash: str | None = None) -> None:
        """Actualiza el nombre y/o contrasena de un usuario."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE id_usuario = :id_usuario",
                    {"id_usuario": persona.id},
                )
                if int(cursor.fetchone()[0] or 0) == 0:
                    raise BaseDatosNoEncontrada("El usuario no existe.")

                if persona.nombre:
                    cursor.execute(
                        "UPDATE usuarios SET nombre = :nombre WHERE id_usuario = :id_usuario",
                        {"nombre": persona.nombre, "id_usuario": persona.id},
                    )
                if contrasena_hash:
                    cursor.execute(
                        "UPDATE usuarios SET password_hash = :password_hash WHERE id_usuario = :id_usuario",
                        {"password_hash": contrasena_hash, "id_usuario": persona.id},
                    )
            conexion.commit()

    def crear_compra(self, id_cliente: str, id_vendedor: str | None, items: list[dict[str, object]]) -> dict[str, object]:
        """Procesa una compra: crea cabecera, detalle, actualiza stock.

        Ejecuta toda la operacion dentro de una transaccion atomica.
        """
        id_vendedor_compra = id_vendedor.strip() if id_vendedor else None
        if not id_cliente:
            raise ValidacionBaseDatosError("El cliente es obligatorio.")
        if not items:
            raise ValidacionBaseDatosError("El carrito esta vacio.")

        id_venta = str(os.urandom(16).hex())
        monto_total = 0.0
        unidades_totales = 0
        items_ticket: list[dict[str, object]] = []
        cliente: Cliente | None = None
        vendedor: Vendedor | None = None

        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario FROM usuarios "
                    "WHERE id_usuario = :id_usuario AND tipo_usuario = 'Cliente'",
                    {"id_usuario": id_cliente},
                )
                fila_cliente = cursor.fetchone()
                if not fila_cliente:
                    raise BaseDatosNoEncontrada("El cliente no existe.")
                cliente = crear_usuario_desde_fila_usuario(fila_cliente)

                if id_vendedor_compra:
                    cursor.execute(
                        "SELECT u.id_usuario, u.nombre, u.telefono, u.correo, u.tipo_usuario "
                        "FROM usuarios u JOIN vendedores v ON v.id_vendedor = u.id_usuario "
                        "WHERE u.id_usuario = :id_usuario",
                        {"id_usuario": id_vendedor_compra},
                    )
                    fila_vendedor = cursor.fetchone()
                    if not fila_vendedor:
                        raise BaseDatosNoEncontrada("El vendedor no existe.")
                    vendedor = crear_usuario_desde_fila_usuario(fila_vendedor)

                cursor.execute(
                    "INSERT INTO ventas (id_venta, id_cliente, id_vendedor, monto_total, total_unidades) "
                    "VALUES (:id_venta, :id_cliente, :id_vendedor, :monto_total, :total_unidades)",
                    {
                        "id_venta": id_venta,
                        "id_cliente": id_cliente,
                        "id_vendedor": id_vendedor_compra,
                        "monto_total": 0,
                        "total_unidades": 0,
                    },
                )

                for item in items:
                    id_producto = str(item["id_producto"]).strip().upper()
                    cantidad = int(item["cantidad"])
                    if cantidad <= 0:
                        raise ValidacionBaseDatosError("La cantidad debe ser mayor a cero.")

                    cursor.execute(
                        "SELECT p.nombre, p.marca, p.precio_actual, p.stock, p.precio_fabricacion, pv.id_vendedor "
                        "FROM productos p "
                        "LEFT JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                        "WHERE p.id_producto = :id_producto FOR UPDATE",
                        {"id_producto": id_producto},
                    )
                    fila_producto = cursor.fetchone()
                    if not fila_producto:
                        raise BaseDatosNoEncontrada(f"El producto {id_producto} no existe.")

                    nombre_producto, marca_producto, precio_actual, stock_actual, costo_producto, id_vendedor_producto = fila_producto
                    stock_actual = int(stock_actual or 0)
                    precio_valor = float(precio_actual or 0)
                    costo_valor = float(costo_producto) if costo_producto is not None else None

                    if vendedor is None and id_vendedor_compra is None and id_vendedor_producto:
                        id_vendedor_compra = id_vendedor_producto
                        cursor.execute(
                            "SELECT u.id_usuario, u.nombre, u.telefono, u.correo, u.tipo_usuario "
                            "FROM usuarios u JOIN vendedores v ON v.id_vendedor = u.id_usuario "
                            "WHERE u.id_usuario = :id_usuario",
                            {"id_usuario": id_vendedor_compra},
                        )
                        fila_vendedor = cursor.fetchone()
                        if fila_vendedor:
                            vendedor = crear_usuario_desde_fila_usuario(fila_vendedor)

                    venta_obj, detalle, stock_restante, subtotal, ganancia = crear_venta_por_item(
                        cliente,
                        vendedor,
                        id_venta,
                        id_producto,
                        nombre_producto,
                        marca_producto,
                        precio_valor,
                        stock_actual,
                        costo_valor,
                        cantidad,
                        datetime.utcnow(),
                    )

                    cursor.execute(
                        "UPDATE productos SET stock = :stock, fecha_actualizacion = CURRENT_TIMESTAMP "
                        "WHERE id_producto = :id_producto",
                        {"stock": stock_restante, "id_producto": id_producto},
                    )

                    monto_total += subtotal
                    unidades_totales += cantidad
                    items_ticket.append(detalle)

                    cursor.execute(
                        "INSERT INTO venta_detalle (id_venta, id_producto, cantidad, precio_unitario, costo_unitario, subtotal, margen_unitario) "
                        "VALUES (:id_venta, :id_producto, :cantidad, :precio_unitario, :costo_unitario, :subtotal, :margen_unitario)",
                        {
                            "id_venta": id_venta,
                            "id_producto": id_producto,
                            "cantidad": cantidad,
                            "precio_unitario": precio_valor,
                            "costo_unitario": costo_valor,
                            "subtotal": subtotal,
                            "margen_unitario": round(ganancia / cantidad, 2) if ganancia is not None else None,
                        },
                    )

                cursor.execute(
                    "UPDATE ventas SET monto_total = :monto_total, total_unidades = :total_unidades WHERE id_venta = :id_venta",
                    {"monto_total": round(monto_total, 2), "total_unidades": unidades_totales, "id_venta": id_venta},
                )
                conexion.commit()

        return {
            "id_venta": id_venta,
            "id_cliente": id_cliente,
            "id_vendedor": id_vendedor_compra,
            "fecha_venta": datetime.utcnow().isoformat(),
            "monto_total": round(monto_total, 2),
            "total_unidades": unidades_totales,
            "items": items_ticket,
        }

    def listar_compras_cliente(self, id_cliente: str, fecha_inicio: datetime | None, pagina: int, tamano_pagina: int) -> tuple[list[dict[str, object | None]], int]:
        """Obtiene el historial de compras de un cliente con paginacion."""
        filtros = ["v.id_cliente = :id_cliente"]
        parametros: dict[str, object] = {"id_cliente": id_cliente}
        if fecha_inicio:
            filtros.append("v.fecha_venta >= :fecha_inicio")
            parametros["fecha_inicio"] = fecha_inicio

        clausula_where = " WHERE " + " AND ".join(filtros)
        consulta_conteo = f"SELECT COUNT(DISTINCT v.id_venta) FROM ventas v{clausula_where}"
        consulta_lista = (
            "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades "
            f"FROM ventas v{clausula_where} "
            "ORDER BY v.fecha_venta DESC, v.id_venta DESC OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY"
        )

        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(consulta_conteo, parametros)
                total_items = int(cursor.fetchone()[0] or 0)
                total_paginas = max(1, (total_items + tamano_pagina - 1) // tamano_pagina) if total_items else 1
                pagina_actual = min(pagina, total_paginas)
                offset = (pagina_actual - 1) * tamano_pagina
                cursor.execute(
                    consulta_lista,
                    {**parametros, "offset": offset, "tamano": tamano_pagina},
                )
                filas = cursor.fetchall()
                ids_ventas = [fila[0] for fila in filas]
                detalles_por_venta: dict[object, list[dict[str, object]]] = {}
                if ids_ventas:
                    placeholders = ", ".join(f":venta_{indice}" for indice in range(len(ids_ventas)))
                    cursor.execute(
                        "SELECT d.id_venta, d.id_producto, p.nombre, d.cantidad "
                        "FROM venta_detalle d "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        f"WHERE d.id_venta IN ({placeholders}) "
                        "ORDER BY d.id_venta DESC, d.id_producto ASC",
                        {f"venta_{indice}": id_venta for indice, id_venta in enumerate(ids_ventas)},
                    )
                    for id_venta, id_producto, nombre_producto, cantidad in cursor.fetchall():
                        detalles_por_venta.setdefault(id_venta, []).append(
                            {
                                "id_producto": id_producto,
                                "nombre": str(nombre_producto or "Producto sin nombre"),
                                "cantidad": int(cantidad) if cantidad is not None else 0,
                            }
                        )
        items = []
        for fila in filas:
            id_venta = fila[0]
            productos = detalles_por_venta.get(id_venta, [])
            resumen = ", ".join(f"{producto['nombre']} x{producto['cantidad']}" for producto in productos[:3])
            if len(productos) > 3:
                resumen = f"{resumen}, +{len(productos) - 3} mas" if resumen else f"+{len(productos) - 3} mas"
            items.append(
                {
                    "id_venta": id_venta,
                    "fecha_venta": fila[1].isoformat() if fila[1] else None,
                    "monto_total": float(fila[2]) if fila[2] is not None else 0.0,
                    "total_unidades": int(fila[3]) if fila[3] is not None else 0,
                    "numero_pedido": str(id_venta),
                    "resumen": resumen,
                    "productos": productos,
                }
            )
        return items, total_items

    def listar_compras_vendedor(self, id_vendedor: str, fecha_inicio: datetime | None, pagina: int, tamano_pagina: int) -> tuple[list[dict[str, object | None]], int]:
        """Obtiene las ventas realizadas por un vendedor con paginacion."""
        filtros = ["v.id_vendedor = :id_vendedor"]
        parametros: dict[str, object] = {"id_vendedor": id_vendedor}
        if fecha_inicio:
            filtros.append("v.fecha_venta >= :fecha_inicio")
            parametros["fecha_inicio"] = fecha_inicio

        clausula_where = " WHERE " + " AND ".join(filtros)
        consulta_conteo = f"SELECT COUNT(DISTINCT v.id_venta) FROM ventas v{clausula_where}"
        consulta_lista = (
            "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades, u.id_usuario, u.nombre "
            f"FROM ventas v JOIN usuarios u ON u.id_usuario = v.id_cliente{clausula_where} "
            "ORDER BY v.fecha_venta DESC, v.id_venta DESC OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY"
        )

        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(consulta_conteo, parametros)
                total_items = int(cursor.fetchone()[0] or 0)
                total_paginas = max(1, (total_items + tamano_pagina - 1) // tamano_pagina) if total_items else 1
                pagina_actual = min(pagina, total_paginas)
                offset = (pagina_actual - 1) * tamano_pagina
                cursor.execute(
                    consulta_lista,
                    {**parametros, "offset": offset, "tamano": tamano_pagina},
                )
                filas = cursor.fetchall()
                ids_ventas = [fila[0] for fila in filas]
                detalles_por_venta: dict[object, list[dict[str, object]]] = {}
                if ids_ventas:
                    placeholders = ", ".join(f":venta_{indice}" for indice in range(len(ids_ventas)))
                    cursor.execute(
                        "SELECT d.id_venta, d.id_producto, p.nombre, d.cantidad "
                        "FROM venta_detalle d "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        f"WHERE d.id_venta IN ({placeholders}) "
                        "ORDER BY d.id_venta DESC, d.id_producto ASC",
                        {f"venta_{indice}": id_venta for indice, id_venta in enumerate(ids_ventas)},
                    )
                    for id_venta, id_producto, nombre_producto, cantidad in cursor.fetchall():
                        detalles_por_venta.setdefault(id_venta, []).append(
                            {
                                "id_producto": id_producto,
                                "nombre": str(nombre_producto or "Producto sin nombre"),
                                "cantidad": int(cantidad) if cantidad is not None else 0,
                            }
                        )
        items = []
        for fila in filas:
            id_venta = fila[0]
            productos = detalles_por_venta.get(id_venta, [])
            resumen = ", ".join(f"{producto['nombre']} x{producto['cantidad']}" for producto in productos[:3])
            if len(productos) > 3:
                resumen = f"{resumen}, +{len(productos) - 3} mas" if resumen else f"+{len(productos) - 3} mas"
            items.append(
                {
                    "id_venta": id_venta,
                    "fecha_venta": fila[1].isoformat() if fila[1] else None,
                    "monto_total": float(fila[2]) if fila[2] is not None else 0.0,
                    "total_unidades": int(fila[3]) if fila[3] is not None else 0,
                    "cliente": {
                        "id_cliente": fila[4],
                        "nombre": fila[5],
                    },
                    "numero_pedido": str(id_venta),
                    "resumen": resumen,
                    "productos": productos,
                }
            )
        return items, total_items

    def obtener_ticket_compra_cliente(self, id_venta: str) -> dict[str, object | None]:
        """Obtiene el detalle completo de una venta (ticket)."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades, "
                    "u.id_usuario, u.nombre, v.id_vendedor, uv.nombre AS vendedor_nombre "
                    "FROM ventas v "
                    "JOIN usuarios u ON u.id_usuario = v.id_cliente "
                    "LEFT JOIN vendedores vv ON vv.id_vendedor = v.id_vendedor "
                    "LEFT JOIN usuarios uv ON uv.id_usuario = vv.id_vendedor "
                    "WHERE v.id_venta = :id_venta",
                    {"id_venta": id_venta},
                )
                cabecera = cursor.fetchone()
                if not cabecera:
                    raise BaseDatosNoEncontrada("La venta no existe.")
                cursor.execute(
                    "SELECT d.id_producto, p.nombre, p.marca, d.cantidad, d.precio_unitario, d.subtotal, d.costo_unitario, d.margen_unitario "
                    "FROM venta_detalle d "
                    "JOIN productos p ON p.id_producto = d.id_producto "
                    "WHERE d.id_venta = :id_venta",
                    {"id_venta": id_venta},
                )
                detalles = cursor.fetchall()
        return {
            "id_venta": cabecera[0],
            "fecha_venta": cabecera[1].isoformat() if cabecera[1] else None,
            "monto_total": float(cabecera[2]) if cabecera[2] is not None else 0.0,
            "total_unidades": int(cabecera[3]) if cabecera[3] is not None else 0,
            "cliente": {
                "id_cliente": cabecera[4],
                "nombre": cabecera[5],
            },
            "vendedor": {
                "id_vendedor": cabecera[6],
                "nombre": cabecera[7],
            },
            "items": [
                {
                    "id_producto": fila[0],
                    "nombre": fila[1],
                    "marca": fila[2],
                    "cantidad": int(fila[3]) if fila[3] is not None else 0,
                    "precio_unitario": float(fila[4]) if fila[4] is not None else 0.0,
                    "subtotal": float(fila[5]) if fila[5] is not None else 0.0,
                    "costo_unitario": float(fila[6]) if fila[6] is not None else None,
                    "margen_unitario": float(fila[7]) if fila[7] is not None else None,
                }
                for fila in detalles
            ],
        }

    def obtener_indicadores_financieros(self, id_vendedor=None) -> dict[str, object]:
        """Obtiene indicadores financieros agregados del sistema."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                if id_vendedor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM productos p "
                        "INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                        "WHERE pv.id_vendedor = :id_vendedor",
                        {"id_vendedor": id_vendedor},
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM productos")
                total_productos = int(cursor.fetchone()[0] or 0)

                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario = 'Vendedor'")
                total_vendedores = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario = 'Cliente'")
                total_clientes = int(cursor.fetchone()[0] or 0)

                if id_vendedor:
                    cursor.execute(
                        "SELECT COUNT(*), COALESCE(SUM(monto_total), 0) FROM ventas "
                        "WHERE id_vendedor = :id_vendedor",
                        {"id_vendedor": id_vendedor},
                    )
                else:
                    cursor.execute("SELECT COUNT(*), COALESCE(SUM(monto_total), 0) FROM ventas")
                fila_ventas = cursor.fetchone()
                total_ventas = int(fila_ventas[0] or 0)
                ingresos = float(fila_ventas[1] or 0)

                if id_vendedor:
                    cursor.execute(
                        "SELECT COALESCE(SUM(d.costo_unitario * d.cantidad), 0) "
                        "FROM venta_detalle d "
                        "INNER JOIN ventas v ON v.id_venta = d.id_venta "
                        "WHERE v.id_vendedor = :id_vendedor",
                        {"id_vendedor": id_vendedor},
                    )
                else:
                    cursor.execute("SELECT COALESCE(SUM(d.costo_unitario * d.cantidad), 0) FROM venta_detalle d")
                costo_total = float(cursor.fetchone()[0] or 0)

                if id_vendedor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM productos p "
                        "INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                        "WHERE pv.id_vendedor = :id_vendedor AND p.stock <= 10",
                        {"id_vendedor": id_vendedor},
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM productos WHERE stock <= 10")
                stock_bajo = int(cursor.fetchone()[0] or 0)

                if id_vendedor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM productos p "
                        "INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                        "WHERE pv.id_vendedor = :id_vendedor AND p.fecha_actualizacion < (CURRENT_DATE - 30)",
                        {"id_vendedor": id_vendedor},
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM productos WHERE fecha_actualizacion < (CURRENT_DATE - 30)")
                estancados = int(cursor.fetchone()[0] or 0)

        return {
            "total_productos": total_productos,
            "total_vendedores": total_vendedores,
            "total_clientes": total_clientes,
            "total_ventas": total_ventas,
            "ingresos_totales": ingresos,
            "costos_totales": costo_total,
            "productos_stock_bajo": stock_bajo,
            "productos_estancados": estancados,
        }

    def obtener_ventas_mensuales(self, id_vendedor=None, meses=6):
        """Obtiene ventas mensuales agregadas de los ultimos N meses."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                filtros = [f"v.fecha_venta >= ADD_MONTHS(CURRENT_DATE, -{meses})"]
                params = {}
                if id_vendedor:
                    filtros.append("v.id_vendedor = :id_vendedor")
                    params["id_vendedor"] = id_vendedor
                where = " AND ".join(filtros)
                cursor.execute(
                    "SELECT EXTRACT(YEAR FROM v.fecha_venta) AS \"anio\", "
                    "EXTRACT(MONTH FROM v.fecha_venta) AS \"mes\", "
                    "TO_CHAR(v.fecha_venta, 'MON') AS \"mes_nombre\", "
                    "SUM(v.monto_total) AS \"ingresos\", "
                    "COUNT(*) AS \"total_ventas\", "
                    "COALESCE(SUM(d.costo_unitario * d.cantidad), 0) AS \"costos\" "
                    "FROM ventas v "
                    "LEFT JOIN venta_detalle d ON d.id_venta = v.id_venta "
                    f"WHERE {where} "
                    "GROUP BY EXTRACT(YEAR FROM v.fecha_venta), EXTRACT(MONTH FROM v.fecha_venta), "
                    "TO_CHAR(v.fecha_venta, 'MON') "
                    "ORDER BY \"anio\" DESC, \"mes\" DESC",
                    params,
                )
                filas = cursor.fetchall()

        meses_map = {
            "ENE": "Ene", "FEB": "Feb", "MAR": "Mar", "ABR": "Abr",
            "MAY": "May", "JUN": "Jun", "JUL": "Jul", "AGO": "Ago",
            "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DIC": "Dic",
        }

        resultados = []
        for fila in filas:
            anio, mes, mes_nombre, ingresos, total_ventas, costos = fila
            mes_corto = meses_map.get(mes_nombre.strip().upper()[:3], mes_nombre.strip()[:3])
            etiqueta = f"{mes_corto} {anio}"
            ganancia = float(ingresos or 0) - float(costos or 0)
            resultados.append({
                "anio": int(anio),
                "mes": int(mes),
                "etiqueta": etiqueta,
                "ingresos": float(ingresos or 0),
                "costos": float(costos or 0),
                "ganancia": round(ganancia, 2),
                "ventas": int(total_ventas or 0),
            })
        return resultados

    def obtener_top_productos_vendedor(self, id_vendedor=None, limite=10):
        """Obtiene los productos mas vendidos por ingresos totales."""
        with self.conectar() as conexion:
            with conexion.cursor() as cursor:
                if id_vendedor:
                    cursor.execute(
                        "SELECT d.id_producto AS \"id_producto\", p.nombre AS \"nombre\", "
                        "SUM(d.cantidad) AS \"cantidad_vendida\", "
                        "SUM(d.subtotal) AS \"ingresos_totales\" "
                        "FROM venta_detalle d "
                        "INNER JOIN ventas v ON v.id_venta = d.id_venta "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        "WHERE v.id_vendedor = :id_vendedor "
                        "GROUP BY d.id_producto, p.nombre "
                        "ORDER BY \"cantidad_vendida\" DESC "
                        "FETCH NEXT :limite ROWS ONLY",
                        {"id_vendedor": id_vendedor, "limite": limite},
                    )
                else:
                    cursor.execute(
                        "SELECT d.id_producto AS \"id_producto\", p.nombre AS \"nombre\", "
                        "SUM(d.cantidad) AS \"cantidad_vendida\", "
                        "SUM(d.subtotal) AS \"ingresos_totales\" "
                        "FROM venta_detalle d "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        "GROUP BY d.id_producto, p.nombre "
                        "ORDER BY \"cantidad_vendida\" DESC "
                        "FETCH NEXT :limite ROWS ONLY",
                        {"limite": limite},
                    )
                filas = cursor.fetchall()
        return [
            {
                "id_producto": fila[0],
                "nombre": fila[1],
                "cantidad_vendida": int(fila[2]) if fila[2] is not None else 0,
                "ingresos_totales": float(fila[3]) if fila[3] is not None else 0.0,
            }
            for fila in filas
        ]


db = BaseOracle()
