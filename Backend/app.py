from __future__ import annotations

import os
import re
import math
import uuid
from functools import lru_cache
from datetime import date, datetime, timedelta
from pathlib import Path
import logging

import oracledb  # type: ignore[import-not-found]
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
from pydantic import BaseModel
import numpy as np
import io
import csv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("daad-backend")

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_PATH = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

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

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI(title="DAAD Auth API")
app.add_middleware(
  CORSMiddleware,
  allow_origins=[FRONTEND_URL],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


class RegisterRequest(BaseModel):
  nombre: str
  telefono: str
  correo: str
  tipo_usuario: str
  contrasena: str


class LoginRequest(BaseModel):
  correo: str
  contrasena: str


class ProductCreateRequest(BaseModel):
  id_producto: str
  nombre: str
  marca: str | None = None
  categoria: str | None = None
  precio_actual: float | None = None
  stock: int = 0
  precio_fabricacion: float | None = None
  fecha_caducidad: date | None = None


class ProductUpdateRequest(BaseModel):
  nombre: str | None = None
  marca: str | None = None
  categoria: str | None = None
  precio_actual: float | None = None
  stock: int | None = None
  precio_fabricacion: float | None = None
  fecha_caducidad: date | None = None


class PurchaseItemRequest(BaseModel):
  id_producto: str
  cantidad: int


class PurchaseRequest(BaseModel):
  id_cliente: str
  id_vendedor: str | None = None
  items: list[PurchaseItemRequest]


def get_connection_string_from_tnsnames(tnsnames_path: Path, dsn_name: str) -> str | None:
  if not tnsnames_path.exists():
    return None
  try:
    content = tnsnames_path.read_text(encoding="utf-8")
    lines: list[str] = []
    for line in content.splitlines():
      line_strip = line.strip()
      if line_strip and not line_strip.startswith("#"):
        lines.append(line)
    clean_content = "\n".join(lines)

    pattern = re.compile(
      r"^\s*" + re.escape(dsn_name) + r"\s*=\s*\(",
      re.IGNORECASE | re.MULTILINE,
    )
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

    connection_string = clean_content[start_pos:end_pos].strip()
    return " ".join(connection_string.split())
  except Exception:
    return None


def get_connection():
  tns_path = wallet_location / "tnsnames.ora"
  connection_string = get_connection_string_from_tnsnames(tns_path, DB_DSN)
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


def validate_email(email: str) -> bool:
  return "@" in email


def validate_password(password: str) -> bool:
  return (
    len(password) >= 8
    and re.search(r"[A-Z]", password)
    and re.search(r"\d", password)
  )


def normalize_email(email: str) -> str:
  return email.strip().lower()


def normalize_product_id(product_id: str) -> str:
  return product_id.strip().upper()


def normalize_optional_text(value: str | None) -> str | None:
  if value is None:
    return None
  cleaned = value.strip()
  return cleaned or None


def product_row_to_dict(row: tuple) -> dict[str, object | None]:
  (
    id_producto,
    nombre,
    marca,
    categoria,
    precio_actual,
    stock,
    precio_fabricacion,
    fecha_caducidad,
    fecha_actualizacion,
  ) = row
  return {
    "id_producto": id_producto,
    "nombre": nombre,
    "marca": marca,
    "categoria": categoria,
    "precio_actual": float(precio_actual) if precio_actual is not None else None,
    "stock": int(stock) if stock is not None else None,
    "precio_fabricacion": float(precio_fabricacion) if precio_fabricacion is not None else None,
    "fecha_caducidad": fecha_caducidad.isoformat() if fecha_caducidad else None,
    "fecha_actualizacion": (
      fecha_actualizacion.isoformat() if isinstance(fecha_actualizacion, (datetime, date)) else None
    ),
  }


@app.get("/api/reportes/ventas/csv")
def export_sales_csv(period: str = Query("all")):
  start_date = resolve_period_start(period)

  query = (
    "SELECT v.id_venta, v.fecha_venta, v.id_cliente, cu.nombre AS cliente_nombre, v.id_vendedor, uv.nombre AS vendedor_nombre, "
    "d.id_producto, p.nombre AS producto_nombre, d.cantidad, d.precio_unitario, d.subtotal, v.monto_total, v.total_unidades "
    "FROM ventas v "
    "JOIN venta_detalle d ON d.id_venta = v.id_venta "
    "LEFT JOIN usuarios cu ON cu.id_usuario = v.id_cliente "
    "LEFT JOIN vendedores vv ON vv.id_vendedor = v.id_vendedor "
    "LEFT JOIN usuarios uv ON uv.id_usuario = vv.id_vendedor "
    "LEFT JOIN productos p ON p.id_producto = d.id_producto "
  )
  params: dict[str, object] = {}
  if start_date:
    query += " WHERE v.fecha_venta >= :start_date"
    params["start_date"] = start_date
  query += " ORDER BY v.fecha_venta DESC"

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al exportar ventas a CSV: %s", exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar el CSV.")

  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow([
    "id_venta",
    "fecha_venta",
    "id_cliente",
    "cliente_nombre",
    "id_vendedor",
    "vendedor_nombre",
    "id_producto",
    "producto_nombre",
    "cantidad",
    "precio_unitario",
    "subtotal",
    "monto_total",
    "total_unidades",
  ])

  for row in rows:
    fecha = row[1].isoformat() if row[1] else ""
    writer.writerow([
      row[0],
      fecha,
      row[2],
      row[3],
      row[4],
      row[5],
      row[6],
      row[7],
      int(row[8]) if row[8] is not None else 0,
      float(row[9]) if row[9] is not None else 0.0,
      float(row[10]) if row[10] is not None else 0.0,
      float(row[11]) if row[11] is not None else 0.0,
      int(row[12]) if row[12] is not None else 0,
    ])

  output.seek(0)
  filename = f"ventas_{(datetime.utcnow().date()).isoformat()}.csv"
  return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


