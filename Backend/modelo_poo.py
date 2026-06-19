from __future__ import annotations

from abc import ABC
from datetime import datetime, timedelta
import math
from typing import Any, Iterable, Sequence

import numpy as np

from Backend.recomendacion_precio import obtener_recomendador


# ──────────────────────────────────────────────────────────────────────────────
# Funciones auxiliares privadas
# ──────────────────────────────────────────────────────────────────────────────

def _limpiar_texto(valor: object | None) -> str:
  if valor is None:
    return ""
  return " ".join(str(valor).split())


def _normalizar_correo(correo: str) -> str:
  return _limpiar_texto(correo).lower()


def _normalizar_float(valor: object | None) -> float | None:
  if valor is None or valor == "":
    return None
  return float(valor)


def _validar_nombre(nombre: str) -> str:
  nombre_limpio = _limpiar_texto(nombre)
  if not nombre_limpio:
    raise ValueError("El nombre no puede estar vacio.")
  return nombre_limpio


def _validar_contrasena(contrasena: str) -> str:
  """Valida que la contrasena cumpla los criterios minimos."""
  pass_limpio = _limpiar_texto(contrasena)
  if len(pass_limpio) < 8:
    raise ValueError("La contrasena debe tener al menos 8 caracteres.")
  if not any(caracter.isupper() for caracter in pass_limpio):
    raise ValueError("La contrasena debe incluir una mayuscula.")
  if not any(caracter.isdigit() for caracter in pass_limpio):
    raise ValueError("La contrasena debe incluir un numero.")
  return pass_limpio


def _producto_a_diccionario(producto: Producto | dict[str, object | None]) -> dict[str, object | None]:
  """Convierte un Producto o diccionario a diccionario estandar."""
  if isinstance(producto, Producto):
    return producto.a_diccionario()
  return dict(producto)


def _parse_fecha_historica(valor: object | None) -> datetime:
  """Convierte un valor de fecha a datetime."""
  if isinstance(valor, datetime):
    return valor
  from datetime import date
  if isinstance(valor, date):
    return datetime.combine(valor, datetime.min.time())
  if valor is None:
    return datetime.utcnow()
  texto = _limpiar_texto(valor)
  if not texto:
    return datetime.utcnow()
  try:
    return datetime.fromisoformat(texto)
  except ValueError:
    return datetime.utcnow()


# ──────────────────────────────────────────────────────────────────────────────
# Persona — clase base abstracta
# ──────────────────────────────────────────────────────────────────────────────

