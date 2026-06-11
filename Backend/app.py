from __future__ import annotations

"""Backend principal del proyecto.

Define la aplicación FastAPI que expone la API REST para:
- registro, login y actualización de perfiles de usuario
- gestión de productos (listar, crear, actualizar, eliminar)
- compra de productos por clientes
- administración y consulta de ventas
- exportación de reportes en CSV e indicadores financieros

Este archivo es el punto de entrada del backend web y utiliza el servicio
`Backend.conexion_base.db` para acceder a la base de datos Oracle.
"""

import os
import re
import math
import uuid
from functools import lru_cache
from datetime import date, datetime, timedelta
from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
from pydantic import BaseModel
import numpy as np
import io
import csv
from Backend.conexion_base import (
  db,
  ConflictoBaseDatosError,
  BaseDatosNoEncontrada,
  ValidacionBaseDatosError,
)
from Backend.modelo_poo import Cliente, Informe, Persona, Producto, Venta, Vendedor, calcular_recomendacion_precio, crear_usuario_desde_fila_usuario
from Backend.recomendacion_precio import rankear_productos_similares, resumir_precios_similares
from Backend.recomendacion_precio.similitud import normalizar_texto_similitud
from Backend.recomendacion_precio.faiss_recommender import recomendar_precio

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("daad-backend")

FRONTEND_URL = os.environ.get("FRONTEND_URL")


def construir_origenes_permitidos(frontend_url: str | None) -> tuple[list[str], bool]:
  if frontend_url:
    allowed_origins = {frontend_url.strip()}
    if frontend_url.startswith("http://localhost:"):
      allowed_origins.add(frontend_url.replace("http://localhost:", "http://127.0.0.1:", 1))
    elif frontend_url.startswith("http://127.0.0.1:"):
      allowed_origins.add(frontend_url.replace("http://127.0.0.1:", "http://localhost:", 1))
    return sorted(origin for origin in allowed_origins if origin), True

  # En entorno de desarrollo permitimos cualquiera de las URLs locales habituales.
  return ["*"] , False

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI(title="DAAD Auth API")
allowed_origins, allow_credentials = construir_origenes_permitidos(FRONTEND_URL)
app.add_middleware(
  CORSMiddleware,
  allow_origins=allowed_origins,
  allow_credentials=allow_credentials,
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
  tipo_usuario: str | None = None


class ProfileUpdateRequest(BaseModel):
  id_usuario: str
  nombre: str | None = None
  contrasena: str | None = None


class ProductCreateRequest(BaseModel):
  id_producto: str
  nombre: str
  marca: str | None = None
  categoria: str | None = None
  precio_actual: float | None = None
  stock: int = 0
  precio_fabricacion: float | None = None
  fecha_caducidad: date | None = None
  id_vendedor: str | None = None


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



class RecommendPriceRequest(BaseModel):
  marca: str | None = None
  categoria: str | None = None
  nombre: str





def validar_correo(email: str) -> bool:
  return "@" in email


def validar_contrasena(password: str) -> bool:
  return (
    len(password) >= 8
    and re.search(r"[A-Z]", password)
    and re.search(r"\d", password)
  )


def normalizar_correo(email: str) -> str:
  return email.strip().lower()


def normalizar_rol_usuario(role: str) -> str:
  normalized_role = role.strip().lower()
  if normalized_role in {"vendedor", "seller", "merchant"}:
    return "Vendedor"
  if normalized_role in {"cliente", "customer", "client"}:
    return "Cliente"
  raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Tipo de usuario no valido.",
  )


def normalizar_id_producto(product_id: str) -> str:
  return product_id.strip().upper()


def normalizar_texto_opcional(value: str | None) -> str | None:
  if value is None:
    return None
  cleaned = value.strip()
  return cleaned or None


def normalizar_texto_mostrar(value: object | None, fallback: str = "") -> str:
  if value is None:
    return fallback
  cleaned = " ".join(str(value).split())
  return cleaned or fallback