BASE_PRODUCT_COLUMNS = ["id_producto", "nombre", "categoria", "precio_actual"]
OPTIONAL_PRODUCT_COLUMNS = ["marca", "stock", "precio_fabricacion", "fecha_caducidad", "fecha_actualizacion"]


@lru_cache(maxsize=1)
def get_product_columns() -> tuple[str, ...]:
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          "SELECT column_name FROM user_tab_columns WHERE table_name = 'PRODUCTOS'"
        )
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al consultar columnas de productos: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo validar la estructura de productos.",
    )

  return tuple(row[0].lower() for row in rows)


def build_product_select_columns() -> list[str]:
  available = set(get_product_columns())
  columns = [column for column in BASE_PRODUCT_COLUMNS if column in available]
  for column in OPTIONAL_PRODUCT_COLUMNS:
    if column in available:
      columns.append(column)
  return columns


def row_to_product_dict(row: tuple, selected_columns: list[str]) -> dict[str, object | None]:
  values = dict(zip(selected_columns, row))
  return {
    "id_producto": values.get("id_producto"),
    "nombre": values.get("nombre"),
    "marca": values.get("marca"),
    "categoria": values.get("categoria"),
    "precio_actual": float(values["precio_actual"]) if values.get("precio_actual") is not None else None,
    "stock": int(values["stock"]) if values.get("stock") is not None else None,
    "precio_fabricacion": float(values["precio_fabricacion"]) if values.get("precio_fabricacion") is not None else None,
    "fecha_caducidad": values["fecha_caducidad"].isoformat() if values.get("fecha_caducidad") else None,
    "fecha_actualizacion": (
      values["fecha_actualizacion"].isoformat() if values.get("fecha_actualizacion") else None
    ),
  }


def build_product_insert_sql(payload: ProductCreateRequest) -> tuple[str, dict[str, object | None]]:
  available = set(get_product_columns())
  columns: list[str] = []
  values: dict[str, object | None] = {}

  base_values = {
    "id_producto": normalize_product_id(payload.id_producto),
    "nombre": payload.nombre.strip(),
    "marca": normalize_optional_text(payload.marca),
    "categoria": normalize_optional_text(payload.categoria),
    "precio_actual": payload.precio_actual,
    "stock": payload.stock if payload.stock is not None else 0,
    "precio_fabricacion": payload.precio_fabricacion,
    "fecha_caducidad": payload.fecha_caducidad,
  }

  for column, value in base_values.items():
    if column in available:
      columns.append(column)
      values[column] = value

  if not columns:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="La tabla de productos no tiene columnas disponibles.",
    )

  sql = (
    f"INSERT INTO productos ({', '.join(columns)}) "
    f"VALUES ({', '.join(f':{column}' for column in columns)})"
  )
  return sql, values