class Persona(ABC):
  """Clase base abstracta para usuarios del sistema."""

  def __init__(
    self,
    id_persona: str,
    nombre: str,
    telefono: str | None,
    correo: str,
    tipo_usuario: str,
    contrasena_hash: str | None = None,
  ):
    if type(self) is Persona:
      raise TypeError("No se puede instanciar la clase abstracta Persona directamente.")
    self.id = _limpiar_texto(id_persona)
    self.nombre = _validar_nombre(nombre)
    self.telefono = _limpiar_texto(telefono)
    self.correo = _normalizar_correo(correo)
    self.tipo_usuario = _limpiar_texto(tipo_usuario)
    self.contrasena_hash = _limpiar_texto(contrasena_hash) if contrasena_hash is not None else None

  def cambiar_nombre(self, nuevo_nombre: str) -> None:
    self.nombre = _validar_nombre(nuevo_nombre)

  def cambiar_contrasena(self, nueva_contrasena_hash: str) -> None:
    contrasena_hash = _limpiar_texto(nueva_contrasena_hash)
    if not contrasena_hash:
      raise ValueError("El hash de la contrasena no puede estar vacio.")
    self.contrasena_hash = contrasena_hash

  def actualizar_perfil(
    self,
    nombre: str | None = None,
    contrasena_hash: str | None = None,
  ) -> None:
    """Actualiza nombre y/o contrasena del usuario."""
    if nombre is not None:
      self.cambiar_nombre(nombre)
    if contrasena_hash is not None:
      self.cambiar_contrasena(contrasena_hash)

  def a_diccionario_publico(self) -> dict[str, object | None]:
    """Devuelve informacion publica del usuario (sin hash ni datos sensibles)."""
    return {
      "id": self.id,
      "nombre": self.nombre,
      "correo": self.correo,
      "tipo_usuario": self.tipo_usuario,
    }

  def a_fila(self) -> dict[str, object | None]:
    """Devuelve los datos del usuario para insertar en la base de datos."""
    return {
      "id_usuario": self.id,
      "nombre": self.nombre,
      "telefono": self.telefono or None,
      "correo": self.correo,
      "tipo_usuario": self.tipo_usuario,
      "password_hash": self.contrasena_hash,
    }

  @classmethod
  def desde_fila_usuario(
    cls,
    fila: Sequence[object],
    contrasena_hash: str | None = None,
  ) -> "Persona":
    """Crea una Persona (Cliente o Vendedor) desde una fila de la BD."""
    id_usuario = str(fila[0])
    nombre = str(fila[1])
    telefono = fila[2] if len(fila) > 2 else None
    correo = str(fila[3])
    tipo_usuario = str(fila[4])

    if tipo_usuario.strip().lower() == "vendedor":
      return Vendedor(
        id_persona=id_usuario,
        nombre=nombre,
        telefono=telefono if telefono is not None else None,
        correo=correo,
        id_vendedor=id_usuario,
        codigo_vendedor=id_usuario,
        contrasena_hash=contrasena_hash,
      )

    return Cliente(
      id_persona=id_usuario,
      nombre=nombre,
      telefono=telefono if telefono is not None else None,
      correo=correo,
      contrasena_hash=contrasena_hash,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Producto
# ──────────────────────────────────────────────────────────────────────────────

class Producto:
  """Entidad de inventario y precio."""

  def __init__(
    self,
    id_producto: str,
    nombre: str,
    marca: str | None,
    precio_venta_actual: float | None,
    stock: int,
    precio_fabricacion: float | None,
    imagen_url: str | None = None,
    fecha_actualizacion: datetime | None = None,
    categoria: str | None = None,
  ):
    self.id_producto = _limpiar_texto(id_producto)
    self.nombre = _validar_nombre(nombre)
    self.marca = _limpiar_texto(marca)
    self.categoria = _limpiar_texto(categoria)
    self.precio_actual = float(precio_venta_actual) if precio_venta_actual is not None else None
    self.stock = int(stock)
    self.precio_fabricacion = float(precio_fabricacion) if precio_fabricacion is not None else None
    self.imagen_url = _limpiar_texto(imagen_url) or None
    self.fecha_actualizacion = fecha_actualizacion

  @classmethod
  def desde_dict(cls, datos: dict[str, object | None]) -> "Producto":
    """Crea un Producto desde un diccionario."""
    return cls(
      id_producto=str(datos.get("id_producto") or ""),
      nombre=str(datos.get("nombre") or ""),
      marca=datos.get("marca") if datos.get("marca") is not None else None,
      precio_venta_actual=_normalizar_float(datos.get("precio_actual")),
      stock=int(datos.get("stock") or 0),
      precio_fabricacion=_normalizar_float(datos.get("precio_fabricacion")),
      imagen_url=datos.get("imagen_url") if datos.get("imagen_url") is not None else None,
      fecha_actualizacion=_parse_fecha_historica(datos.get("fecha_actualizacion")) if datos.get("fecha_actualizacion") else None,
      categoria=datos.get("categoria") if datos.get("categoria") is not None else None,
    )

  @classmethod
  def desde_fila(cls, fila: Sequence[object], columnas: Sequence[str]) -> "Producto":
    """Crea un Producto desde una fila de resultados SQL."""
    datos = dict(zip(columnas, fila))
    return cls.desde_dict(datos)

  def cambiar_precio(self, nuevo_precio: float) -> None:
    precio_limpio = float(nuevo_precio)
    if precio_limpio < 0:
      raise ValueError("El precio no puede ser negativo.")
    self.precio_actual = round(precio_limpio, 2)

  def actualizar_stock(self, nuevo_stock: int) -> None:
    stock_limpio = int(nuevo_stock)
    if stock_limpio < 0:
      raise ValueError("El stock no puede ser negativo.")
    self.stock = stock_limpio

  def a_diccionario(self) -> dict[str, object | None]:
    return {
      "id_producto": self.id_producto,
      "nombre": self.nombre,
      "marca": self.marca or None,
      "categoria": self.categoria or None,
      "precio_actual": self.precio_actual,
      "stock": self.stock,
      "precio_fabricacion": self.precio_fabricacion,
      "imagen_url": self.imagen_url,
      "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
    }

  def a_fila(self) -> dict[str, object | None]:
    return {
      "id_producto": self.id_producto,
      "nombre": self.nombre,
      "marca": self.marca or None,
      "categoria": self.categoria or None,
      "precio_actual": self.precio_actual,
      "stock": self.stock,
      "precio_fabricacion": self.precio_fabricacion,
      "imagen_url": self.imagen_url,
      "fecha_actualizacion": self.fecha_actualizacion,
    }

  def actualizar_datos(
    self,
    nombre: str | None = None,
    marca: str | None = None,
    categoria: str | None = None,
    precio_actual: float | None = None,
    stock: int | None = None,
    precio_fabricacion: float | None = None,
    fecha_caducidad: Any = None,
    imagen_url: str | None = None,
  ) -> None:
    """Actualiza los datos del producto."""
    if nombre is not None:
      self.nombre = _validar_nombre(nombre)
    if marca is not None:
      self.marca = _limpiar_texto(marca)
    if categoria is not None:
      self.categoria = _limpiar_texto(categoria)
    if precio_actual is not None:
      self.cambiar_precio(precio_actual)
    if stock is not None:
      self.actualizar_stock(stock)
    if precio_fabricacion is not None:
      precio_fab_limpio = float(precio_fabricacion)
      if precio_fab_limpio < 0:
        raise ValueError("El costo no puede ser negativo.")
      self.precio_fabricacion = precio_fab_limpio
    if imagen_url is not None:
      self.imagen_url = _limpiar_texto(imagen_url) or None
    self.fecha_actualizacion = datetime.utcnow()



# ──────────────────────────────────────────────────────────────────────────────
# Venta
# ──────────────────────────────────────────────────────────────────────────────

class Venta:
  """Registro de una transaccion comercial."""

  def __init__(
    self,
    id_venta: str,
    producto: Producto,
    cantidad: int,
    fecha_venta: datetime,
    total_pagado: float,
  ):
    self.id_venta = _limpiar_texto(id_venta)
    self.producto = producto
    self.cantidad = int(cantidad)
    self.fecha_venta = fecha_venta
    self.total_pagado = float(total_pagado)

  @property
  def subtotal_unitario(self) -> float | None:
    if self.cantidad <= 0:
      return None
    return round(self.total_pagado / self.cantidad, 2)

  def a_diccionario(self) -> dict[str, object | None]:
    return {
      "id_venta": self.id_venta,
      "producto": self.producto.a_diccionario(),
      "cantidad": self.cantidad,
      "fecha_venta": self.fecha_venta.isoformat() if hasattr(self.fecha_venta, "isoformat") else str(self.fecha_venta),
      "total_pagado": self.total_pagado,
    }

  def a_fila(self) -> dict[str, object | None]:
    return {
      "id_venta": self.id_venta,
      "id_producto": self.producto.id_producto,
      "cantidad": self.cantidad,
      "fecha_venta": self.fecha_venta,
      "precio_unitario": self.subtotal_unitario,
      "subtotal": self.total_pagado,
    }

  @classmethod
  def desde_detalle(
    cls,
    id_venta: str,
    producto: Producto,
    cantidad: int,
    fecha_venta: datetime | None,
    precio_unitario: float,
  ) -> "Venta":
    fecha = fecha_venta or datetime.utcnow()
    return cls(
      id_venta=id_venta,
      producto=producto,
      cantidad=cantidad,
      fecha_venta=fecha,
      total_pagado=round(float(precio_unitario) * int(cantidad), 2),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Informe
# ──────────────────────────────────────────────────────────────────────────────

class Informe:
  """Salida agregada para reportes financieros e indicadores del sistema."""

  def __init__(
    self,
    ingresos_totales: float,
    costos_totales: float,
    margen_ganancia: float,
    alertas_stock_bajo: Sequence[Producto],
    total_productos: int = 0,
    total_vendedores: int = 0,
    total_clientes: int = 0,
    total_ventas: int = 0,
    productos_stock_bajo: int = 0,
    productos_estancados: int = 0,
  ):
    self.ingresos_totales = float(ingresos_totales)
    self.costos_totales = float(costos_totales)
    self.margen_ganancia = float(margen_ganancia)
    self.alertas_stock_bajo = list(alertas_stock_bajo)
    self.total_productos = int(total_productos)
    self.total_vendedores = int(total_vendedores)
    self.total_clientes = int(total_clientes)
    self.total_ventas = int(total_ventas)
    self.productos_stock_bajo = int(productos_stock_bajo)
    self.productos_estancados = int(productos_estancados)

  @classmethod
  def desde_agregados_bd(
    cls,
    ingresos_totales: float,
    costos_totales: float,
    alertas_stock_bajo: Sequence[Producto],
    total_productos: int = 0,
    total_vendedores: int = 0,
    total_clientes: int = 0,
    total_ventas: int = 0,
    productos_stock_bajo: int = 0,
    productos_estancados: int = 0,
  ) -> "Informe":
    """Construye un Informe directamente a partir de agregados de base de datos."""
    margen = float(ingresos_totales) - float(costos_totales)
    return cls(
      ingresos_totales=ingresos_totales,
      costos_totales=costos_totales,
      margen_ganancia=margen,
      alertas_stock_bajo=alertas_stock_bajo,
      total_productos=total_productos,
      total_vendedores=total_vendedores,
      total_clientes=total_clientes,
      total_ventas=total_ventas,
      productos_stock_bajo=productos_stock_bajo,
      productos_estancados=productos_estancados,
    )

  def a_diccionario(self) -> dict[str, object | None]:
    return {
      "ingresos_totales": self.ingresos_totales,
      "costos_totales": self.costos_totales,
      "margen_ganancia": self.margen_ganancia,
      "alertas_stock_bajo": [producto.a_diccionario() for producto in self.alertas_stock_bajo],
      "total_productos": self.total_productos,
      "total_vendedores": self.total_vendedores,
      "total_clientes": self.total_clientes,
      "total_ventas": self.total_ventas,
      "productos_stock_bajo": self.productos_stock_bajo,
      "productos_estancados": self.productos_estancados,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Cliente
# ──────────────────────────────────────────────────────────────────────────────

class Cliente(Persona):
  """Rol de consumidor con capacidad de compras."""

  def __init__(
    self,
    id_persona: str,
    nombre: str,
    telefono: str | None,
    correo: str,
    historial_compras: Sequence[Venta] | None = None,
    contrasena_hash: str | None = None,
  ):
    super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Cliente", contrasena_hash=contrasena_hash)
    self.historial_compras = list(historial_compras or [])

  def registrar_compra(self, venta: Venta) -> None:
    self.historial_compras.append(venta)


# ──────────────────────────────────────────────────────────────────────────────
# Vendedor
# ──────────────────────────────────────────────────────────────────────────────

class Vendedor(Persona):
  """Rol operativo con acceso a ventas y precios."""

  def __init__(
    self,
    id_persona: str,
    nombre: str,
    telefono: str | None,
    correo: str,
    id_vendedor: str,
    codigo_vendedor: str | None = None,
    especialidad: str | None = None,
    objetivo_ventas: float | None = None,
    contrasena_hash: str | None = None,
  ):
    super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Vendedor", contrasena_hash=contrasena_hash)
    self.id_vendedor = _limpiar_texto(id_vendedor)
    self.codigo_vendedor = _limpiar_texto(codigo_vendedor) or self.id_vendedor
    self.especialidad = _limpiar_texto(especialidad)
    self.objetivo_ventas = float(objetivo_ventas) if objetivo_ventas is not None else 0.0

  def vender_producto(
    self,
    producto: Producto,
    cantidad: int,
    fecha_venta: datetime | None = None,
    total_pagado: float | None = None,
    id_venta: str | None = None,
  ) -> Venta:
    """Registra la venta de un producto, descontando stock."""
    if cantidad <= 0:
      raise ValueError("La cantidad debe ser mayor que cero.")
    if producto.stock < cantidad:
      raise ValueError("No hay stock suficiente para completar la venta.")
    producto.actualizar_stock(producto.stock - cantidad)
    fecha = fecha_venta or datetime.utcnow()
    total = total_pagado if total_pagado is not None else float((producto.precio_actual or 0) * cantidad)
    return Venta(
      id_venta=id_venta or f"VENTA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
      producto=producto,
      cantidad=cantidad,
      fecha_venta=fecha,
      total_pagado=round(float(total), 2),
    )

  def a_fila(self) -> dict[str, object | None]:
    """Serializa el vendedor incluyendo campos propios de la tabla vendedores."""
    base = super().a_fila()
    base.update({
      "id_vendedor": self.id_vendedor,
      "codigo_vendedor": self.codigo_vendedor,
      "especialidad": self.especialidad or None,
      "objetivo_ventas": self.objetivo_ventas,
    })
    return base

  def a_diccionario_vendedor(self) -> dict[str, object | None]:
    """Diccionario publico con datos del vendedor para respuestas de API."""
    return {
      "id_vendedor": self.id_vendedor,
      "nombre_vendedor": self.nombre,
      "codigo_vendedor": self.codigo_vendedor,
      "especialidad": self.especialidad or None,
    }

  @classmethod
  def desde_fila_vendedor(
    cls,
    fila_usuario: Sequence[object],
    codigo_vendedor: str | None = None,
    especialidad: str | None = None,
    objetivo_ventas: float | None = None,
    contrasena_hash: str | None = None,
  ) -> "Vendedor":
    """Construye un Vendedor a partir de una fila de la tabla usuarios
    mas datos opcionales de la tabla vendedores."""
    id_usuario = str(fila_usuario[0])
    nombre = str(fila_usuario[1])
    telefono = fila_usuario[2] if len(fila_usuario) > 2 else None
    correo = str(fila_usuario[3]) if len(fila_usuario) > 3 else ""
    return cls(
      id_persona=id_usuario,
      nombre=nombre,
      telefono=telefono,
      correo=correo,
      id_vendedor=id_usuario,
      codigo_vendedor=codigo_vendedor or id_usuario,
      especialidad=especialidad,
      objetivo_ventas=objetivo_ventas,
      contrasena_hash=contrasena_hash,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Función pública de construcción de venta por item
# ──────────────────────────────────────────────────────────────────────────────

def crear_venta_por_item(
  cliente: Cliente | None,
  vendedor: Vendedor | None,
  id_venta: str,
  id_producto: str,
  nombre: str,
  marca: str | None,
  precio_actual: float | None,
  stock_actual: int,
  precio_fabricacion: float | None,
  cantidad: int,
  fecha_venta: datetime | None = None,
) -> tuple[Venta, dict[str, object | None], int, float, float | None]:
  """Construye el objeto Venta y el detalle desde los datos del producto."""
  if cantidad <= 0:
    raise ValueError("La cantidad debe ser mayor que cero.")

  producto = Producto(
    id_producto=id_producto,
    nombre=nombre,
    marca=marca,
    precio_venta_actual=precio_actual,
    stock=stock_actual,
    precio_fabricacion=precio_fabricacion,
  )

  if producto.stock < cantidad:
    raise ValueError("No hay stock suficiente para completar la venta.")

  producto.actualizar_stock(producto.stock - cantidad)
  precio_unitario = float(precio_actual or 0.0)
  subtotal = round(precio_unitario * cantidad, 2)
  ganancia = None
  if precio_fabricacion is not None:
    ganancia = round((precio_unitario - float(precio_fabricacion)) * cantidad, 2)

  if vendedor is not None:
    venta = vendedor.vender_producto(
      producto,
      cantidad,
      fecha_venta=fecha_venta,
      total_pagado=subtotal,
      id_venta=id_venta,
    )
  else:
    venta = Venta.desde_detalle(
      id_venta=id_venta,
      producto=producto,
      cantidad=cantidad,
      fecha_venta=fecha_venta,
      precio_unitario=precio_unitario,
    )

  if cliente is not None:
    cliente.registrar_compra(venta)

  detalle = {
    "id_producto": id_producto,
    "cantidad": cantidad,
    "precio_unitario": precio_unitario,
    "costo_unitario": float(precio_fabricacion) if precio_fabricacion is not None else None,
    "subtotal": subtotal,
    "margen_unitario": round(precio_unitario - float(precio_fabricacion), 2) if precio_fabricacion is not None else None,
  }

  return venta, detalle, producto.stock, subtotal, ganancia


# ──────────────────────────────────────────────────────────────────────────────
# Función de recomendación de precio completa (usada en detalle de producto)
# ──────────────────────────────────────────────────────────────────────────────

def calcular_recomendacion_precio(
  producto: Producto | dict[str, object | None],
  historial: Iterable[dict[str, object]] | None,
  competencia_promedio: float | None = None,
  catalogo: list[dict[str, object | None]] | None = None,
  limite: int = 5,
) -> dict[str, object | None]:
  """Calcula una recomendacion de precio completa usando historial y similitud TF-IDF.

  Analiza el precio actual contra el historial y el mercado comparable
  para generar una senial de compra, precio sugerido y puntuacion vectorial.
  La similitud de productos se delega al RecomendadorPrecio (TF-IDF).

  Argumentos:
    producto: Producto a analizar (objeto o dict).
    historial: Lista de diccionarios con 'fecha' y 'precio'.
    competencia_promedio: Ignorado. Se conserva por compatibilidad de firma.
    catalogo: Ignorado. Se conserva por compatibilidad de firma.
    limite: Numero maximo de similares a considerar.

  Retorna:
    Dict con signal, suggested_price, reason, margin_percent,
    market_reference_*, trend_label, estimated_buy_date,
    buy_now, buy_reason, similar_products.
  """
  producto_dict = _producto_a_diccionario(producto)
  precio_actual = float(producto_dict.get("precio_actual") or 0)
  precio_costo = float(producto_dict.get("precio_fabricacion") or 0)
  stock = int(producto_dict.get("stock") or 0)

  # Obtener productos similares via TF-IDF
  try:
    recomendador = obtener_recomendador()
    resultado_similitud = recomendador.recomendar(
      nombre=str(producto_dict.get("nombre") or ""),
      marca=producto_dict.get("marca"),
      categoria=producto_dict.get("categoria"),
      precio_actual=precio_actual or None,
      id_producto=str(producto_dict.get("id_producto") or "") or None,
    )
    productos_similares = [
      {
        "id_producto": p.get("id_producto"),
        "nombre": p.get("nombre"),
        "marca": p.get("marca"),
        "categoria": p.get("categoria"),
        "precio_actual": p.get("precio"),
        "similarity_score": p.get("similitud"),
      }
      for p in resultado_similitud.get("productos_utilizados", [])
    ][:limite]
    referencia_mercado = resultado_similitud.get("precio_recomendado")
    piso_mercado = min((float(p["precio_actual"]) for p in productos_similares if p.get("precio_actual")), default=None)
    techo_mercado = max((float(p["precio_actual"]) for p in productos_similares if p.get("precio_actual")), default=None)
  except Exception:
    productos_similares = []
    referencia_mercado = None
    piso_mercado = None
    techo_mercado = None

  historial_lista = list(historial or [])
  precios_historial = [float(item["precio"]) for item in historial_lista if item.get("precio") is not None]
  fechas_historial = [_parse_fecha_historica(item.get("fecha")) for item in historial_lista]

  promedio_historial = float(np.mean(precios_historial)) if precios_historial else precio_actual
  minimo_historial = float(np.min(precios_historial)) if precios_historial else precio_actual
  ultima_fecha = fechas_historial[-1] if fechas_historial else datetime.utcnow()
  dias_estancado = max((datetime.utcnow() - ultima_fecha).days, 0)
  margen = ((precio_actual - precio_costo) / precio_costo) if precio_costo > 0 else 0.0
  brecha_similitud = (
    ((precio_actual - referencia_mercado) / referencia_mercado)
    if referencia_mercado and referencia_mercado > 0
    else 0.0
  )

  # Señal basada en historial de precios
  if precio_actual <= minimo_historial * 1.02:
    senial = "es el precio mas bajo de los ultimos dias"
  elif precio_actual > promedio_historial * 1.03:
    senial = "el precio esta por arriba del promedio"
  else:
    senial = "el precio esta en su precio promedio"

  precio_sugerido = precio_actual
  razon = "El precio actual se mantiene competitivo."

  # Logica de ajuste de precio basada en condiciones de mercado
  if referencia_mercado and precio_actual > 0:
    precio_sugerido = round(referencia_mercado * 0.98, 2)
    razon = "Se propone un precio ligeramente por debajo del grupo de productos similares para ser competitivo."

  if precio_costo > 0:
    precio_piso = round(precio_costo * 1.12, 2)
    precio_sugerido = max(precio_sugerido, precio_piso)
    if precio_sugerido == precio_piso:
      razon = "Se respeta un margen minimo sobre el costo y se ajusta frente a productos similares."

  if precio_costo > 0 and margen < 0.1 and not referencia_mercado:
    precio_sugerido = round(precio_costo * 1.1, 2)
    razon = "Se ajusta para asegurar una ganancia superior al 10%."
  elif dias_estancado >= 21:
    precio_piso = round(precio_costo * 1.1, 2) if precio_costo > 0 else precio_actual * 0.95
    precio_sugerido = max(precio_piso, round(precio_actual * 0.95, 2))
    razon = "El producto lleva demasiado tiempo estancado; conviene bajar el precio para aumentar el giro."
  elif stock >= 40 and precio_actual > promedio_historial:
    precio_piso = round(precio_costo * 1.1, 2) if precio_costo > 0 else precio_actual * 0.97
    precio_sugerido = max(precio_piso, round(precio_actual * 0.97, 2))
    razon = "Hay inventario suficiente; una ligera bajada puede acelerar la rotacion."

  # Actualizar señal segun referencia de mercado
  if referencia_mercado:
    if precio_actual <= referencia_mercado * 0.85:
      senial = "es una oportunidad imperdible, sumamente bajo respecto al mercado"
    elif precio_actual <= referencia_mercado * 0.95:
      senial = "esta por debajo del mercado comparable"
    elif precio_actual > referencia_mercado * 1.05:
      senial = "esta por encima de productos similares"
    else:
      senial = "se mantiene cerca del mercado comparable"

  etiqueta_tendencia = "estable"
  fecha_estimada_compra = None
  pendiente = 0.0
  comprar_ahora = True
  razon_compra = "El precio se mantiene razonable frente al historial y a productos similares."

  # Analisis de tendencia historica
  if len(precios_historial) >= 2:
    valores_x = np.array([(item_date - fechas_historial[0]).days for item_date in fechas_historial], dtype=float)
    valores_y = np.array(precios_historial, dtype=float)
    pendiente, _intercepto = np.polyfit(valores_x, valores_y, 1)
    if pendiente < 0 and precio_sugerido < precio_actual:
      dias_para_objetivo = (precio_sugerido - precios_historial[-1]) / pendiente if pendiente != 0 else None
      if dias_para_objetivo and dias_para_objetivo > 0:
        fecha_estimada = fechas_historial[-1] + timedelta(days=math.ceil(dias_para_objetivo))
        fecha_estimada_compra = fecha_estimada.date().isoformat()
        etiqueta_tendencia = "a la baja"
    elif pendiente > 0:
      etiqueta_tendencia = "al alza"

  # Logica de "comprar ahora o esperar"
  if referencia_mercado:
    if precio_actual <= referencia_mercado * 0.85:
      comprar_ahora = True
      razon_compra = "Oportunidad excepcional: el precio esta mas de un 15% por debajo del mercado comparable."
    elif precio_actual <= referencia_mercado * 0.97 and pendiente <= 0:
      comprar_ahora = True
      razon_compra = "Esta por debajo de los productos comparables y la tendencia no apunta a un alza inmediata."
    elif precio_actual > referencia_mercado * 1.05 or pendiente > 0:
      comprar_ahora = False
      razon_compra = "Conviene esperar: el precio esta por encima del mercado comparable o la tendencia sube."
  elif pendiente > 0 and precio_actual > promedio_historial:
    comprar_ahora = False
    razon_compra = "La tendencia historica va al alza y el precio sigue moviendose por encima del promedio."

  # Puntuacion vectorial con pesos
  caracteristicas = np.array([
    margen,
    max(brecha_similitud, 0.0),
    min(dias_estancado / 30.0, 3.0),
    min(stock / 50.0, 2.0),
  ])
  pesos = np.array([0.50, 0.25, 0.15, -0.10])
  puntuacion_vectorial = float(np.dot(caracteristicas, pesos))

  return {
    "signal": senial,
    "suggested_price": precio_sugerido,
    "reason": razon,
    "margin_percent": round(margen * 100, 2),
    "market_reference_price": round(referencia_mercado, 2) if referencia_mercado is not None else None,
    "market_reference_floor": round(piso_mercado, 2) if piso_mercado is not None else None,
    "market_reference_ceiling": round(techo_mercado, 2) if techo_mercado is not None else None,
    "trend_label": etiqueta_tendencia,
    "estimated_buy_date": fecha_estimada_compra,
    "stagnant_days": dias_estancado,
    "vector_score": round(puntuacion_vectorial, 4),
    "buy_now": comprar_ahora,
    "buy_reason": razon_compra,
    "similar_products": productos_similares,
  }


# ──────────────────────────────────────────────────────────────────────────────
# Función factory pública
# ──────────────────────────────────────────────────────────────────────────────

def crear_usuario_desde_fila_usuario(
  fila: Sequence[object],
  contrasena_hash: str | None = None,
) -> Persona:
  """Fabrica una Persona (Cliente o Vendedor) desde una fila de BD."""
  return Persona.desde_fila_usuario(fila, contrasena_hash=contrasena_hash)