def _validar_no_negativo(name: str, value: float | int | None) -> None:
  if value is None:
    return
  if float(value) < 0:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"El campo '{name}' no puede ser negativo.",
    )


def _paginar_respuesta(
  items: list[dict[str, object | None]],
  total_items: int,
  page: int,
  page_size: int,
) -> dict[str, object | int]:
  total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
  current_page = min(page, total_pages)
  return {
    "items": items,
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/vendedor/reportes/ventas/csv")
def exportar_ventas_csv(period: str = Query("all")):
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
    with db.connect() as connection:
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
OPTIONAL_PRODUCT_COLUMNS = ["marca", "stock", "precio_fabricacion", "fecha_caducidad", "imagen_url", "fecha_actualizacion"]


@lru_cache(maxsize=1)
def obtener_columnas_producto() -> tuple[str, ...]:
  try:
    with db.connect() as connection:
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


def construir_columnas_seleccion_producto() -> list[str]:
  available = set(obtener_columnas_producto())
  columns = [column for column in BASE_PRODUCT_COLUMNS if column in available]
  for column in OPTIONAL_PRODUCT_COLUMNS:
    if column in available:
      columns.append(column)
  return columns


def consultar_producto_por_id(product_id: str) -> dict[str, object | None] | None:
  try:
    producto = db.consultar_producto_por_id(product_id)
  except Exception as exc:
    logger.exception("Error al consultar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el producto.",
    )

  if not producto:
    return None
  return producto.a_diccionario()


def obtener_historial_precios(product_id: str, limit: int = 12) -> list[dict[str, object]]:
  try:
    return db.obtener_historial_precios(product_id, limit)
  except Exception as exc:
    logger.exception("Error al consultar historial de precios: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el historial de precios.",
    )


def obtener_promedio_competencia(product_id: str) -> float | None:
  try:
    return db.obtener_promedio_competencia(product_id)
  except Exception as exc:
    logger.exception("Error al consultar competencia de mercado: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar la competencia de mercado.",
    )


def obtener_vendedor_producto(product_id: str) -> dict[str, object | None] | None:
  try:
    return db.obtener_vendedor_producto(product_id)
  except Exception as exc:
    logger.exception("Error al consultar vendedor del producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el vendedor del producto.",
    )


def obtener_persona_por_id(user_id: str) -> Persona | None:
  try:
    return db.obtener_persona_por_id(user_id)
  except Exception as exc:
    logger.exception("Error al consultar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el usuario.",
    )


def obtener_firma_catalogo_similitud() -> tuple[int, str]:
  try:
    return db.obtener_firma_catalogo_similitud()
  except Exception as exc:
    logger.exception("Error al consultar la firma del catalogo para similitud: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el catalogo de productos.",
    )


@lru_cache(maxsize=8)
def cargar_catalogo_similitud(signature: tuple[int, str]) -> list[dict[str, object | None]]:
  try:
    return db.cargar_catalogo_similitud(signature)
  except Exception as exc:
    logger.exception("Error al cargar el catalogo para similitud: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo cargar el catalogo de productos.",
    )


def calcular_recomendacion_precio_app(
  product: dict[str, object | None],
  history: list[dict[str, object]],
  competition_average: float | None,
) -> dict[str, object | None]:
  product_object = Producto.desde_dict(product)
  return calcular_recomendacion_precio(
    product_object,
    history,
    competition_average,
    cargar_catalogo_similitud(obtener_firma_catalogo_similitud()),
    limite=5,
  )



@app.post("/api/recomendar-precio")
def api_recomendar_precio(request: RecommendPriceRequest):
  try:
    salida = recomendar_precio(request.marca, request.categoria, request.nombre, top_k=10, min_sim=0.6)
    return salida
  except Exception as exc:
    logger.exception("Error en recomendacion de precio: %s", exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def construir_detalle_producto_cliente(product_id: str) -> dict[str, object | None]:
  product = consultar_producto_por_id(product_id)
  if not product:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )

  history = obtener_historial_precios(product_id, limit=20)
  competition_average = obtener_promedio_competencia(product_id)
  vendor = obtener_vendedor_producto(product_id)
  recommendation = calcular_recomendacion_precio_app(product, history, competition_average)

  return {
    "product": product,
    "vendor": vendor,
    "price_history": history,
    "competition_average": competition_average,
    "recommendation": recommendation,
  }


@app.post("/api/productos/recomendacion-precio")
def recomendar_precio_producto(payload: RecommendPriceRequest):
  # Usar el recomendador basado en filtro tipo Excel para sugerir precios.
  sugerencia = recomendar_precio(payload.marca, payload.categoria, payload.nombre, top_k=10, min_sim=0.6)

  return {
    "suggested_price": sugerencia.get("precio_sugerido"),
    "reason": "Recomendación calculada sobre productos similares.",
    "similar_products": [
      {
        "id_producto": item.get("id_producto"),
        "nombre": item.get("nombre"),
        "precio_actual": item.get("precio_actual"),
        "similarity_score": item.get("similitud") if item.get("similitud") is not None else item.get("similarity_score"),
      }
      for item in sugerencia.get("similares", [])
    ],
  }


@app.get("/api/health")
def estado_salud():
  return {"status": "ok"}


@app.post("/api/auth/register")
def registrar_usuario(payload: RegisterRequest):
  email = normalizar_correo(payload.correo)
  tipo_usuario = normalizar_rol_usuario(payload.tipo_usuario)
  if not validar_correo(email):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )
  if not validar_contrasena(payload.contrasena):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="La contrasena no cumple los criterios.",
    )
  user_id = str(uuid.uuid4())
  password_hash = pwd_context.hash(payload.contrasena)

  if tipo_usuario == "Vendedor":
    persona = Vendedor(
      id_persona=user_id,
      nombre=payload.nombre.strip(),
      telefono=payload.telefono.strip(),
      correo=email,
      id_vendedor=user_id,
      codigo_vendedor=user_id,
      password_hash=password_hash,
    )
  else:
    persona = Cliente(
      id_persona=user_id,
      nombre=payload.nombre.strip(),
      telefono=payload.telefono.strip(),
      correo=email,
      password_hash=password_hash,
    )

  try:
    db.registrar_usuario(persona)
  except ConflictoBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
  except Exception as exc:
    logger.exception("Error al registrar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar el usuario.",
    )

  return persona.a_diccionario_publico()