def build_product_update_sql(
  payload: ProductUpdateRequest,
  product_id: str,
  provided_fields: set[str] | None = None,
) -> tuple[str, dict[str, object | None]]:
  available = set(get_product_columns())
  assignments: list[str] = []
  values: dict[str, object | None] = {"id_producto": product_id}

  updates = {
    "nombre": normalize_optional_text(payload.nombre),
    "marca": normalize_optional_text(payload.marca),
    "categoria": normalize_optional_text(payload.categoria),
    "precio_actual": payload.precio_actual,
    "stock": payload.stock,
    "precio_fabricacion": payload.precio_fabricacion,
    "fecha_caducidad": payload.fecha_caducidad,
  }

  for column, value in updates.items():
    if column in available:
      # Si el campo fue enviado explícitamente con valor None, queremos setear NULL
      if provided_fields and column in provided_fields and value is None:
        assignments.append(f"{column} = NULL")
      elif value is not None:
        assignments.append(f"{column} = :{column}")
        values[column] = value

  if "fecha_actualizacion" in available:
    assignments.append("fecha_actualizacion = CURRENT_TIMESTAMP")

  if not assignments:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="La tabla de productos no permite actualizaciones en este momento.",
    )

  sql = f"UPDATE productos SET {', '.join(assignments)} WHERE id_producto = :id_producto"
  return sql, values


SQL_LIST_PRODUCTOS = (
  "SELECT id_producto, nombre, marca, categoria, precio_actual, stock, precio_fabricacion, "
  "fecha_caducidad, fecha_actualizacion FROM productos ORDER BY fecha_actualizacion DESC, nombre ASC"
)

SQL_GET_PRODUCTO = (
  "SELECT id_producto, nombre, marca, categoria, precio_actual, stock, precio_fabricacion, "
  "fecha_caducidad, fecha_actualizacion FROM productos WHERE id_producto = :id_producto"
)

SQL_INSERT_PRODUCTO = (
  "INSERT INTO productos (id_producto, nombre, marca, categoria, precio_actual, stock, precio_fabricacion, fecha_caducidad) "
  "VALUES (:id_producto, :nombre, :marca, :categoria, :precio_actual, :stock, :precio_fabricacion, :fecha_caducidad)"
)

SQL_UPDATE_PRODUCTO = (
  "UPDATE productos SET "
  "nombre = COALESCE(:nombre, nombre), "
  "marca = COALESCE(:marca, marca), "
  "categoria = COALESCE(:categoria, categoria), "
  "precio_actual = COALESCE(:precio_actual, precio_actual), "
  "stock = COALESCE(:stock, stock), "
  "precio_fabricacion = COALESCE(:precio_fabricacion, precio_fabricacion), "
  "fecha_caducidad = COALESCE(:fecha_caducidad, fecha_caducidad), "
  "fecha_actualizacion = CURRENT_TIMESTAMP "
  "WHERE id_producto = :id_producto"
)

SQL_DELETE_PRODUCTO = "DELETE FROM productos WHERE id_producto = :id_producto"


def fetch_producto_by_id(product_id: str) -> dict[str, object | None] | None:
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        selected_columns = build_product_select_columns()
        cursor.execute(
          f"SELECT {', '.join(selected_columns)} FROM productos WHERE id_producto = :id_producto",
          {"id_producto": product_id},
        )
        row = cursor.fetchone()
  except Exception as exc:
    logger.exception("Error al consultar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el producto.",
    )

  if not row:
    return None
  return row_to_product_dict(row, selected_columns)


def fetch_price_history(product_id: str, limit: int = 12) -> list[dict[str, object]]:
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          "SELECT fecha, precio_registrado FROM ("
          "  SELECT fecha, precio_registrado FROM historial_precios "
          "  WHERE id_producto = :id_producto ORDER BY fecha DESC"
          ") WHERE ROWNUM <= :limit",
          {"id_producto": product_id, "limit": limit},
        )
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al consultar historial de precios: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el historial de precios.",
    )

  history: list[dict[str, object]] = []
  for fecha, precio in reversed(rows):
    history.append(
      {
        "fecha": fecha.isoformat() if fecha else None,
        "precio": float(precio) if precio is not None else None,
      }
    )
  return history


def fetch_competition_average(product_id: str) -> float | None:
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          "SELECT AVG(precio_competencia_promedio) FROM competencia_mercado WHERE id_producto = :id_producto",
          {"id_producto": product_id},
        )
        row = cursor.fetchone()
  except Exception as exc:
    logger.exception("Error al consultar competencia de mercado: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar la competencia de mercado.",
    )

  if not row or row[0] is None:
    return None
  return float(row[0])


