from __future__ import annotations

"""Capa de persistencia para Oracle.

Este módulo expone la clase OracleDB con operaciones de lectura y escritura en la
base de datos. La lógica de negocio de cliente/vendedor debe residir en la
lógica de dominio POO (`Backend.modelo_poo`), mientras que aquí solo se deben
manejar consultas, inserciones, actualizaciones y eliminaciones de datos.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import oracledb  # type: ignore[import-not-found]
from dotenv import load_dotenv

from Backend.modelo_poo import Cliente, Persona, Producto, Venta, Vendedor, crear_usuario_desde_fila_usuario, crear_venta_por_item

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_PATH = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

if not WALLET_PATH:
    _wallet_root = ROOT_DIR / "wallet"
    if _wallet_root.is_dir():
        for _child in sorted(_wallet_root.iterdir()):
            if _child.is_dir() and (_child / "tnsnames.ora").is_file():
                WALLET_PATH = str(_child)
                break

if not WALLET_PATH:
    raise RuntimeError("WALLET_PATH no definido en .env")

wallet_location = Path(WALLET_PATH)
if not wallet_location.is_absolute():
    wallet_location = (ROOT_DIR / wallet_location).resolve()

BASE_PRODUCT_COLUMNS = ["id_producto", "nombre", "categoria", "precio_actual"]
OPTIONAL_PRODUCT_COLUMNS = ["marca", "stock", "precio_fabricacion", "fecha_caducidad", "imagen_url", "fecha_actualizacion"]


class DatabaseNotFoundError(Exception):
    pass


class DatabaseConflictError(Exception):
    pass


class DatabaseValidationError(Exception):
    pass


class OracleDB:
    def __init__(self):
        self._product_columns: tuple[str, ...] | None = None

    def _parse_tnsnames(self, tnsnames_path: Path, dsn_name: str) -> str | None:
        if not tnsnames_path.exists():
            return None

        try:
            content = tnsnames_path.read_text(encoding="utf-8")
            lines: list[str] = []
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(line)
            clean_content = "\n".join(lines)

            pattern = re.compile(r"^\s*" + re.escape(dsn_name) + r"\s*=\s*\(", re.IGNORECASE | re.MULTILINE)
            match = pattern.search(clean_content)
            if not match:
                return None

            start_pos = match.end() - 1
            paren_count = 0
            end_pos = start_pos
            for index in range(start_pos, len(clean_content)):
                char = clean_content[index]
                if char == "(":
                    paren_count += 1
                elif char == ")":
                    paren_count -= 1
                    if paren_count == 0:
                        end_pos = index + 1
                        break
            return " ".join(clean_content[start_pos:end_pos].split())
        except Exception:
            return None

    def connect(self):
        tns_path = wallet_location / "tnsnames.ora"
        connection_string = self._parse_tnsnames(tns_path, DB_DSN)
        if connection_string:
            return oracledb.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dsn=connection_string,
                config_dir=str(wallet_location),
                wallet_location=str(wallet_location),
                wallet_password=WALLET_PASSWORD,
            )

        return oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            config_dir=str(wallet_location),
            wallet_location=str(wallet_location),
            wallet_password=WALLET_PASSWORD,
        )

    def _fetch_product_columns(self) -> tuple[str, ...]:
        if self._product_columns is None:
            with self.connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'PRODUCTOS'")
                    rows = cursor.fetchall()
            self._product_columns = tuple(row[0].lower() for row in rows)
        return self._product_columns

    def _build_product_select_columns(self) -> list[str]:
        available = set(self._fetch_product_columns())
        columns = [column for column in BASE_PRODUCT_COLUMNS if column in available]
        for column in OPTIONAL_PRODUCT_COLUMNS:
            if column in available:
                columns.append(column)
        return columns

    def fetch_producto_by_id(self, product_id: str) -> Producto | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                selected_columns = self._build_product_select_columns()
                cursor.execute(
                    f"SELECT {', '.join(selected_columns)} FROM productos WHERE id_producto = :id_producto",
                    {"id_producto": product_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        return Producto.from_row(row, selected_columns)

    def list_productos(self, page: int, page_size: int) -> tuple[list[Producto], int]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                selected_columns = self._build_product_select_columns()
                cursor.execute("SELECT COUNT(*) FROM productos")
                total_items = int(cursor.fetchone()[0] or 0)
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
                current_page = min(page, total_pages)
                offset = (current_page - 1) * page_size
                cursor.execute(
                    f"SELECT {', '.join(selected_columns)} FROM productos "
                    f"ORDER BY fecha_actualizacion DESC, nombre ASC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY",
                    {"offset": offset, "page_size": page_size},
                )
                rows = cursor.fetchall()
        return [Producto.from_row(row, selected_columns) for row in rows], total_items

    def list_vendor_products(self, vendor_id: str, page: int, page_size: int) -> tuple[list[Producto], int]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                selected_columns = self._build_product_select_columns()
                selected_columns_sql = ", ".join(f"p.{column}" for column in selected_columns)
                cursor.execute(
                    "SELECT COUNT(*) FROM productos p INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                    "WHERE pv.id_vendedor = :vendedor_id",
                    {"vendedor_id": vendor_id},
                )
                total_items = int(cursor.fetchone()[0] or 0)
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
                current_page = min(page, total_pages)
                offset = (current_page - 1) * page_size
                cursor.execute(
                    f"SELECT {selected_columns_sql} FROM productos p "
                    "INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                    "WHERE pv.id_vendedor = :vendedor_id "
                    "ORDER BY p.fecha_actualizacion DESC, p.nombre ASC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY",
                    {"vendedor_id": vendor_id, "offset": offset, "page_size": page_size},
                )
                rows = cursor.fetchall()
        return [Producto.from_row(row, selected_columns) for row in rows], total_items

    def create_producto(self, producto: Producto, vendor_id: str | None = None) -> None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                selected_columns = self._build_product_select_columns()
                insert_columns = [column for column in [
                    "id_producto", "nombre", "marca", "categoria", "precio_actual", "stock", "precio_fabricacion", "fecha_caducidad", "imagen_url"
                ] if column in selected_columns]
                values = {column: getattr(producto, column if column != "precio_actual" else "precio_actual") for column in insert_columns}
                cursor.execute(
                    f"INSERT INTO productos ({', '.join(insert_columns)}) VALUES ({', '.join(f':{column}' for column in insert_columns)})",
                    values,
                )
                if vendor_id:
                    cursor.execute(
                        "SELECT id_vendedor FROM vendedores WHERE id_vendedor = :id_vendedor",
                        {"id_vendedor": vendor_id},
                    )
                    if not cursor.fetchone():
                        raise DatabaseNotFoundError("El vendedor no existe.")
                    cursor.execute(
                        "INSERT INTO producto_vendedor (id_producto, id_vendedor) VALUES (:id_producto, :id_vendedor)",
                        {"id_producto": producto.id_producto, "id_vendedor": vendor_id},
                    )
                connection.commit()

    def update_producto(self, product_id: str, producto: Producto, provided_fields: set[str] | None = None) -> None:
        available = set(self._fetch_product_columns())
        assignments: list[str] = []
        values: dict[str, object | None] = {"id_producto": product_id}
        updates = {
            "nombre": producto.nombre,
            "marca": producto.marca,
            "categoria": producto.categoria,
            "precio_actual": producto.precio_actual,
            "stock": producto.stock,
            "precio_fabricacion": producto.precio_fabricacion,
            "fecha_caducidad": producto.fecha_caducidad,
            "imagen_url": producto.imagen_url,
        }
        for column, value in updates.items():
            if column in available:
                if provided_fields and column in provided_fields and value is None:
                    assignments.append(f"{column} = NULL")
                elif value is not None:
                    assignments.append(f"{column} = :{column}")
                    values[column] = value
        if "fecha_actualizacion" in available:
            assignments.append("fecha_actualizacion = CURRENT_TIMESTAMP")
        if not assignments:
            raise DatabaseValidationError("La tabla de productos no permite actualizaciones en este momento.")
        sql = f"UPDATE productos SET {', '.join(assignments)} WHERE id_producto = :id_producto"
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                if cursor.rowcount == 0:
                    raise DatabaseNotFoundError("El producto no existe.")
                connection.commit()

    def delete_producto(self, product_id: str) -> None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM productos WHERE id_producto = :id_producto", {"id_producto": product_id})
                if cursor.rowcount == 0:
                    raise DatabaseNotFoundError("El producto no existe.")
                connection.commit()

    def fetch_product_vendor(self, product_id: str) -> dict[str, object | None] | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id_usuario, u.nombre, u.telefono, u.correo, u.tipo_usuario, "
                    "v.codigo_vendedor, v.especialidad "
                    "FROM producto_vendedor pv "
                    "JOIN vendedores v ON v.id_vendedor = pv.id_vendedor "
                    "JOIN usuarios u ON u.id_usuario = v.id_vendedor "
                    "WHERE pv.id_producto = :id_producto",
                    {"id_producto": product_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        vendedor = Vendedor.desde_fila_vendedor(
            row[:5],
            codigo_vendedor=row[5],
            especialidad=row[6],
        )
        return vendedor.to_vendor_dict()

    def fetch_price_history(self, product_id: str, limit: int = 12) -> list[dict[str, object | None]]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fecha, precio_registrado FROM ("
                    "  SELECT fecha, precio_registrado FROM historial_precios "
                    "  WHERE id_producto = :id_producto ORDER BY fecha DESC"
                    ") WHERE ROWNUM <= :limit",
                    {"id_producto": product_id, "limit": limit},
                )
                rows = cursor.fetchall()
        return [
            {
                "fecha": fecha.isoformat() if fecha else None,
                "precio": float(precio) if precio is not None else None,
            }
            for fecha, precio in reversed(rows)
        ]

    def fetch_competition_average(self, product_id: str) -> float | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT AVG(precio_competencia_promedio) FROM competencia_mercado WHERE id_producto = :id_producto",
                    {"id_producto": product_id},
                )
                row = cursor.fetchone()
        if not row or row[0] is None:
            return None
        return float(row[0])

    def fetch_similarity_catalog_signature(self) -> tuple[int, str]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*), MAX(fecha_actualizacion) FROM productos")
                row = cursor.fetchone()
        total_items = int(row[0] or 0) if row else 0
        latest_update = row[1].isoformat() if row and row[1] else ""
        return total_items, latest_update

    def load_similarity_catalog(self, signature: tuple[int, str]) -> list[dict[str, object | None]]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                catalog_columns = [
                    "id_producto", "nombre", "marca", "categoria",
                    "precio_actual", "stock", "precio_fabricacion", "fecha_actualizacion",
                ]
                cursor.execute(
                    "SELECT id_producto, nombre, marca, categoria, precio_actual, stock, precio_fabricacion, fecha_actualizacion FROM productos ORDER BY nombre ASC"
                )
                rows = cursor.fetchall()
        return [Producto.from_row(row, catalog_columns).to_dict() for row in rows]

    def fetch_persona_by_id(self, user_id: str) -> Persona | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario FROM usuarios WHERE id_usuario = :id_usuario",
                    {"id_usuario": user_id},
                )
                row = cursor.fetchone()
        if not row:
            return None
        return Persona.from_row(row)

    def register_user(self, persona: Persona) -> Persona:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_usuario FROM usuarios WHERE correo = :correo AND tipo_usuario = :tipo_usuario",
                    {"correo": persona.correo, "tipo_usuario": persona.tipo_usuario},
                )
                if cursor.fetchone():
                    raise DatabaseConflictError("El correo ya esta registrado para ese rol.")
                persona_values = persona.to_row()
                allowed_keys = {"id_usuario", "nombre", "telefono", "correo", "tipo_usuario", "password_hash"}
                insert_values = {key: persona_values[key] for key in allowed_keys if key in persona_values}
                cursor.execute(
                    "INSERT INTO usuarios (id_usuario, nombre, telefono, correo, tipo_usuario, password_hash) "
                    "VALUES (:id_usuario, :nombre, :telefono, :correo, :tipo_usuario, :password_hash)",
                    insert_values,
                )
                if persona.tipo_usuario == "Vendedor":
                    cursor.execute(
                        "INSERT INTO vendedores (id_vendedor, codigo_vendedor, especialidad, objetivo_ventas) "
                        "VALUES (:id_vendedor, :codigo_vendedor, :especialidad, :objetivo_ventas)",
                        {
                            "id_vendedor": persona.id,
                            "codigo_vendedor": getattr(persona, "codigo_vendedor", persona.id),
                            "especialidad": getattr(persona, "especialidad", None),
                            "objetivo_ventas": getattr(persona, "objetivo_ventas", None) or 0,
                        },
                    )
                connection.commit()
        return persona

    def update_user_profile(self, persona: Persona, password_hash: str | None = None) -> Persona:
        update_parts: list[str] = []
        params: dict[str, object | None] = {"id_usuario": persona.id}
        if persona.nombre:
            update_parts.append("nombre = :nombre")
            params["nombre"] = persona.nombre
        if password_hash is not None:
            update_parts.append("password_hash = :password_hash")
            params["password_hash"] = password_hash
        if not update_parts:
            raise DatabaseValidationError("No hay cambios para actualizar.")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = :id_usuario", {"id_usuario": persona.id})
                if not cursor.fetchone():
                    raise DatabaseNotFoundError("El usuario no existe.")
                cursor.execute(f"UPDATE usuarios SET {', '.join(update_parts)} WHERE id_usuario = :id_usuario", params)
                connection.commit()
        return persona

    def create_purchase(self, client_id: str, sale_vendor_id: str | None, items: list[dict[str, object]]) -> dict[str, object]:
        client_id = client_id.strip()
        vendor_id = sale_vendor_id.strip() if sale_vendor_id else None
        if not client_id:
            raise DatabaseValidationError("El cliente es obligatorio.")
        if not items:
            raise DatabaseValidationError("El carrito esta vacio.")

        sale_id = str(os.urandom(16).hex())
        total_amount = 0.0
        total_units = 0
        ticket_items: list[dict[str, object]] = []
        cliente: Cliente | None = None
        vendedor: Vendedor | None = None

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario FROM usuarios WHERE id_usuario = :id_usuario AND tipo_usuario = 'Cliente'",
                    {"id_usuario": client_id},
                )
                client_row = cursor.fetchone()
                if not client_row:
                    raise DatabaseNotFoundError("El cliente no existe.")
                cliente = crear_usuario_desde_fila_usuario(client_row)

                if vendor_id:
                    cursor.execute(
                        "SELECT u.id_usuario, u.nombre, u.telefono, u.correo, u.tipo_usuario "
                        "FROM usuarios u JOIN vendedores v ON v.id_vendedor = u.id_usuario "
                        "WHERE u.id_usuario = :id_usuario",
                        {"id_usuario": vendor_id},
                    )
                    vendor_row = cursor.fetchone()
                    if not vendor_row:
                        raise DatabaseNotFoundError("El vendedor no existe.")
                    vendedor = crear_usuario_desde_fila_usuario(vendor_row)

                cursor.execute(
                    "INSERT INTO ventas (id_venta, id_cliente, id_vendedor, monto_total, total_unidades) "
                    "VALUES (:id_venta, :id_cliente, :id_vendedor, :monto_total, :total_unidades)",
                    {"id_venta": sale_id, "id_cliente": client_id, "id_vendedor": vendor_id, "monto_total": 0, "total_unidades": 0},
                )

                for item in items:
                    product_id = str(item["id_producto"]).strip().upper()
                    quantity = int(item["cantidad"])
                    if quantity <= 0:
                        raise DatabaseValidationError("La cantidad debe ser mayor a cero.")

                    cursor.execute(
                        "SELECT p.nombre, p.marca, p.precio_actual, p.stock, p.precio_fabricacion, pv.id_vendedor "
                        "FROM productos p "
                        "LEFT JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
                        "WHERE p.id_producto = :id_producto FOR UPDATE",
                        {"id_producto": product_id},
                    )
                    product_row = cursor.fetchone()
                    if not product_row:
                        raise DatabaseNotFoundError(f"El producto {product_id} no existe.")

                    product_name, product_brand, price_actual, current_stock, product_cost, product_vendor_id = product_row
                    current_stock = int(current_stock or 0)
                    price_value = float(price_actual or 0)
                    cost_value = float(product_cost) if product_cost is not None else None

                    if vendedor is None and vendor_id is None and product_vendor_id:
                        vendor_id = product_vendor_id
                        cursor.execute(
                            "SELECT u.id_usuario, u.nombre, u.telefono, u.correo, u.tipo_usuario "
                            "FROM usuarios u JOIN vendedores v ON v.id_vendedor = u.id_usuario "
                            "WHERE u.id_usuario = :id_usuario",
                            {"id_usuario": vendor_id},
                        )
                        vendor_row = cursor.fetchone()
                        if vendor_row:
                            vendedor = crear_usuario_desde_fila_usuario(vendor_row)

                    venta_obj, detalle, next_stock, subtotal, profit = crear_venta_por_item(
                        cliente,
                        vendedor,
                        sale_id,
                        product_id,
                        product_name,
                        product_brand,
                        price_value,
                        current_stock,
                        cost_value,
                        quantity,
                        datetime.utcnow(),
                    )

                    cursor.execute(
                        "UPDATE productos SET stock = :stock, fecha_actualizacion = CURRENT_TIMESTAMP "
                        "WHERE id_producto = :id_producto",
                        {"stock": next_stock, "id_producto": product_id},
                    )

                    total_amount += subtotal
                    total_units += quantity
                    ticket_items.append(detalle)

                    cursor.execute(
                        "INSERT INTO venta_detalle (id_venta, id_producto, cantidad, precio_unitario, costo_unitario, subtotal, margen_unitario) "
                        "VALUES (:id_venta, :id_producto, :cantidad, :precio_unitario, :costo_unitario, :subtotal, :margen_unitario)",
                        {
                            "id_venta": sale_id,
                            "id_producto": product_id,
                            "cantidad": quantity,
                            "precio_unitario": price_value,
                            "costo_unitario": cost_value,
                            "subtotal": subtotal,
                            "margen_unitario": round(profit / quantity, 2) if profit is not None else None,
                        },
                    )

                cursor.execute(
                    "UPDATE ventas SET monto_total = :monto_total, total_unidades = :total_unidades WHERE id_venta = :id_venta",
                    {"monto_total": round(total_amount, 2), "total_unidades": total_units, "id_venta": sale_id},
                )
                connection.commit()

        return {
            "id_venta": sale_id,
            "id_cliente": client_id,
            "id_vendedor": vendor_id,
            "fecha_venta": datetime.utcnow().isoformat(),
            "monto_total": round(total_amount, 2),
            "total_unidades": total_units,
            "items": ticket_items,
        }

    def list_client_purchases(self, client_id: str, start_date: datetime | None, page: int, page_size: int) -> tuple[list[dict[str, object | None]], int]:
        filters = ["v.id_cliente = :id_cliente"]
        parameters: dict[str, object] = {"id_cliente": client_id}
        if start_date:
            filters.append("v.fecha_venta >= :start_date")
            parameters["start_date"] = start_date

        where_clause = " WHERE " + " AND ".join(filters)
        query_count = f"SELECT COUNT(DISTINCT v.id_venta) FROM ventas v{where_clause}"
        query_list = (
            "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades "
            f"FROM ventas v{where_clause} "
            "ORDER BY v.fecha_venta DESC, v.id_venta DESC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"
        )

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query_count, parameters)
                total_items = int(cursor.fetchone()[0] or 0)
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
                current_page = min(page, total_pages)
                offset = (current_page - 1) * page_size
                cursor.execute(
                    query_list,
                    {**parameters, "offset": offset, "page_size": page_size},
                )
                rows = cursor.fetchall()
                sale_ids = [row[0] for row in rows]
                details_by_sale: dict[object, list[dict[str, object]]] = {}
                if sale_ids:
                    placeholders = ", ".join(f":sale_{index}" for index in range(len(sale_ids)))
                    cursor.execute(
                        "SELECT d.id_venta, d.id_producto, p.nombre, d.cantidad "
                        "FROM venta_detalle d "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        f"WHERE d.id_venta IN ({placeholders}) "
                        "ORDER BY d.id_venta DESC, d.id_producto ASC",
                        {f"sale_{index}": sale_id for index, sale_id in enumerate(sale_ids)},
                    )
                    for sale_id, product_id, product_name, quantity in cursor.fetchall():
                        details_by_sale.setdefault(sale_id, []).append(
                            {
                                "id_producto": product_id,
                                "nombre": str(product_name or "Producto sin nombre"),
                                "cantidad": int(quantity) if quantity is not None else 0,
                            }
                        )
        items = []
        for row in rows:
            sale_id = row[0]
            products = details_by_sale.get(sale_id, [])
            resumen = ", ".join(f"{product['nombre']} x{product['cantidad']}" for product in products[:3])
            if len(products) > 3:
                resumen = f"{resumen}, +{len(products) - 3} más" if resumen else f"+{len(products) - 3} más"
            items.append(
                {
                    "id_venta": sale_id,
                    "fecha_venta": row[1].isoformat() if row[1] else None,
                    "monto_total": float(row[2]) if row[2] is not None else 0.0,
                    "total_unidades": int(row[3]) if row[3] is not None else 0,
                    "numero_pedido": str(sale_id),
                    "resumen": resumen,
                    "productos": products,
                }
            )
        return items, total_items

    def list_vendor_purchases(self, vendor_id: str, start_date: datetime | None, page: int, page_size: int) -> tuple[list[dict[str, object | None]], int]:
        filters = ["v.id_vendedor = :id_vendedor"]
        parameters: dict[str, object] = {"id_vendedor": vendor_id}
        if start_date:
            filters.append("v.fecha_venta >= :start_date")
            parameters["start_date"] = start_date

        where_clause = " WHERE " + " AND ".join(filters)
        query_count = f"SELECT COUNT(DISTINCT v.id_venta) FROM ventas v{where_clause}"
        query_list = (
            "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades, u.id_usuario, u.nombre "
            f"FROM ventas v JOIN usuarios u ON u.id_usuario = v.id_cliente{where_clause} "
            "ORDER BY v.fecha_venta DESC, v.id_venta DESC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"
        )

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query_count, parameters)
                total_items = int(cursor.fetchone()[0] or 0)
                total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
                current_page = min(page, total_pages)
                offset = (current_page - 1) * page_size
                cursor.execute(
                    query_list,
                    {**parameters, "offset": offset, "page_size": page_size},
                )
                rows = cursor.fetchall()
                sale_ids = [row[0] for row in rows]
                details_by_sale: dict[object, list[dict[str, object]]] = {}
                if sale_ids:
                    placeholders = ", ".join(f":sale_{index}" for index in range(len(sale_ids)))
                    cursor.execute(
                        "SELECT d.id_venta, d.id_producto, p.nombre, d.cantidad "
                        "FROM venta_detalle d "
                        "LEFT JOIN productos p ON p.id_producto = d.id_producto "
                        f"WHERE d.id_venta IN ({placeholders}) "
                        "ORDER BY d.id_venta DESC, d.id_producto ASC",
                        {f"sale_{index}": sale_id for index, sale_id in enumerate(sale_ids)},
                    )
                    for sale_id, product_id, product_name, quantity in cursor.fetchall():
                        details_by_sale.setdefault(sale_id, []).append(
                            {
                                "id_producto": product_id,
                                "nombre": str(product_name or "Producto sin nombre"),
                                "cantidad": int(quantity) if quantity is not None else 0,
                            }
                        )
        items = []
        for row in rows:
            sale_id = row[0]
            products = details_by_sale.get(sale_id, [])
            resumen = ", ".join(f"{product['nombre']} x{product['cantidad']}" for product in products[:3])
            if len(products) > 3:
                resumen = f"{resumen}, +{len(products) - 3} más" if resumen else f"+{len(products) - 3} más"
            items.append(
                {
                    "id_venta": sale_id,
                    "fecha_venta": row[1].isoformat() if row[1] else None,
                    "monto_total": float(row[2]) if row[2] is not None else 0.0,
                    "total_unidades": int(row[3]) if row[3] is not None else 0,
                    "cliente": {
                        "id_cliente": row[4],
                        "nombre": row[5],
                    },
                    "numero_pedido": str(sale_id),
                    "resumen": resumen,
                    "productos": products,
                }
            )
        return items, total_items

    def get_client_purchase_ticket(self, sale_id: str) -> dict[str, object | None]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades, "
                    "u.id_usuario, u.nombre, v.id_vendedor, uv.nombre AS vendedor_nombre "
                    "FROM ventas v "
                    "JOIN usuarios u ON u.id_usuario = v.id_cliente "
                    "LEFT JOIN vendedores vv ON vv.id_vendedor = v.id_vendedor "
                    "LEFT JOIN usuarios uv ON uv.id_usuario = vv.id_vendedor "
                    "WHERE v.id_venta = :id_venta",
                    {"id_venta": sale_id},
                )
                header = cursor.fetchone()
                if not header:
                    raise DatabaseNotFoundError("La venta no existe.")
                cursor.execute(
                    "SELECT d.id_producto, p.nombre, p.marca, d.cantidad, d.precio_unitario, d.subtotal, d.costo_unitario, d.margen_unitario "
                    "FROM venta_detalle d "
                    "JOIN productos p ON p.id_producto = d.id_producto "
                    "WHERE d.id_venta = :id_venta",
                    {"id_venta": sale_id},
                )
                details = cursor.fetchall()
        return {
            "id_venta": header[0],
            "fecha_venta": header[1].isoformat() if header[1] else None,
            "monto_total": float(header[2]) if header[2] is not None else 0.0,
            "total_unidades": int(header[3]) if header[3] is not None else 0,
            "cliente": {
                "id_cliente": header[4],
                "nombre": header[5],
            },
            "vendedor": {
                "id_vendedor": header[6],
                "nombre": header[7],
            },
            "items": [
                {
                    "id_producto": row[0],
                    "nombre": row[1],
                    "marca": row[2],
                    "cantidad": int(row[3]) if row[3] is not None else 0,
                    "precio_unitario": float(row[4]) if row[4] is not None else 0.0,
                    "subtotal": float(row[5]) if row[5] is not None else 0.0,
                    "costo_unitario": float(row[6]) if row[6] is not None else None,
                    "margen_unitario": float(row[7]) if row[7] is not None else None,
                }
                for row in details
            ],
        }

    def get_financial_indicators(self) -> dict[str, object]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM productos")
                total_products = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario = 'Vendedor'")
                total_vendors = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario = 'Cliente'")
                total_clients = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(monto_total), 0) FROM ventas")
                sales_row = cursor.fetchone()
                total_sales = int(sales_row[0] or 0)
                revenue = float(sales_row[1] or 0)
                cursor.execute("SELECT COALESCE(SUM(d.costo_unitario * d.cantidad), 0) FROM venta_detalle d")
                total_cost = float(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM productos WHERE stock <= 10")
                low_stock = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM productos WHERE fecha_actualizacion < (CURRENT_DATE - 30)")
                stagnant_count = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT AVG(monto_total) FROM ventas")
                avg_ticket_row = cursor.fetchone()
                avg_ticket = float(avg_ticket_row[0] or 0)

        return {
            "total_productos": total_products,
            "total_vendedores": total_vendors,
            "total_clientes": total_clients,
            "total_ventas": total_sales,
            "ingresos_totales": revenue,
            "costos_totales": total_cost,
            "productos_stock_bajo": low_stock,
            "productos_estancados": stagnant_count,
            "avg_ticket": avg_ticket,
        }


db = OracleDB()