@app.post("/api/auth/login")
def iniciar_sesion_usuario(payload: LoginRequest):
  email = normalizar_correo(payload.correo)
  tipo_usuario = normalizar_rol_usuario(payload.tipo_usuario) if payload.tipo_usuario else None
  if not validar_correo(email):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )

  query_roles_by_email = "SELECT tipo_usuario FROM usuarios WHERE correo = :correo"
  query_user = (
    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario, password_hash "
    "FROM usuarios WHERE correo = :correo AND tipo_usuario = :tipo_usuario"
  )

  try:
    with db.connect() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_roles_by_email, {"correo": email})
        available_roles = [row[0] for row in cursor.fetchall()]
        if not available_roles:
          raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
          )

        if not tipo_usuario:
          if len(available_roles) > 1:
            raise HTTPException(
              status_code=status.HTTP_409_CONFLICT,
              detail="Este correo existe en multiples roles. Selecciona tu tipo de cuenta.",
            )
          tipo_usuario = available_roles[0]
        elif tipo_usuario not in available_roles:
          available_label = ", ".join(sorted(available_roles))
          if len(available_roles) == 1:
            raise HTTPException(
              status_code=status.HTTP_409_CONFLICT,
              detail=f"Tu cuenta esta registrada, pero como {available_roles[0].lower()}.",
            )
          raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tu cuenta esta registrada como {available_label.lower()}. Selecciona el rol correcto.",
          )

        cursor.execute(query_user, {"correo": email, "tipo_usuario": tipo_usuario})
        row = cursor.fetchone()
  except Exception as exc:
    if isinstance(exc, HTTPException):
      raise
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

  user = crear_usuario_desde_fila_usuario(row[:5], password_hash=row[5])
  if not pwd_context.verify(payload.contrasena, row[5]):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Credenciales incorrectas.",
    )

  return user.a_diccionario_publico()