def fetch_product_vendor(product_id: str) -> dict[str, object | None] | None:
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          "SELECT v.id_vendedor, u.nombre, v.codigo_vendedor, v.especialidad "
          "FROM producto_vendedor pv "
          "JOIN vendedores v ON v.id_vendedor = pv.id_vendedor "
          "JOIN usuarios u ON u.id_usuario = v.id_vendedor "
          "WHERE pv.id_producto = :id_producto",
          {"id_producto": product_id},
        )
        row = cursor.fetchone()
  except Exception as exc:
    logger.exception("Error al consultar vendedor del producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el vendedor del producto.",
    )

  if not row:
    return None

  return {
    "id_vendedor": row[0],
    "nombre_vendedor": row[1],
    "codigo_vendedor": row[2],
    "especialidad": row[3],
  }


def calculate_price_recommendation(
  product: dict[str, object | None],
  history: list[dict[str, object]],
  competition_average: float | None,
) -> dict[str, object | None]:
  current_price = float(product.get("precio_actual") or 0)
  cost_price = float(product.get("precio_fabricacion") or 0)
  stock = int(product.get("stock") or 0)

  history_prices = [float(item["precio"]) for item in history if item.get("precio") is not None]
  history_dates = [
    datetime.fromisoformat(item["fecha"]) if item.get("fecha") else datetime.utcnow()
    for item in history
  ]

  average_history = float(np.mean(history_prices)) if history_prices else current_price
  minimum_history = float(np.min(history_prices)) if history_prices else current_price
  latest_date = history_dates[-1] if history_dates else datetime.utcnow()
  stagnant_days = max((datetime.utcnow() - latest_date).days, 0)
  competition_gap = (
    ((current_price - competition_average) / competition_average)
    if competition_average and competition_average > 0
    else 0.0
  )
  margin = ((current_price - cost_price) / cost_price) if cost_price > 0 else 0.0

  if current_price <= minimum_history * 1.02:
    signal = "es el precio más bajo de los últimos días"
  elif current_price > average_history * 1.03:
    signal = "el precio está por arriba del promedio"
  else:
    signal = "el precio está en su precio promedio"

  suggested_price = current_price
  reason = "El precio actual se mantiene competitivo."

  if cost_price > 0 and margin < 0.1:
    suggested_price = round(cost_price * 1.1, 2)
    reason = "Se ajusta para asegurar una ganancia superior al 10%."
  elif stagnant_days >= 21 and competition_gap > 0:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.95
    suggested_price = max(floor_price, round(current_price * 0.95, 2))
    reason = "El producto lleva demasiado tiempo estancado; conviene bajar el precio para aumentar el giro."
  elif competition_average and current_price > competition_average * 1.05:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.95
    suggested_price = max(floor_price, round(competition_average * 0.99, 2))
    reason = "El precio está por encima de la competencia de mercado."
  elif stock >= 40 and current_price > average_history:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.97
    suggested_price = max(floor_price, round(current_price * 0.97, 2))
    reason = "Hay inventario suficiente; una ligera bajada puede acelerar la rotación."

  trend_label = "estable"
  estimated_buy_date = None
  slope = 0.0

  if len(history_prices) >= 2:
    x_values = np.array([(item_date - history_dates[0]).days for item_date in history_dates], dtype=float)
    y_values = np.array(history_prices, dtype=float)
    slope, intercept = np.polyfit(x_values, y_values, 1)
    if slope < 0 and suggested_price < current_price:
      days_until_target = (suggested_price - history_prices[-1]) / slope if slope != 0 else None
      if days_until_target and days_until_target > 0:
        estimated_date = history_dates[-1] + timedelta(days=math.ceil(days_until_target))
        estimated_buy_date = estimated_date.date().isoformat()
        trend_label = "a la baja"
    elif slope > 0:
      trend_label = "al alza"

  features = np.array([
    margin,
    max(competition_gap, 0.0),
    min(stagnant_days / 30.0, 3.0),
    min(stock / 50.0, 2.0),
  ])
  weights = np.array([0.50, 0.25, 0.15, -0.10])
  vector_score = float(np.dot(features, weights))

  return {
    "signal": signal,
    "suggested_price": suggested_price,
    "reason": reason,
    "margin_percent": round(margin * 100, 2),
    "competition_average": competition_average,
    "trend_label": trend_label,
    "estimated_buy_date": estimated_buy_date,
    "stagnant_days": stagnant_days,
    "vector_score": round(vector_score, 4),
  }


