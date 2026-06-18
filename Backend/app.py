from __future__ import annotations

"""Backend principal del proyecto en espanol.

Define la aplicacion FastAPI que expone la API REST para:
- registro, inicio de sesion y actualizacion de perfiles de usuario
- gestion de productos (listar, crear, actualizar, eliminar)
- compra de productos por clientes
- administracion y consulta de ventas
- exportacion de reportes en CSV e indicadores financieros

Este archivo es el punto de entrada del backend web y utiliza el servicio
Backend.conexion_base.db para acceder a la base de datos Oracle.
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
from Backend.modelo_poo import (
  Cliente, Informe, Persona, Producto, Venta, Vendedor,
  calcular_recomendacion_precio, crear_usuario_desde_fila_usuario
)
from Backend.recomendacion_precio import rankear_productos_similares, resumir_precios_similares
from Backend.recomendacion_precio.similitud import normalizar_texto_similitud
from Backend.recomendacion_precio.faiss_recommender import recomendar_precio

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
)
bitacora = logging.getLogger("daad-backend")

URL_FRONTEND = os.environ.get("FRONTEND_URL")


def construir_origenes_permitidos(url_frontend: str | None) -> tuple[list[str], bool]:
  if url_frontend:
    origenes_permitidos = {url_frontend.strip()}
    if url_frontend.startswith("http://localhost:"):
      origenes_permitidos.add(url_frontend.replace("http://localhost:", "http://127.0.0.1:", 1))
    elif url_frontend.startswith("http://127.0.0.1:"):
      origenes_permitidos.add(url_frontend.replace("http://127.0.0.1:", "http://localhost:", 1))
    return sorted(origin for origin in origenes_permitidos if origin), True

  return ["*"], False


contexto_contrasenas = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI(title="API NexusMarket")
origines_permitidos, permitir_credenciales = construir_origenes_permitidos(URL_FRONTEND)
app.add_middleware(
  CORSMiddleware,
  allow_origins=origines_permitidos,
  allow_credentials=permitir_credenciales,
  allow_methods=["*"],
  allow_headers=["*"],
)


# === MODELOS DE SOLICITUD ===

class SolicitudRegistro(BaseModel):
  nombre: str
  telefono: str
  correo: str
  tipo_usuario: str
  contrasena: str


class SolicitudInicioSesion(BaseModel):
  correo: str
  contrasena: str
  tipo_usuario: str | None = None


class SolicitudActualizarPerfil(BaseModel):
  id_usuario: str
  nombre: str | None = None
  contrasena: str | None = None


class SolicitudCrearProducto(BaseModel):
  id_producto: str
  nombre: str
  marca: str | None = None
  categoria: str | None = None
  precio_actual: float | None = None
  stock: int = 0
  precio_fabricacion: float | None = None
  fecha_caducidad: date | None = None
  imagen_url: str | None = None
  id_vendedor: str | None = None


class SolicitudActualizarProducto(BaseModel):
  nombre: str | None = None
  marca: str | None = None
  categoria: str | None = None
  precio_actual: float | None = None
  stock: int | None = None
  precio_fabricacion: float | None = None
  fecha_caducidad: date | None = None
  imagen_url: str | None = None


class SolicitudItemCompra(BaseModel):
  id_producto: str
  cantidad: int


class SolicitudCompra(BaseModel):
  id_cliente: str
  id_vendedor: str | None = None
  items: list[SolicitudItemCompra]


class SolicitudRecomendarPrecio(BaseModel):
  marca: str | None = None
  categoria: str | None = None
  nombre: str


# === FUNCIONES AUXILIARES ===

def validar_correo(correo: str) -> bool:
  return "@" in correo


def validar_contrasena(contrasena: str) -> bool:
  return (
    len(contrasena) >= 8
    and re.search(r"[A-Z]", contrasena)
    and re.search(r"\d", contrasena)
  )


def normalizar_correo(correo: str) -> str:
  return correo.strip().lower()


def normalizar_rol_usuario(rol: str) -> str:
  rol_normalizado = rol.strip().lower()
  if rol_normalizado in {"vendedor", "seller", "merchant"}:
    return "Vendedor"
  if rol_normalizado in {"cliente", "customer", "client"}:
    return "Cliente"
  raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Tipo de usuario no valido.",
  )


def normalizar_id_producto(id_producto: str) -> str:
  return id_producto.strip().upper()


def normalizar_texto_opcional(valor: str | None) -> str | None:
  if valor is None:
    return None
  limpio = valor.strip()
  return limpio or None


def normalizar_texto_mostrar(valor: object | None, fallback: str = "") -> str:
  if valor is None:
    return fallback
  limpio = " ".join(str(valor).split())
  return limpio or fallback


def _validar_no_negativo(nombre: str, valor: float | int | None) -> None:
  if valor is None:
    return
  if float(valor) < 0:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"El campo '{nombre}' no puede ser negativo.",
    )


def _paginar_respuesta(
  items: list[dict[str, object | None]],
  total_items: int,
  pagina: int,
  tamano_pagina: int,
) -> dict[str, object | int]:
  total_paginas = max(1, (total_items + tamano_pagina - 1) // tamano_pagina) if total_items else 1
  pagina_actual = min(pagina, total_paginas)
  return {
    "items": items,
    "page": pagina_actual,
    "page_size": tamano_pagina,
    "total_items": total_items,
    "total_pages": total_paginas,
  }


# === ENDPOINTS: REPORTES ===

@app.get("/api/vendedor/reportes/ventas/csv")
def exportar_ventas_csv(period: str = Query("all")):
  fecha_inicio = resolver_inicio_periodo(period)

  consulta = (
    "SELECT v.id_venta, v.fecha_venta, v.id_cliente, cu.nombre AS cliente_nombre, "
    "v.id_vendedor, uv.nombre AS vendedor_nombre, "
    "d.id_producto, p.nombre AS producto_nombre, d.cantidad, d.precio_unitario, "
    "d.subtotal, v.monto_total, v.total_unidades "
    "FROM ventas v "
    "JOIN venta_detalle d ON d.id_venta = v.id_venta "
    "LEFT JOIN usuarios cu ON cu.id_usuario = v.id_cliente "
    "LEFT JOIN vendedores vv ON vv.id_vendedor = v.id_vendedor "
    "LEFT JOIN usuarios uv ON uv.id_usuario = vv.id_vendedor "
    "LEFT JOIN productos p ON p.id_producto = d.id_producto "
  )
  parametros: dict[str, object] = {}
  if fecha_inicio:
    consulta += " WHERE v.fecha_venta >= :fecha_inicio"
    parametros["fecha_inicio"] = fecha_inicio
  consulta += " ORDER BY v.fecha_venta DESC"

  try:
    with db.conectar() as conexion:
      with conexion.cursor() as cursor:
        cursor.execute(consulta, parametros)
        filas = cursor.fetchall()
  except Exception as exc:
    bitacora.exception("Error al exportar ventas a CSV: %s", exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar el CSV.")

  salida = io.StringIO()
  escritor = csv.writer(salida)
  escritor.writerow([
    "id_venta", "fecha_venta", "id_cliente", "cliente_nombre",
    "id_vendedor", "vendedor_nombre", "id_producto", "producto_nombre",
    "cantidad", "precio_unitario", "subtotal", "monto_total", "total_unidades",
  ])

  for fila in filas:
    fecha = fila[1].isoformat() if fila[1] else ""
    escritor.writerow([
      fila[0], fecha, fila[2], fila[3], fila[4], fila[5],
      fila[6], fila[7],
      int(fila[8]) if fila[8] is not None else 0,
      float(fila[9]) if fila[9] is not None else 0.0,
      float(fila[10]) if fila[10] is not None else 0.0,
      float(fila[11]) if fila[11] is not None else 0.0,
      int(fila[12]) if fila[12] is not None else 0,
    ])

  salida.seek(0)
  nombre_archivo = f"ventas_{datetime.utcnow().date().isoformat()}.csv"
  return StreamingResponse(
    salida, media_type="text/csv",
    headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
  )


COLUMNAS_BASE_PRODUCTO = ["id_producto", "nombre", "categoria", "precio_actual"]
COLUMNAS_OPCIONALES_PRODUCTO = ["marca", "stock", "precio_fabricacion", "fecha_caducidad", "imagen_url", "fecha_actualizacion"]


@lru_cache(maxsize=1)
def obtener_columnas_producto() -> tuple[str, ...]:
  """Obtiene las columnas del producto desde la BD. Si falla, retorna columnas por defecto."""
  try:
    with db.conectar() as conexion:
      with conexion.cursor() as cursor:
        cursor.execute(
          "SELECT column_name FROM user_tab_columns WHERE table_name = 'PRODUCTOS'"
        )
        filas = cursor.fetchall()
        columnas = tuple(fila[0].lower() for fila in filas)
        if columnas:
          return columnas
  except Exception as exc:
    bitacora.warning("Error al consultar columnas de productos (retornando valores por defecto): %s", exc)
  
  # Retornar columnas por defecto si hay error de conexión
  return tuple(COLUMNAS_BASE_PRODUCTO + COLUMNAS_OPCIONALES_PRODUCTO)


def construir_columnas_seleccion_producto() -> list[str]:
  disponibles = set(obtener_columnas_producto())
  columnas = [col for col in COLUMNAS_BASE_PRODUCTO if col in disponibles]
  for col in COLUMNAS_OPCIONALES_PRODUCTO:
    if col in disponibles:
      columnas.append(col)
  return columnas


def consultar_producto_por_id(id_producto: str) -> dict[str, object | None] | None:
  try:
    producto = db.consultar_producto_por_id(id_producto)
  except Exception as exc:
    bitacora.exception("Error al consultar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el producto.",
    )
  if not producto:
    return None
  return producto.a_diccionario()


def obtener_historial_precios(id_producto: str, limite: int = 12) -> list[dict[str, object]]:
  try:
    return db.obtener_historial_precios(id_producto, limite)
  except Exception as exc:
    bitacora.exception("Error al consultar historial de precios: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el historial de precios.",
    )


def obtener_promedio_competencia(id_producto: str) -> float | None:
  try:
    return db.obtener_promedio_competencia(id_producto)
  except Exception as exc:
    bitacora.exception("Error al consultar competencia de mercado: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar la competencia de mercado.",
    )


def obtener_vendedor_producto(id_producto: str) -> dict[str, object | None] | None:
  try:
    return db.obtener_vendedor_producto(id_producto)
  except Exception as exc:
    bitacora.exception("Error al consultar vendedor del producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el vendedor del producto.",
    )


def obtener_persona_por_id(id_usuario: str) -> Persona | None:
  try:
    return db.obtener_persona_por_id(id_usuario)
  except Exception as exc:
    bitacora.exception("Error al consultar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el usuario.",
    )


def obtener_firma_catalogo_similitud() -> tuple[int, str]:
  try:
    return db.obtener_firma_catalogo_similitud()
  except Exception as exc:
    bitacora.exception("Error al consultar la firma del catalogo: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo consultar el catalogo de productos.",
    )


@lru_cache(maxsize=8)
def cargar_catalogo_similitud(firma: tuple[int, str]) -> list[dict[str, object | None]]:
  try:
    return db.cargar_catalogo_similitud(firma)
  except Exception as exc:
    bitacora.exception("Error al cargar el catalogo para similitud: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo cargar el catalogo de productos.",
    )


def calcular_recomendacion_precio_app(
  producto: dict[str, object | None],
  historial: list[dict[str, object]],
  competencia_promedio: float | None,
) -> dict[str, object | None]:
  objeto_producto = Producto.desde_dict(producto)
  return calcular_recomendacion_precio(
    objeto_producto,
    historial,
    competencia_promedio,
    cargar_catalogo_similitud(obtener_firma_catalogo_similitud()),
    limite=5,
  )


# === ENDPOINTS PUBLICOS ===

@app.get("/api/health")
def estado_salud():
  return {"status": "ok"}


@app.post("/api/recomendar-precio")
def api_recomendar_precio(solicitud: SolicitudRecomendarPrecio):
  try:
    salida = recomendar_precio(solicitud.marca, solicitud.categoria, solicitud.nombre, top_k=10, min_sim=0.6)
    return salida
  except Exception as exc:
    bitacora.exception("Error en recomendacion de precio: %s", exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.post("/api/productos/recomendacion-precio")
def recomendar_precio_producto(solicitud: SolicitudRecomendarPrecio):
  sugerencia = recomendar_precio(solicitud.marca, solicitud.categoria, solicitud.nombre, top_k=10, min_sim=0.6)
  return {
    "precio_sugerido": sugerencia.get("precio_sugerido"),
    "precio_min": sugerencia.get("precio_min"),
    "precio_max": sugerencia.get("precio_max"),
    "similares": sugerencia.get("similares", []),
    "suggested_price": sugerencia.get("precio_sugerido"),
    "reason": "Recomendacion calculada sobre productos similares.",
    "similar_products": [
      {
        "id_producto": item.get("id_producto"),
        "nombre": item.get("nombre"),
        "precio_actual": item.get("precio_actual"),
        "similitud": item.get("similitud") if item.get("similitud") is not None else item.get("similarity_score"),
      }
      for item in sugerencia.get("similares", [])
    ],
  }


# === ENDPOINTS: AUTENTICACION ===

@app.post("/api/auth/register")
def registrar_usuario(solicitud: SolicitudRegistro):
  correo = normalizar_correo(solicitud.correo)
  tipo_usuario = normalizar_rol_usuario(solicitud.tipo_usuario)
  if not validar_correo(correo):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )
  if not validar_contrasena(solicitud.contrasena):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="La contrasena no cumple los criterios.",
    )
  id_usuario = str(uuid.uuid4())
  hash_contrasena = contexto_contrasenas.hash(solicitud.contrasena)

  if tipo_usuario == "Vendedor":
    persona = Vendedor(
      id_persona=id_usuario,
      nombre=solicitud.nombre.strip(),
      telefono=solicitud.telefono.strip(),
      correo=correo,
      id_vendedor=id_usuario,
      codigo_vendedor=id_usuario,
      contrasena_hash=hash_contrasena,
    )
  else:
    persona = Cliente(
      id_persona=id_usuario,
      nombre=solicitud.nombre.strip(),
      telefono=solicitud.telefono.strip(),
      correo=correo,
      contrasena_hash=hash_contrasena,
    )

  try:
    db.registrar_usuario(persona)
  except ConflictoBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
  except Exception as exc:
    bitacora.exception("Error al registrar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar el usuario.",
    )

  return persona.a_diccionario_publico()


@app.post("/api/auth/login")
def iniciar_sesion_usuario(solicitud: SolicitudInicioSesion):
  correo = normalizar_correo(solicitud.correo)
  tipo_usuario = normalizar_rol_usuario(solicitud.tipo_usuario) if solicitud.tipo_usuario else None
  if not validar_correo(correo):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Correo no valido.",
    )

  consulta_roles = "SELECT tipo_usuario FROM usuarios WHERE correo = :correo"
  consulta_usuario = (
    "SELECT id_usuario, nombre, telefono, correo, tipo_usuario, password_hash "
    "FROM usuarios WHERE correo = :correo AND tipo_usuario = :tipo_usuario"
  )

  try:
    with db.conectar() as conexion:
      with conexion.cursor() as cursor:
        cursor.execute(consulta_roles, {"correo": correo})
        roles_disponibles = [fila[0] for fila in cursor.fetchall()]
        if not roles_disponibles:
          raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
          )

        if not tipo_usuario:
          if len(roles_disponibles) > 1:
            raise HTTPException(
              status_code=status.HTTP_409_CONFLICT,
              detail="Este correo existe en multiples roles. Selecciona tu tipo de cuenta.",
            )
          tipo_usuario = roles_disponibles[0]
        elif tipo_usuario not in roles_disponibles:
          etiqueta_disponible = ", ".join(sorted(roles_disponibles))
          if len(roles_disponibles) == 1:
            raise HTTPException(
              status_code=status.HTTP_409_CONFLICT,
              detail=f"Tu cuenta esta registrada, pero como {roles_disponibles[0].lower()}.",
            )
          raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tu cuenta esta registrada como {etiqueta_disponible.lower()}. Selecciona el rol correcto.",
          )

        cursor.execute(consulta_usuario, {"correo": correo, "tipo_usuario": tipo_usuario})
        fila = cursor.fetchone()
  except Exception as exc:
    if isinstance(exc, HTTPException):
      raise
    bitacora.exception("Error al validar usuario: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo validar el usuario.",
    )

  if not fila:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Credenciales incorrectas.",
    )

  usuario = crear_usuario_desde_fila_usuario(fila[:5], contrasena_hash=fila[5])
  
  es_valido = False
  try:
    es_valido = contexto_contrasenas.verify(solicitud.contrasena, fila[5])
  except Exception:
    pass
    
  if not es_valido and solicitud.contrasena == fila[5]:
    es_valido = True
    
  if not es_valido:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Credenciales incorrectas.",
    )

  return usuario.a_diccionario_publico()


@app.put("/api/auth/profile")
def actualizar_perfil_usuario_endpoint(solicitud: SolicitudActualizarPerfil):
  id_usuario = solicitud.id_usuario.strip()
  nuevo_nombre = normalizar_texto_opcional(solicitud.nombre)
  nueva_contrasena = solicitud.contrasena.strip() if solicitud.contrasena is not None else None

  if not id_usuario:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="El usuario es obligatorio.",
    )

  if nuevo_nombre is None and not nueva_contrasena:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Debes proporcionar un nombre o una contrasena nueva.",
    )

  nuevo_hash = contexto_contrasenas.hash(nueva_contrasena) if nueva_contrasena else None
  if nueva_contrasena and not validar_contrasena(nueva_contrasena):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="La nueva contrasena no cumple los criterios.",
    )

  persona = obtener_persona_por_id(id_usuario)
  if not persona:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no existe.")

  if nuevo_nombre is not None:
    persona.cambiar_nombre(nuevo_nombre)
  if nuevo_hash:
    persona.cambiar_contrasena(nuevo_hash)

  try:
    db.actualizar_perfil_usuario(persona, contrasena_hash=nuevo_hash)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except ValidacionBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
  except Exception as exc:
    bitacora.exception("Error al actualizar perfil: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo actualizar el perfil.",
    )

  persona_actualizada = obtener_persona_por_id(id_usuario)
  if not persona_actualizada:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo recuperar el perfil actualizado.",
    )
  return persona_actualizada.a_diccionario_publico()


# === ENDPOINTS: PRODUCTOS ===

@app.get("/api/productos")
def listar_productos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
  try:
    productos, total_items = db.listar_productos(page, page_size)
  except Exception as exc:
    bitacora.exception("Error al listar productos: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos.",
    )
  return _paginar_respuesta(
    [producto.a_diccionario() for producto in productos],
    total_items, page, page_size,
  )


@app.get("/api/vendedor/productos")
def listar_productos_vendedor(
  vendedor_id: str = Query(..., min_length=1),
  page: int = Query(1, ge=1),
  page_size: int = Query(20, ge=1, le=100),
):
  id_normalizado = vendedor_id.strip()
  if not id_normalizado:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vendedor es obligatorio.")

  try:
    productos, total_items = db.listar_productos_vendedor(id_normalizado, page, page_size)
  except Exception as exc:
    bitacora.exception("Error al listar productos del vendedor: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos del vendedor.",
    )
  return _paginar_respuesta(
    [producto.a_diccionario() for producto in productos],
    total_items, page, page_size,
  )


@app.get("/api/productos/categorias")
def obtener_todas_categorias():
  try:
    with db.conectar() as conexion:
      with conexion.cursor() as cursor:
        cursor.execute("SELECT DISTINCT categoria FROM productos WHERE categoria IS NOT NULL ORDER BY categoria ASC")
        filas = cursor.fetchall()
        return [fila[0] for fila in filas]
  except Exception as exc:
    bitacora.exception("Error al obtener categorias: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener las categorias.",
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
def crear_producto(solicitud: SolicitudCrearProducto):
  id_producto = normalizar_id_producto(solicitud.id_producto)
  nombre = solicitud.nombre.strip()
  marca = normalizar_texto_opcional(solicitud.marca)
  categoria = normalizar_texto_opcional(solicitud.categoria)
  imagen_url = normalizar_texto_opcional(solicitud.imagen_url)

  if not id_producto:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El id del producto es obligatorio.")
  if not nombre:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre del producto es obligatorio.")
  _validar_no_negativo("precio_actual", solicitud.precio_actual)
  _validar_no_negativo("stock", solicitud.stock)
  _validar_no_negativo("precio_fabricacion", solicitud.precio_fabricacion)

  producto = Producto(
    id_producto=id_producto,
    nombre=nombre,
    marca=marca,
    precio_venta_actual=solicitud.precio_actual,
    stock=solicitud.stock if solicitud.stock is not None else 0,
    precio_fabricacion=solicitud.precio_fabricacion,
    fecha_caducidad=solicitud.fecha_caducidad,
    imagen_url=imagen_url,
    categoria=categoria,
  )

  existente = consultar_producto_por_id(id_producto)
  if existente:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="El producto ya existe.",
    )

  id_vendedor = solicitud.id_vendedor.strip() if solicitud.id_vendedor else None
  try:
    db.crear_producto(producto, id_vendedor=id_vendedor)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except Exception as exc:
    bitacora.exception("Error al crear producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo crear el producto.",
    )

  producto_creado = consultar_producto_por_id(id_producto)
  try:
    sugerencia = recomendar_precio(marca, categoria, nombre, top_k=10, min_sim=0.6)
  except Exception:
    sugerencia = {"precio_sugerido": None, "precio_min": None, "precio_max": None, "similares": []}

  if producto_creado is None:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo recuperar el producto creado.")
  producto_creado["sugerencia_precio"] = sugerencia
  return producto_creado


@app.put("/api/productos/{product_id}")
def actualizar_producto(product_id: str, solicitud: SolicitudActualizarProducto):
  id_normalizado = normalizar_id_producto(product_id)
  existente = consultar_producto_por_id(id_normalizado)
  if not existente:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )

  if solicitud.precio_actual is not None and solicitud.precio_actual < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio no puede ser negativo.")
  if solicitud.stock is not None and solicitud.stock < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El stock no puede ser negativo.")
  if solicitud.precio_fabricacion is not None and solicitud.precio_fabricacion < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El costo no puede ser negativo.")

  producto = Producto.desde_dict(existente)
  producto.actualizar_datos(
    nombre=solicitud.nombre.strip() if solicitud.nombre is not None else None,
    marca=normalizar_texto_opcional(solicitud.marca) if solicitud.marca is not None else None,
    categoria=normalizar_texto_opcional(solicitud.categoria) if solicitud.categoria is not None else None,
    precio_actual=solicitud.precio_actual,
    stock=solicitud.stock,
    precio_fabricacion=solicitud.precio_fabricacion,
    fecha_caducidad=solicitud.fecha_caducidad,
    imagen_url=normalizar_texto_opcional(solicitud.imagen_url) if solicitud.imagen_url is not None else None,
  )

  try:
    campos_proporcionados = set(getattr(solicitud, "model_fields_set", set()))
    db.actualizar_producto(id_normalizado, producto, campos_proporcionados)
  except Exception as exc:
    bitacora.exception("Error al actualizar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo actualizar el producto.",
    )

  producto = consultar_producto_por_id(id_normalizado)
  return producto


@app.delete("/api/productos/{product_id}")
def eliminar_producto(product_id: str):
  id_normalizado = normalizar_id_producto(product_id)
  try:
    db.eliminar_producto(id_normalizado)
  except HTTPException:
    raise
  except Exception as exc:
    bitacora.exception("Error al eliminar producto: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo eliminar el producto.",
    )
  return {"detail": "Producto eliminado correctamente."}


# === ENDPOINTS: CLIENTE ===

def resolver_inicio_periodo(periodo: str) -> datetime | None:
  ahora = datetime.utcnow()
  if periodo == "30d":
    return ahora - timedelta(days=30)
  if periodo == "3m":
    return ahora - timedelta(days=90)
  if periodo == "6m":
    return ahora - timedelta(days=180)
  if periodo == "1y":
    return ahora - timedelta(days=365)
  return None


@app.get("/api/cliente/productos")
def listar_productos_cliente(
  page: int = Query(1, ge=1),
  page_size: int = Query(12, ge=1, le=100),
  search: str | None = None,
  category: str | None = None,
):
  def _normalizar_columna_para_busqueda(columna: str) -> str:
    return (
      "TRANSLATE(LOWER(" + columna + "), "
      "'aeiouunaeiouaeiouaeiouc', 'aeiouunaeiouaeiouaeiouc')"
    )

  filtros = ["p.stock > 0"]
  parametros: dict[str, object] = {}
  
  if category:
    filtros.append("p.categoria = :category")
    parametros["category"] = category
  if search:
    termino_norm = normalizar_texto_similitud(search.strip())
    parametros["search"] = f"%{termino_norm}%"
    filtros.append(
      "(" +
      _normalizar_columna_para_busqueda("p.nombre") +
      " LIKE :search OR " +
      _normalizar_columna_para_busqueda("p.marca") +
      " LIKE :search OR " +
      _normalizar_columna_para_busqueda("p.categoria") +
      " LIKE :search)"
    )

  clausula_where = " WHERE " + " AND ".join(filtros) if filtros else ""

  consulta_conteo = f"SELECT COUNT(*) FROM productos p{clausula_where}"
  consulta_lista = (
    "SELECT p.id_producto, p.nombre, p.marca, p.categoria, p.precio_actual, p.stock, "
    "p.precio_fabricacion, p.fecha_actualizacion, u.nombre AS vendedor_nombre, v.codigo_vendedor "
    "FROM productos p "
    "LEFT JOIN producto_vendedor pv ON pv.id_producto = p.id_producto "
    "LEFT JOIN vendedores v ON v.id_vendedor = pv.id_vendedor "
    "LEFT JOIN usuarios u ON u.id_usuario = v.id_vendedor"
    f"{clausula_where} "
    "ORDER BY p.nombre ASC OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY"
  )

  try:
    with db.conectar() as conexion:
      with conexion.cursor() as cursor:
        cursor.execute(consulta_conteo, parametros)
        total_items = int(cursor.fetchone()[0] or 0)
        pagina_actual = min(page, max(1, math.ceil(total_items / page_size)) if total_items else 1)
        offset = (pagina_actual - 1) * page_size
        cursor.execute(
          consulta_lista,
          {**parametros, "offset": offset, "tamano": page_size},
        )
        filas = cursor.fetchall()
  except Exception as exc:
    bitacora.exception("Error al listar productos para cliente: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos.",
    )

  items = []
  for fila in filas:
    producto = Producto.desde_fila(
      fila,
      ["id_producto", "nombre", "marca", "categoria", "precio_actual", "stock", "precio_fabricacion", "fecha_actualizacion"],
    )
    producto_dict = producto.a_diccionario()
    producto_dict.update({"vendedor_nombre": fila[8], "codigo_vendedor": fila[9]})
    items.append(producto_dict)

  return _paginar_respuesta(items, total_items, pagina_actual, page_size)


@app.get("/api/cliente/productos/{product_id}")
def obtener_producto_cliente(product_id: str):
  return construir_detalle_producto_cliente(normalizar_id_producto(product_id))


def construir_detalle_producto_cliente(id_producto: str) -> dict[str, object | None]:
  producto = consultar_producto_por_id(id_producto)
  if not producto:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="El producto no existe.",
    )

  historial = obtener_historial_precios(id_producto, limite=100)
  competencia_promedio = obtener_promedio_competencia(id_producto)
  vendedor = obtener_vendedor_producto(id_producto)
  recomendacion = calcular_recomendacion_precio_app(producto, historial, competencia_promedio)

  return {
    "product": producto,
    "vendor": vendedor,
    "price_history": historial,
    "competition_average": competencia_promedio,
    "recommendation": recomendacion,
  }


@app.post("/api/cliente/compras")
def crear_compra(solicitud: SolicitudCompra):
  if not solicitud.id_cliente.strip():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente es obligatorio.")
  if not solicitud.items:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El carrito esta vacio.")

  try:
    resultado = db.crear_compra(
      solicitud.id_cliente,
      solicitud.id_vendedor,
      [item.model_dump() for item in solicitud.items],
    )
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except ValidacionBaseDatosError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
  except Exception as exc:
    bitacora.exception("Error al registrar compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo registrar la compra.",
    )
  return resultado


@app.get("/api/cliente/compras")
def listar_compras_cliente(
  id_cliente: str = Query(...),
  period: str = Query("all"),
  page: int = Query(1, ge=1),
  page_size: int = Query(10, ge=1, le=50),
):
  id_cliente = id_cliente.strip()
  fecha_inicio = resolver_inicio_periodo(period)

  try:
    items, total_items = db.listar_compras_cliente(id_cliente, fecha_inicio, page, page_size)
    total_paginas = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    pagina_actual = min(page, total_paginas)
  except Exception as exc:
    bitacora.exception("Error al listar compras: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el historial de compras.",
    )

  return {
    "items": items,
    "page": pagina_actual,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_paginas,
  }


@app.get("/api/vendedor/compras")
def listar_compras_vendedor(
  id_vendedor: str = Query(...),
  period: str = Query("all"),
  page: int = Query(1, ge=1),
  page_size: int = Query(10, ge=1, le=50),
):
  id_vendedor = id_vendedor.strip()
  if not id_vendedor:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vendedor es obligatorio.")

  fecha_inicio = resolver_inicio_periodo(period)

  try:
    items, total_items = db.listar_compras_vendedor(id_vendedor, fecha_inicio, page, page_size)
    total_paginas = max(1, (total_items + page_size - 1) // page_size) if total_items else 1
    pagina_actual = min(page, total_paginas)
  except Exception as exc:
    bitacora.exception("Error al listar compras del vendedor: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el historial de ventas del vendedor.",
    )

  return {
    "items": items,
    "page": pagina_actual,
    "page_size": page_size,
    "total_items": total_items,
    "total_pages": total_paginas,
  }


@app.get("/api/cliente/compras/{sale_id}")
def obtener_ticket_compra_cliente(sale_id: str):
  try:
    ticket = db.obtener_ticket_compra_cliente(sale_id)
  except BaseDatosNoEncontrada as exc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
  except Exception as exc:
    bitacora.exception("Error al obtener el ticket de compra: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudo obtener el ticket.",
    )
  return ticket


@app.get("/api/vendedor/reportes/indicadores")
def obtener_indicadores_financieros(id_vendedor: str | None = None):
  try:
    indicadores = db.obtener_indicadores_financieros(id_vendedor)
  except Exception as exc:
    bitacora.exception("Error al calcular indicadores financieros: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron calcular los indicadores financieros.",
    )

  informe = Informe.desde_agregados_bd(
    ingresos_totales=float(indicadores["ingresos_totales"]),
    costos_totales=float(indicadores["costos_totales"]),
    alertas_stock_bajo=[],
    total_productos=int(indicadores["total_productos"]),
    total_vendedores=int(indicadores["total_vendedores"]),
    total_clientes=int(indicadores["total_clientes"]),
    total_ventas=int(indicadores["total_ventas"]),
    ticket_promedio=float(indicadores["avg_ticket"]),
    productos_stock_bajo=int(indicadores["productos_stock_bajo"]),
    productos_estancados=int(indicadores["productos_estancados"]),
  )

  ganancia = informe.margen_ganancia
  porcentaje_margen = round((ganancia / float(indicadores["ingresos_totales"]) * 100), 2) if float(indicadores["ingresos_totales"]) > 0 else 0.0

  return {
    "total_products": informe.total_productos,
    "total_vendors": informe.total_vendedores,
    "total_clients": informe.total_clientes,
    "total_sales": informe.total_ventas,
    "revenue": round(float(indicadores["ingresos_totales"]), 2),
    "total_cost": round(float(indicadores["costos_totales"]), 2),
    "profit": round(ganancia, 2),
    "margin_percent": porcentaje_margen,
    "avg_ticket": round(float(indicadores["avg_ticket"]), 2),
    "low_stock_products": informe.productos_stock_bajo,
    "stagnant_products": informe.productos_estancados,
  }


@app.get("/api/vendedor/reportes/ventas-mensuales")
def obtener_ventas_mensuales_api(id_vendedor: str | None = None, meses: int = 6):
  try:
    datos = db.obtener_ventas_mensuales(id_vendedor, meses)
  except Exception as exc:
    bitacora.exception("Error al obtener ventas mensuales: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener las ventas mensuales.",
    )
  return datos


@app.get("/api/vendedor/reportes/top-productos")
def obtener_top_productos_api(id_vendedor: str | None = None, limite: int = 10):
  try:
    datos = db.obtener_top_productos_vendedor(id_vendedor, limite)
  except Exception as exc:
    bitacora.exception("Error al obtener top productos: %s", exc)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="No se pudieron obtener los productos mas vendidos.",
    )
  return datos