@app.put("/api/auth/profile")
def actualizar_perfil_usuario_endpoint(payload: ProfileUpdateRequest):
  user_id = payload.id_usuario.strip()
  new_name = normalizar_texto_opcional(payload.nombre)
  new_password = payload.contrasena.strip() if payload.contrasena is not None else None

  if not user_id:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="El usuario es obligatorio.",
    )

  if new_name is None and not new_password:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Debes proporcionar un nombre o una contrasena nueva.",
    )

  new_password_hash = pwd_context.hash(new_password) if new_password else None
  if new_password and not validar_contrasena(new_password):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="La nueva contrasena no cumple los criterios.",
    )

  persona = obtener_persona_por_id(user_id)
  if not persona:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no existe.")

  if new_name is not None:
    persona.cambiar_nombre(new_name)
  if new_password_hash:
    persona.cambiar_contrasena(new_password_hash)

  try:
    db.actualizar_perfil_usuario(persona, password_hash=new_password_hash)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except ValidacionBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
  except Exception as exc:
    logger.exception("Error al actualizar perfil: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo actualizar el perfil.",
    )

  persona_actualizada = obtener_persona_por_id(user_id)
  if not persona_actualizada:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo recuperar el perfil actualizado.",
    )

  return persona_actualizada.a_diccionario_publico()


@app.get("/api/productos")
def listar_productos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
  try:
    productos, total_items = db.listar_productos(page, page_size)
  except Exception as exc:
    logger.exception("Error al listar productos: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos.",
    )

  return _paginar_respuesta(
    [producto.a_diccionario() for producto in productos],
    total_items,
    page,
    page_size,
  )


@app.get("/api/vendedor/productos")
def listar_productos_vendedor(
  vendedor_id: str = Query(..., min_length=1),
  page: int = Query(1, ge=1),
  page_size: int = Query(20, ge=1, le=100),
):
  normalized_vendor_id = vendedor_id.strip()
  if not normalized_vendor_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vendedor es obligatorio.")

  try:
    productos, total_items = db.listar_productos_vendedor(normalized_vendor_id, page, page_size)
  except Exception as exc:
    logger.exception("Error al listar productos del vendedor: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos del vendedor.",
    )

  return _paginar_respuesta(
    [producto.a_diccionario() for producto in productos],
    total_items,
    page,
    page_size,
  )


@app.get("/api/productos/{product_id}")
def obtener_producto(product_id: str):
  producto = consultar_producto_por_id(normalizar_id_producto(product_id))
  if not producto:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )
  return producto


@app.post("/api/productos")
def crear_producto(payload: ProductCreateRequest):
  product_id = normalizar_id_producto(payload.id_producto)
  nombre = payload.nombre.strip()
  marca = normalizar_texto_opcional(payload.marca)
  categoria = normalizar_texto_opcional(payload.categoria)
  imagen_url = normalizar_texto_opcional(payload.imagen_url)

  if not product_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El id del producto es obligatorio.")
  if not nombre:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre del producto es obligatorio.")
  _validar_no_negativo("precio_actual", payload.precio_actual)
  _validar_no_negativo("stock", payload.stock)
  _validar_no_negativo("precio_fabricacion", payload.precio_fabricacion)

  producto = Producto(
    id_producto=product_id,
    nombre=nombre,
    marca=marca,
    precio_venta_actual=payload.precio_actual,
    stock=payload.stock if payload.stock is not None else 0,
    precio_fabricacion=payload.precio_fabricacion,
    fecha_caducidad=payload.fecha_caducidad,
    imagen_url=imagen_url,
    categoria=categoria,
  )

  existing = consultar_producto_por_id(product_id)
  if existing:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="El producto ya existe.",
    )

  vendor_id = payload.id_vendedor.strip() if payload.id_vendedor else None
  try:
    db.crear_producto(producto, vendor_id=vendor_id)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except Exception as exc:
    logger.exception("Error al crear producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo crear el producto.",
    )

  producto_creado = consultar_producto_por_id(product_id)
  try:
    sugerencia = recomendar_precio(marca, categoria, nombre, top_k=10, min_sim=0.6)
  except Exception:
    sugerencia = {"precio_sugerido": None, "precio_min": None, "precio_max": None, "similares": []}

  # Añadir la sugerencia al diccionario del producto devuelto
  if producto_creado is None:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo recuperar el producto creado.")
  producto_creado["sugerencia_precio"] = sugerencia
  return producto_creado