def build_client_product_detail(product_id: str) -> dict[str, object | None]:
  product = fetch_producto_by_id(product_id)
  if not product:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )

  history = fetch_price_history(product_id, limit=20)
  competition_average = fetch_competition_average(product_id)
  vendor = fetch_product_vendor(product_id)
  recommendation = calculate_price_recommendation(product, history, competition_average)

  return {
    "product": product,
    "vendor": vendor,
    "price_history": history,
    "competition_average": competition_average,
    "recommendation": recommendation,
  }


@app.get("/api/health")
def healthcheck():
  return {"status": "ok"}


@app.post("/api/auth/register")
def register_user(payload: RegisterRequest):
  email = normalize_email(payload.correo)
  if not validate_email(email):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )
  if not validate_password(payload.contrasena):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="La contrasena no cumple los criterios.",
    )
  if payload.tipo_usuario not in {"Vendedor", "Cliente"}:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Tipo de usuario no valido.",
    )

  user_id = str(uuid.uuid4())
  password_hash = pwd_context.hash(payload.contrasena)

  query_exists = "SELECT id_usuario FROM usuarios WHERE correo = :correo"
  query_insert = (
    "INSERT INTO usuarios (id_usuario, nombre, telefono, correo, tipo_usuario, password_hash) "
    "VALUES (:id_usuario, :nombre, :telefono, :correo, :tipo_usuario, :password_hash)"
  )

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_exists, {"correo": email})
        if cursor.fetchone():
          raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya esta registrado.",
          )
        cursor.execute(
          query_insert,
          {
            "id_usuario": user_id,
            "nombre": payload.nombre.strip(),
            "telefono": payload.telefono.strip(),
            "correo": email,
            "tipo_usuario": payload.tipo_usuario,
            "password_hash": password_hash,
          },
        )
        connection.commit()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al registrar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar el usuario.",
    )

  return {
    "id": user_id,
    "nombre": payload.nombre.strip(),
    "correo": email,
    "tipo_usuario": payload.tipo_usuario,
  }


@app.post("/api/auth/login")
def login_user(payload: LoginRequest):
  email = normalize_email(payload.correo)
  if not validate_email(email):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )

  query_user = (
    "SELECT id_usuario, nombre, correo, tipo_usuario, password_hash "
    "FROM usuarios WHERE correo = :correo"
  )

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_user, {"correo": email})
        row = cursor.fetchone()
  except Exception as exc:
    logger.exception("Error al validar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo validar el usuario.",
    )

  if not row:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Credenciales incorrectas.",
    )

  user_id, nombre, correo, tipo_usuario, password_hash = row
  if not pwd_context.verify(payload.contrasena, password_hash):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Credenciales incorrectas.",
    )

  return {
    "id": user_id,
    "nombre": nombre,
    "correo": correo,
    "tipo_usuario": tipo_usuario,
  }


@app.get("/api/productos")
def list_productos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        selected_columns = build_product_select_columns()
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
  except Exception as exc:
    logger.exception("Error al listar productos: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos.",
    )

  return {
    "items": [row_to_product_dict(row, selected_columns) for row in rows],
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/vendedor/productos")
def list_vendor_products(
  vendedor_id: str = Query(..., min_length=1),
  page: int = Query(1, ge=1),
  page_size: int = Query(20, ge=1, le=100),
):
  normalized_vendor_id = vendedor_id.strip()
  if not normalized_vendor_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vendedor es obligatorio.")

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        selected_columns = build_product_select_columns()
        selected_columns_sql = ", ".join(f"p.{column}" for column in selected_columns)
        cursor.execute(
          "SELECT COUNT(*) FROM productos p INNER JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
          "WHERE pv.id_vendedor = :vendedor_id",
          {"vendedor_id": normalized_vendor_id},
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
          {
            "vendedor_id": normalized_vendor_id,
            "offset": offset,
            "page_size": page_size,
          },
        )
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al listar productos del vendedor: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos del vendedor.",
    )

  return {
    "items": [row_to_product_dict(row, selected_columns) for row in rows],
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/productos/{product_id}")
def get_producto(product_id: str):
  producto = fetch_producto_by_id(normalize_product_id(product_id))
  if not producto:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )
  return producto


@app.post("/api/productos")
def create_producto(payload: ProductCreateRequest):
  product_id = normalize_product_id(payload.id_producto)
  nombre = payload.nombre.strip()
  marca = normalize_optional_text(payload.marca)
  categoria = normalize_optional_text(payload.categoria)

  if not product_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El id del producto es obligatorio.")
  if not nombre:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre del producto es obligatorio.")
  if payload.precio_actual is not None and payload.precio_actual < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio no puede ser negativo.")
  if payload.stock is not None and payload.stock < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El stock no puede ser negativo.")
  if payload.precio_fabricacion is not None and payload.precio_fabricacion < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El costo no puede ser negativo.")

  existing = fetch_producto_by_id(product_id)
  if existing:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="El producto ya existe.",
    )

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        sql, values = build_product_insert_sql(payload)
        cursor.execute(sql, values)
        connection.commit()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al crear producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo crear el producto.",
    )

  producto = fetch_producto_by_id(product_id)
  return producto


@app.put("/api/productos/{product_id}")
def update_producto(product_id: str, payload: ProductUpdateRequest):
  normalized_id = normalize_product_id(product_id)
  existing = fetch_producto_by_id(normalized_id)
  if not existing:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )

  if payload.precio_actual is not None and payload.precio_actual < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio no puede ser negativo.")
  if payload.stock is not None and payload.stock < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El stock no puede ser negativo.")
  if payload.precio_fabricacion is not None and payload.precio_fabricacion < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El costo no puede ser negativo.")

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        provided = set(getattr(payload, "__fields_set__", set()))
        sql, values = build_product_update_sql(payload, normalized_id, provided)
        logger.info("SQL UPDATE: %s", sql)
        logger.info("UPDATE values: %s", values)
        cursor.execute(sql, values)
        connection.commit()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al actualizar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo actualizar el producto.",
    )

  producto = fetch_producto_by_id(normalized_id)
  return producto


@app.delete("/api/productos/{product_id}")
def delete_producto(product_id: str):
  normalized_id = normalize_product_id(product_id)

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(SQL_DELETE_PRODUCTO, {"id_producto": normalized_id})
        if cursor.rowcount == 0:
          raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El producto no existe.",
          )
        connection.commit()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al eliminar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo eliminar el producto.",
    )

  return {"detail": "Producto eliminado correctamente."}


def resolve_period_start(period: str) -> datetime | None:
  now = datetime.utcnow()
  if period == "30d":
    return now - timedelta(days=30)
  if period == "3m":
    return now - timedelta(days=90)
  if period == "6m":
    return now - timedelta(days=180)
  if period == "1y":
    return now - timedelta(days=365)
  return None