@app.put("/api/productos/{product_id}")
def actualizar_producto(product_id: str, payload: ProductUpdateRequest):
  normalized_id = normalizar_id_producto(product_id)
  existing = consultar_producto_por_id(normalized_id)
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

  producto = Producto.desde_dict(existing)
  producto.actualizar_datos(
    nombre=payload.nombre.strip() if payload.nombre is not None else None,
    marca=normalizar_texto_opcional(payload.marca) if payload.marca is not None else None,
    categoria=normalizar_texto_opcional(payload.categoria) if payload.categoria is not None else None,
    precio_actual=payload.precio_actual,
    stock=payload.stock,
    precio_fabricacion=payload.precio_fabricacion,
    fecha_caducidad=payload.fecha_caducidad,
    imagen_url=normalizar_texto_opcional(payload.imagen_url) if payload.imagen_url is not None else None,
  )

  try:
    provided = set(getattr(payload, "__fields_set__", set()))
    db.actualizar_producto(normalized_id, producto, provided)
  except Exception as exc:
    logger.exception("Error al actualizar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo actualizar el producto.",
    )

  producto = consultar_producto_por_id(normalized_id)
  return producto


@app.delete("/api/productos/{product_id}")
def eliminar_producto(product_id: str):
  normalized_id = normalizar_id_producto(product_id)

  try:
    db.eliminar_producto(normalized_id)
  except HTTPException:
    raise
  except Exception as exc:
    logger.exception("Error al eliminar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo eliminar el producto.",
    )

  return {"detail": "Producto eliminado correctamente."}


def resolver_inicio_periodo(period: str) -> datetime | None:
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
def listar_productos_cliente(
  page: int = Query(1, ge=1),
  page_size: int = Query(12, ge=1, le=100),
  search: str | None = None,
):
  def _normalizar_columna_para_busqueda(columna: str) -> str:
    return (
      "TRANSLATE(LOWER(" + columna + "), "
      "'áéíóúüñàèìòùâêîôûç', 'aeiouunaeiouaeiouaeiouc')"
    )
  filters = ["p.stock > 0"]
  parameters: dict[str, object] = {}
  if search:
    termino_norm = normalizar_texto_similitud(search.strip())
    parameters["search"] = f"%{termino_norm}%"
    filters.append(
      "(" +
      _normalizar_columna_para_busqueda("p.nombre") +
      " LIKE :search OR " +
      _normalizar_columna_para_busqueda("p.marca") +
      " LIKE :search OR " +
      _normalizar_columna_para_busqueda("p.categoria") +
      " LIKE :search)"
    )

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
    with db.connect() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query_count, parameters)
        total_items = int(cursor.fetchone()[0] or 0)
        current_page = min(page, max(1, math.ceil(total_items / page_size)) if total_items else 1)
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
    producto = Producto.desde_fila(
      row,
      ["id_producto", "nombre", "marca", "categoria", "precio_actual", "stock", "precio_fabricacion", "fecha_actualizacion"],
    )
    producto_dict = producto.a_diccionario()
    producto_dict.update(
      {
        "vendedor_nombre": row[8],
        "codigo_vendedor": row[9],
      }
    )
    items.append(producto_dict)

  return _paginar_respuesta(items, total_items, current_page, page_size)