@app.get("/api/cliente/productos")
def list_client_products(
  page: int = Query(1, ge=1),
  page_size: int = Query(12, ge=1, le=100),
  search: str | None = None,
):
  filters = ["p.stock > 0"]
  parameters: dict[str, object] = {}
  if search:
    filters.append("(LOWER(p.nombre) LIKE LOWER(:search) OR LOWER(p.marca) LIKE LOWER(:search) OR LOWER(p.categoria) LIKE LOWER(:search))")
    parameters["search"] = f"%{search.strip()}%"

  where_clause = " WHERE " + " AND ".join(filters) if filters else ""

  query_count = f"SELECT COUNT(*) FROM productos p{where_clause}"
  query_list = (
    "SELECT p.id_producto, p.nombre, p.marca, p.categoria, p.precio_actual, p.stock, "
    "p.precio_fabricacion, p.fecha_actualizacion, u.nombre AS vendedor_nombre, v.codigo_vendedor "
    "FROM productos p "
    "LEFT JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
    "LEFT JOIN vendedores v ON v.id_vendedor = pv.id_vendedor "
    "LEFT JOIN usuarios u ON u.id_usuario = v.id_vendedor"
    f"{where_clause} "
    "ORDER BY p.nombre ASC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"
  )

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_count, parameters)
        total_items = int(cursor.fetchone()[0] or 0)
        total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
        current_page = min(page, total_pages)
        offset = (current_page - 1) * page_size
        cursor.execute(
          query_list,
          {
            **parameters,
            "offset": offset,
            "page_size": page_size,
          },
        )
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al listar productos para cliente: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos.",
    )

  items = []
  for row in rows:
    items.append(
      {
        "id_producto": row[0],
        "nombre": row[1],
        "marca": row[2],
        "categoria": row[3],
        "precio_actual": float(row[4]) if row[4] is not None else None,
        "stock": int(row[5]) if row[5] is not None else 0,
        "precio_fabricacion": float(row[6]) if row[6] is not None else None,
        "fecha_actualizacion": row[7].isoformat() if row[7] else None,
        "vendedor_nombre": row[8],
        "codigo_vendedor": row[9],
      }
    )

  return {
    "items": items,
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/cliente/productos/{product_id}")
def get_client_product(product_id: str):
  return build_client_product_detail(normalize_product_id(product_id))


@app.post("/api/cliente/compras")
def create_purchase(payload: PurchaseRequest):
  client_id = payload.id_cliente.strip()
  if not client_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente es obligatorio.")
  if not payload.items:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El carrito esta vacio.")

  sale_id = str(uuid.uuid4())
  sale_vendor_id: str | None = payload.id_vendedor.strip() if payload.id_vendedor else None
  total_amount = 0.0
  total_units = 0
  ticket_items: list[dict[str, object]] = []

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          "SELECT id_usuario FROM usuarios WHERE id_usuario = :id_usuario AND tipo_usuario = 'Cliente'",
          {"id_usuario": client_id},
        )
        if not cursor.fetchone():
          raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El cliente no existe.",
          )

        if sale_vendor_id:
          cursor.execute(
            "SELECT id_vendedor FROM vendedores WHERE id_vendedor = :id_vendedor",
            {"id_vendedor": sale_vendor_id},
          )
          if not cursor.fetchone():
            raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail="El vendedor no existe.",
            )

        # insertar cabecera de la venta primero para respetar la FK de detalle
        logger.info("Creando venta %s para cliente %s (vendedor=%s)", sale_id, client_id, sale_vendor_id)
        cursor.execute(
          "INSERT INTO ventas (id_venta, id_cliente, id_vendedor, monto_total, total_unidades) "
          "VALUES (:id_venta, :id_cliente, :id_vendedor, :monto_total, :total_unidades)",
          {
            "id_venta": sale_id,
            "id_cliente": client_id,
            "id_vendedor": sale_vendor_id,
            "monto_total": 0,
            "total_unidades": 0,
          },
        )
        # verificar que la cabecera fue creada (consulta inmediata)
        try:
          cursor.execute("SELECT id_venta FROM ventas WHERE id_venta = :id_venta", {"id_venta": sale_id})
          found = cursor.fetchone()
          logger.info("Verificacion venta creada: %s", bool(found))
        except Exception:
          logger.exception("No se pudo verificar la insercion de la venta %s", sale_id)

        for item in payload.items:
          product_id = normalize_product_id(item.id_producto)
          quantity = int(item.cantidad)
          if quantity <= 0:
            raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
              detail="La cantidad debe ser mayor a cero.",
            )

          cursor.execute(
            "SELECT p.nombre, p.marca, p.precio_actual, p.stock, p.precio_fabricacion, pv.id_vendedor "
            "FROM productos p "
            "LEFT JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
            "WHERE p.id_producto = :id_producto FOR UPDATE",
            {"id_producto": product_id},
          )
          product_row = cursor.fetchone()
          if not product_row:
            raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail=f"El producto {product_id} no existe.",
            )

          product_name, product_brand, price_actual, current_stock, product_cost, product_vendor_id = product_row
          current_stock = int(current_stock or 0)
          price_value = float(price_actual or 0)
          cost_value = float(product_cost or 0) if product_cost is not None else None

          if current_stock < quantity:
            raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
              detail=f"No hay stock suficiente para {product_name}.",
            )

          cursor.execute(
            "UPDATE productos SET stock = stock - :cantidad, fecha_actualizacion = CURRENT_TIMESTAMP "
            "WHERE id_producto = :id_producto",
            {"cantidad": quantity, "id_producto": product_id},
          )

          subtotal = round(price_value * quantity, 2)
          profit = round((price_value - (cost_value or 0)) * quantity, 2) if cost_value is not None else None
          total_amount += subtotal
          total_units += quantity
          ticket_items.append(
            {
              "id_producto": product_id,
              "nombre": product_name,
              "marca": product_brand,
              "cantidad": quantity,
              "precio_unitario": price_value,
              "subtotal": subtotal,
              "costo_unitario": cost_value,
              "margen_unitario": round(price_value - (cost_value or 0), 2) if cost_value is not None else None,
            }
          )

          if sale_vendor_id is None and product_vendor_id:
            sale_vendor_id = product_vendor_id

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
              "margen_unitario": profit / quantity if profit is not None else None,
            },
          )

        # actualizar la cabecera con los totales reales
        cursor.execute(
          "UPDATE ventas SET monto_total = :monto_total, total_unidades = :total_unidades WHERE id_venta = :id_venta",
          {
            "monto_total": round(total_amount, 2),
            "total_unidades": total_units,
            "id_venta": sale_id,
          },
        )
        connection.commit()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al registrar compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar la compra.",
    )

  return {
    "id_venta": sale_id,
    "id_cliente": client_id,
    "id_vendedor": sale_vendor_id,
    "fecha_venta": datetime.utcnow().isoformat(),
    "monto_total": round(total_amount, 2),
    "total_unidades": total_units,
    "items": ticket_items,
  }