@app.get("/api/cliente/productos/{product_id}")
def obtener_producto_cliente(product_id: str):
  return construir_detalle_producto_cliente(normalizar_id_producto(product_id))


@app.post("/api/cliente/compras")
def crear_compra(payload: PurchaseRequest):
  if not payload.id_cliente.strip():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente es obligatorio.")
  if not payload.items:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El carrito esta vacio.")

  try:
    result = db.crear_compra(
      payload.id_cliente,
      payload.id_vendedor,
      [item.dict() for item in payload.items],
    )
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except ValidacionBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
  except Exception as exc:
    logger.exception("Error al registrar compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar la compra.",
    )

  return result


@app.get("/api/cliente/compras")
def listar_compras_cliente(
  id_cliente: str = Query(...),
  period: str = Query("all"),
  page: int = Query(1, ge=1),
  page_size: int = Query(10, ge=1, le=50),
):
  client_id = id_cliente.strip()
  start_date = resolver_inicio_periodo(period)

  try:
    items, total_items = db.listar_compras_cliente(client_id, start_date, page, page_size)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    current_page = min(page, total_pages)
  except Exception as exc:
    logger.exception("Error al listar compras: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el historial de compras.",
    )

  return {
    "items": items,
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/vendedor/compras")
def listar_compras_vendedor(
  id_vendedor: str = Query(...),
  period: str = Query("all"),
  page: int = Query(1, ge=1),
  page_size: int = Query(10, ge=1, le=50),
):
  vendor_id = id_vendedor.strip()
  if not vendor_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vendedor es obligatorio.")

  start_date = resolver_inicio_periodo(period)

  try:
    items, total_items = db.listar_compras_vendedor(vendor_id, start_date, page, page_size)
    total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    current_page = min(page, total_pages)
  except Exception as exc:
    logger.exception("Error al listar compras del vendedor: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el historial de ventas del vendedor.",
    )

  return {
    "items": items,
    "page": current_page,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_pages,
  }


@app.get("/api/cliente/compras/{sale_id}")
def obtener_ticket_compra_cliente(sale_id: str):
  try:
    ticket = db.obtener_ticket_compra_cliente(sale_id)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except Exception as exc:
    logger.exception("Error al obtener el ticket de compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el ticket.",
    )

  return ticket


@app.get("/api/vendedor/reportes/indicadores")
def obtener_indicadores_financieros():
  try:
    indicators = db.obtener_indicadores_financieros()
  except Exception as exc:
    logger.exception("Error al calcular indicadores financieros: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron calcular los indicadores financieros.",
    )

  report = Informe.desde_agregados_bd(
    ingresos_totales=float(indicators["ingresos_totales"]),
    costos_totales=float(indicators["costos_totales"]),
    alertas_stock_bajo=[],
    total_productos=int(indicators["total_productos"]),
    total_vendedores=int(indicators["total_vendedores"]),
    total_clientes=int(indicators["total_clientes"]),
    total_ventas=int(indicators["total_ventas"]),
    ticket_promedio=float(indicators["avg_ticket"]),
    productos_stock_bajo=int(indicators["productos_stock_bajo"]),
    productos_estancados=int(indicators["productos_estancados"]),
  )

  profit = report.margen_ganancia
  margin_percent = round((profit / float(indicators["ingresos_totales"]) * 100), 2) if float(indicators["ingresos_totales"]) > 0 else 0.0

  return {
    "total_products": report.total_productos,
    "total_vendors": report.total_vendedores,
    "total_clients": report.total_clientes,
    "total_sales": report.total_ventas,
    "revenue": round(float(indicators["ingresos_totales"]), 2),
    "total_cost": round(float(indicators["costos_totales"]), 2),
    "profit": round(profit, 2),
    "margin_percent": margin_percent,
    "avg_ticket": round(float(indicators["avg_ticket"]), 2),
    "low_stock_products": report.productos_stock_bajo,
    "stagnant_products": report.productos_estancados,
  }



# Nota: he renombrado las funciones del backend al español y eliminado aliases.