@app.get("/api/cliente/compras")
def list_client_purchases(
  id_cliente: str = Query(...),
  period: str = Query("all"),
  page: int = Query(1, ge=1),
  page_size: int = Query(10, ge=1, le=50),
):
  client_id = id_cliente.strip()
  start_date = resolve_period_start(period)

  filters = ["v.id_cliente = :id_cliente"]
  parameters: dict[str, object] = {"id_cliente": client_id}
  if start_date:
    filters.append("v.fecha_venta >= :start_date")
    parameters["start_date"] = start_date

  where_clause = " WHERE " + " AND ".join(filters)

  query_count = f"SELECT COUNT(*) FROM ventas v{where_clause}"
  query_list = (
    "SELECT v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades, "
    "LISTAGG(d.id_producto || ' x' || d.cantidad, ', ') WITHIN GROUP (ORDER BY d.id_producto) AS resumen "
    "FROM ventas v "
    "JOIN venta_detalle d ON d.id_venta = v.id_venta"
    f"{where_clause} "
    "GROUP BY v.id_venta, v.fecha_venta, v.monto_total, v.total_unidades "
    "ORDER BY v.fecha_venta DESC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"
  )

  try:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_count, parameters)
        total_items = int(cursor.fetchone()[0] or 0)
        total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
        current_page = min(page, total_pages)
        offset = (current_page - 1) * page_size
        cursor.execute(
          query_list,
          {
            **parameters,
            "offset": offset,
            "page_size": page_size,
          },
        )
        rows = cursor.fetchall()
  except Exception as exc:
    logger.exception("Error al listar compras: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el historial de compras.",
    )

  items = []
  for row in rows:
    items.append(
      {
        "id_venta": row[0],
        "fecha_venta": row[1].isoformat() if row[1] else None,
        "monto_total": float(row[2]) if row[2] is not None else 0.0,
        "total_unidades": int(row[3]) if row[3] is not None else 0,
        "resumen": row[4],
      }
    )

  return {
    "items": items,
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/cliente/compras/{sale_id}")
def get_client_purchase_ticket(sale_id: str):
  try:
    with get_connection() as connection:
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
          raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La venta no existe.",
          )
        cursor.execute(
          "SELECT d.id_producto, p.nombre, p.marca, d.cantidad, d.precio_unitario, d.subtotal, d.costo_unitario, d.margen_unitario "
          "FROM venta_detalle d "
          "JOIN productos p ON p.id_producto = d.id_producto "
          "WHERE d.id_venta = :id_venta",
          {"id_venta": sale_id},
        )
        rows = cursor.fetchall()
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al consultar ticket de compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el ticket.",
    )

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
      for row in rows
    ],
  }


@app.get("/api/reportes/indicadores")
def get_financial_indicators():
  try:
    with get_connection() as connection:
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

        cursor.execute(
          "SELECT COALESCE(SUM(d.costo_unitario * d.cantidad), 0) FROM venta_detalle d"
        )
        total_cost = float(cursor.fetchone()[0] or 0)

        cursor.execute("SELECT COUNT(*) FROM productos WHERE stock <= 10")
        low_stock_products = int(cursor.fetchone()[0] or 0)

        cursor.execute(
          "SELECT COUNT(*) FROM productos WHERE fecha_actualizacion < (CURRENT_DATE - 30)"
        )
        stagnant_products = int(cursor.fetchone()[0] or 0)

        cursor.execute(
          "SELECT AVG(monto_total) FROM ventas"
        )
        avg_ticket_row = cursor.fetchone()
        avg_ticket = float(avg_ticket_row[0] or 0)
  except Exception as exc:
    logger.exception("Error al calcular indicadores financieros: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron calcular los indicadores financieros.",
    )

  profit = revenue - total_cost
  margin_percent = round((profit / revenue * 100), 2) if revenue > 0 else 0.0

  return {
    "total_products": total_products,
    "total_vendors": total_vendors,
    "total_clients": total_clients,
    "total_sales": total_sales,
    "revenue": round(revenue, 2),
    "total_cost": round(total_cost, 2),
    "profit": round(profit, 2),
    "margin_percent": margin_percent,
    "avg_ticket": round(avg_ticket, 2),
    "low_stock_products": low_stock_products,
    "stagnant_products": stagnant_products,
  }
