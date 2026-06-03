from __future__ import annotations

from abc import ABC
from datetime import date, datetime, timedelta
import math
from typing import Any, Iterable, Sequence

import numpy as np

from Backend.recomendacion_precio import rank_similar_products, summarize_similarity_prices


def _limpiar_texto(valor: object | None) -> str:
  if valor is None:
    return ""
  return " ".join(str(valor).split())


def _normalizar_correo(correo: str) -> str:
  return _limpiar_texto(correo).lower()


def _normalizar_numero(valor: object | None) -> str:
  return _limpiar_texto(valor)


def _normalizar_float(valor: object | None) -> float | None:
  if valor is None or valor == "":
    return None
  return float(valor)


def _normalizar_fecha_obj(valor: object | None) -> date | None:
  if valor is None:
    return None
  if isinstance(valor, date):
    return valor
  texto = _limpiar_texto(valor)
  if not texto:
    return None
  return date.fromisoformat(texto)


def _validar_nombre(nombre: str) -> str:
  nombre_limpio = _limpiar_texto(nombre)
  if not nombre_limpio:
    raise ValueError("El nombre no puede estar vacio.")
  return nombre_limpio


def _validar_password(password: str) -> str:
  password_limpio = _limpiar_texto(password)
  if len(password_limpio) < 8:
    raise ValueError("La contrasena debe tener al menos 8 caracteres.")
  if not any(caracter.isupper() for caracter in password_limpio):
    raise ValueError("La contrasena debe incluir una mayuscula.")
  if not any(caracter.isdigit() for caracter in password_limpio):
    raise ValueError("La contrasena debe incluir un numero.")
  return password_limpio


def _producto_a_diccionario(producto: Producto | dict[str, object | None]) -> dict[str, object | None]:
  if isinstance(producto, Producto):
    return producto.to_dict()
  return dict(producto)


def _parse_fecha_historica(valor: object | None) -> datetime:
  if isinstance(valor, datetime):
    return valor
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


class Persona(ABC):
  """Clase base abstracta para usuarios del sistema."""

  def __init__(
    self,
    id_persona: str,
    nombre: str,
    telefono: str | None,
    correo: str,
    tipo_usuario: str,
    password_hash: str | None = None,
  ):
    if type(self) is Persona:
      raise TypeError("No se puede instanciar la clase abstracta Persona directamente.")
    self.id = _limpiar_texto(id_persona)
    self.nombre = _validar_nombre(nombre)
    self.telefono = _normalizar_numero(telefono)
    self.correo = _normalizar_correo(correo)
    self.tipo_usuario = _limpiar_texto(tipo_usuario)
    self.password_hash = _limpiar_texto(password_hash) if password_hash is not None else None

  def cambiar_nombre(self, nuevo_nombre: str) -> None:
    self.nombre = _validar_nombre(nuevo_nombre)

  def cambiar_telefono(self, nuevo_telefono: str | None) -> None:
    self.telefono = _normalizar_numero(nuevo_telefono)

  def cambiar_correo(self, nuevo_correo: str) -> None:
    correo_limpio = _normalizar_correo(nuevo_correo)
    if not correo_limpio or "@" not in correo_limpio:
      raise ValueError("El correo no es valido.")
    self.correo = correo_limpio

  def cambiar_contrasena(self, nueva_contrasena_hash: str) -> None:
    contrasena_hash = _limpiar_texto(nueva_contrasena_hash)
    if not contrasena_hash:
      raise ValueError("El hash de la contrasena no puede estar vacio.")
    self.password_hash = contrasena_hash

  def actualizar_perfil(
    self,
    nombre: str | None = None,
    telefono: str | None = None,
    correo: str | None = None,
    contrasena_hash: str | None = None,
  ) -> None:
    if nombre is not None:
      self.cambiar_nombre(nombre)
    if telefono is not None:
      self.cambiar_telefono(telefono)
    if correo is not None:
      self.cambiar_correo(correo)
    if contrasena_hash is not None:
      self.cambiar_contrasena(contrasena_hash)

  def to_public_dict(self) -> dict[str, object | None]:
    return {
      "id": self.id,
      "nombre": self.nombre,
      "correo": self.correo,
      "tipo_usuario": self.tipo_usuario,
    }

  def to_row(self) -> dict[str, object | None]:
    return {
      "id_usuario": self.id,
      "nombre": self.nombre,
      "telefono": self.telefono or None,
      "correo": self.correo,
      "tipo_usuario": self.tipo_usuario,
      "password_hash": self.password_hash,
    }

  @classmethod
  def from_row(
    cls,
    row: Sequence[object],
    password_hash: str | None = None,
  ) -> "Persona":
    return cls.desde_fila_usuario(row, password_hash=password_hash)

  @classmethod
  def desde_fila_usuario(
    cls,
    fila: Sequence[object],
    password_hash: str | None = None,
  ) -> "Persona":
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
        password_hash=password_hash,
      )

    return Cliente(
      id_persona=id_usuario,
      nombre=nombre,
      telefono=telefono if telefono is not None else None,
      correo=correo,
      password_hash=password_hash,
    )


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
    fecha_caducidad: date | None = None,
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
    self.fecha_caducidad = fecha_caducidad
    self.imagen_url = _limpiar_texto(imagen_url) or None
    self.fecha_actualizacion = fecha_actualizacion

  @classmethod
  def desde_dict(cls, datos: dict[str, object | None]) -> "Producto":
    return cls(
      id_producto=str(datos.get("id_producto") or ""),
      nombre=str(datos.get("nombre") or ""),
      marca=datos.get("marca") if datos.get("marca") is not None else None,
      precio_venta_actual=_normalizar_float(datos.get("precio_actual")),
      stock=int(datos.get("stock") or 0),
      precio_fabricacion=_normalizar_float(datos.get("precio_fabricacion")),
      fecha_caducidad=_normalizar_fecha_obj(datos.get("fecha_caducidad")),
      imagen_url=datos.get("imagen_url") if datos.get("imagen_url") is not None else None,
      fecha_actualizacion=_parse_fecha_historica(datos.get("fecha_actualizacion")) if datos.get("fecha_actualizacion") else None,
      categoria=datos.get("categoria") if datos.get("categoria") is not None else None,
    )

  @classmethod
  def desde_fila(cls, fila: Sequence[object], columnas: Sequence[str]) -> "Producto":
    datos = dict(zip(columnas, fila))
    return cls.desde_dict(datos)

  @classmethod
  def from_row(cls, fila: Sequence[object], columnas: Sequence[str]) -> "Producto":
    return cls.desde_fila(fila, columnas)

  def cambiar_precio(self, nuevo_precio: float) -> None:
    precio_limpio = float(nuevo_precio)
    if precio_limpio < 0:
      raise ValueError("El precio no puede ser negativo.")
    self.precio_actual = round(precio_limpio, 2)

  def ajustar_precio(self, porcentaje: float) -> None:
    if self.precio_actual is None:
      raise ValueError("El producto no tiene precio actual.")
    self.cambiar_precio(self.precio_actual * (1 + float(porcentaje)))

  def actualizar_stock(self, nuevo_stock: int) -> None:
    stock_limpio = int(nuevo_stock)
    if stock_limpio < 0:
      raise ValueError("El stock no puede ser negativo.")
    self.stock = stock_limpio

  def aplicar_descuento(self, porcentaje: float) -> None:
    if self.precio_actual is None:
      raise ValueError("El producto no tiene precio actual.")
    self.cambiar_precio(self.precio_actual * (1 - float(porcentaje)))

  def actualizar_datos(
    self,
    nombre: str | None = None,
    marca: str | None = None,
    categoria: str | None = None,
    precio_actual: float | None = None,
    stock: int | None = None,
    precio_fabricacion: float | None = None,
    fecha_caducidad: date | None = None,
    imagen_url: str | None = None,
  ) -> None:
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
      if float(precio_fabricacion) < 0:
        raise ValueError("El costo no puede ser negativo.")
      self.precio_fabricacion = float(precio_fabricacion)
    if fecha_caducidad is not None:
      self.fecha_caducidad = fecha_caducidad
    if imagen_url is not None:
      self.imagen_url = _limpiar_texto(imagen_url) or None

  def to_dict(self) -> dict[str, object | None]:
    return {
      "id_producto": self.id_producto,
      "nombre": self.nombre,
      "marca": self.marca or None,
      "categoria": self.categoria or None,
      "precio_actual": self.precio_actual,
      "stock": self.stock,
      "precio_fabricacion": self.precio_fabricacion,
      "fecha_caducidad": self.fecha_caducidad.isoformat() if self.fecha_caducidad else None,
      "imagen_url": self.imagen_url,
      "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
    }

  def to_row(self) -> dict[str, object | None]:
    return {
      "id_producto": self.id_producto,
      "nombre": self.nombre,
      "marca": self.marca or None,
      "categoria": self.categoria or None,
      "precio_actual": self.precio_actual,
      "stock": self.stock,
      "precio_fabricacion": self.precio_fabricacion,
      "fecha_caducidad": self.fecha_caducidad,
      "imagen_url": self.imagen_url,
      "fecha_actualizacion": self.fecha_actualizacion,
    }


class Venta:
  """Registro de una transaccion comercial."""

  def __init__(
    self,
    id_venta: str,
    producto: Producto,
    cantidad: int,
    fecha_venta: date | datetime,
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

  def to_dict(self) -> dict[str, object | None]:
    return {
      "id_venta": self.id_venta,
      "producto": self.producto.to_dict(),
      "cantidad": self.cantidad,
      "fecha_venta": self.fecha_venta.isoformat() if hasattr(self.fecha_venta, "isoformat") else str(self.fecha_venta),
      "total_pagado": self.total_pagado,
    }

  def to_row(self) -> dict[str, object | None]:
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
    fecha_venta: date | datetime | None,
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


class Informe:
  """Salida agregada para reportes financieros."""

  def __init__(
    self,
    ingresos_totales: float,
    costos_totales: float,
    margen_ganancia: float,
    alertas_stock_bajo: Sequence[Producto],
  ):
    self.ingresos_totales = float(ingresos_totales)
    self.costos_totales = float(costos_totales)
    self.margen_ganancia = float(margen_ganancia)
    self.alertas_stock_bajo = list(alertas_stock_bajo)

  def to_dict(self) -> dict[str, object | None]:
    return {
      "ingresos_totales": self.ingresos_totales,
      "costos_totales": self.costos_totales,
      "margen_ganancia": self.margen_ganancia,
      "alertas_stock_bajo": [producto.to_dict() for producto in self.alertas_stock_bajo],
    }


def calcular_recomendacion_precio(
  producto: Producto | dict[str, object | None],
  historial: Iterable[dict[str, object]] | None,
  competencia_promedio: float | None,
  catalogo: list[dict[str, object | None]] | None,
  limite: int = 5,
) -> dict[str, object | None]:
  producto_dict = _producto_a_diccionario(producto)
  current_price = float(producto_dict.get("precio_actual") or 0)
  cost_price = float(producto_dict.get("precio_fabricacion") or 0)
  stock = int(producto_dict.get("stock") or 0)

  catalogo_similares = catalogo or []
  similar_products = rank_similar_products(
    producto_dict,
    catalogo_similares,
    limit=limite,
    exclude_product_id=str(producto_dict.get("id_producto") or ""),
  )
  market_reference, market_floor, market_ceiling = summarize_similarity_prices(similar_products)

  history = list(historial or [])
  history_prices = [float(item["precio"]) for item in history if item.get("precio") is not None]
  history_dates = [_parse_fecha_historica(item.get("fecha")) for item in history]

  average_history = float(np.mean(history_prices)) if history_prices else current_price
  minimum_history = float(np.min(history_prices)) if history_prices else current_price
  latest_date = history_dates[-1] if history_dates else datetime.utcnow()
  stagnant_days = max((datetime.utcnow() - latest_date).days, 0)
  competition_gap = (
    ((current_price - competencia_promedio) / competencia_promedio)
    if competencia_promedio and competencia_promedio > 0
    else 0.0
  )
  margin = ((current_price - cost_price) / cost_price) if cost_price > 0 else 0.0
  similarity_gap = (
    ((current_price - market_reference) / market_reference)
    if market_reference and market_reference > 0
    else 0.0
  )

  if current_price <= minimum_history * 1.02:
    signal = "es el precio mas bajo de los ultimos dias"
  elif current_price > average_history * 1.03:
    signal = "el precio esta por arriba del promedio"
  else:
    signal = "el precio esta en su precio promedio"

  suggested_price = current_price
  reason = "El precio actual se mantiene competitivo."

  if market_reference and current_price > 0:
    suggested_price = round(market_reference * 0.98, 2)
    reason = "Se propone un precio ligeramente por debajo del grupo de productos similares para ser competitivo."

  if cost_price > 0:
    floor_price = round(cost_price * 1.12, 2)
    suggested_price = max(suggested_price, floor_price)
    if suggested_price == floor_price:
      reason = "Se respeta un margen minimo sobre el costo y se ajusta frente a productos similares."

  if cost_price > 0 and margin < 0.1 and not market_reference:
    suggested_price = round(cost_price * 1.1, 2)
    reason = "Se ajusta para asegurar una ganancia superior al 10%."
  elif stagnant_days >= 21 and competition_gap > 0:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.95
    suggested_price = max(floor_price, round(current_price * 0.95, 2))
    reason = "El producto lleva demasiado tiempo estancado; conviene bajar el precio para aumentar el giro."
  elif competencia_promedio and current_price > competencia_promedio * 1.05:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.95
    suggested_price = max(floor_price, round(competencia_promedio * 0.99, 2))
    reason = "El precio esta por encima de la competencia de mercado."
  elif stock >= 40 and current_price > average_history:
    floor_price = round(cost_price * 1.1, 2) if cost_price > 0 else current_price * 0.97
    suggested_price = max(floor_price, round(current_price * 0.97, 2))
    reason = "Hay inventario suficiente; una ligera bajada puede acelerar la rotacion."

  if market_reference:
    if current_price <= market_reference * 0.97:
      signal = "está por debajo del mercado comparable"
    elif current_price > market_reference * 1.05:
      signal = "está por encima de productos similares"
    else:
      signal = "se mantiene cerca del mercado comparable"

  trend_label = "estable"
  estimated_buy_date = None
  slope = 0.0
  buy_now = True
  buy_reason = "El precio se mantiene razonable frente al historial y a productos similares."

  if len(history_prices) >= 2:
    x_values = np.array([(item_date - history_dates[0]).days for item_date in history_dates], dtype=float)
    y_values = np.array(history_prices, dtype=float)
    slope, _intercept = np.polyfit(x_values, y_values, 1)
    if slope < 0 and suggested_price < current_price:
      days_until_target = (suggested_price - history_prices[-1]) / slope if slope != 0 else None
      if days_until_target and days_until_target > 0:
        estimated_date = history_dates[-1] + timedelta(days=math.ceil(days_until_target))
        estimated_buy_date = estimated_date.date().isoformat()
        trend_label = "a la baja"
    elif slope > 0:
      trend_label = "al alza"

  if market_reference:
    if current_price <= market_reference * 0.97 and slope <= 0:
      buy_now = True
      buy_reason = "Está por debajo de los productos comparables y la tendencia no apunta a un alza inmediata."
    elif current_price > market_reference * 1.05 or slope > 0:
      buy_now = False
      buy_reason = "Conviene esperar: el precio está por encima del mercado comparable o la tendencia sube."
  elif slope > 0 and current_price > average_history:
    buy_now = False
    buy_reason = "La tendencia histórica va al alza y el precio sigue moviéndose por encima del promedio."

  features = np.array([
    margin,
    max(competition_gap, 0.0),
    max(similarity_gap, 0.0),
    min(stagnant_days / 30.0, 3.0),
    min(stock / 50.0, 2.0),
  ])
  weights = np.array([0.44, 0.18, 0.18, 0.12, -0.08])
  vector_score = float(np.dot(features, weights))

  return {
    "signal": signal,
    "suggested_price": suggested_price,
    "reason": reason,
    "margin_percent": round(margin * 100, 2),
    "competition_average": competencia_promedio,
    "market_reference_price": round(market_reference, 2) if market_reference is not None else None,
    "market_reference_floor": round(market_floor, 2) if market_floor is not None else None,
    "market_reference_ceiling": round(market_ceiling, 2) if market_ceiling is not None else None,
    "trend_label": trend_label,
    "estimated_buy_date": estimated_buy_date,
    "stagnant_days": stagnant_days,
    "vector_score": round(vector_score, 4),
    "buy_now": buy_now,
    "buy_reason": buy_reason,
    "similar_products": similar_products,
  }


class Cliente(Persona):
  """Rol de consumidor."""

  def __init__(
    self,
    id_persona: str,
    nombre: str,
    telefono: str | None,
    correo: str,
    presupuesto_maximo: float = 0.0,
    historial_compras: Sequence[Venta] | None = None,
    password_hash: str | None = None,
  ):
    super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Cliente", password_hash=password_hash)
    self.historial_compras = list(historial_compras or [])
    self.presupuesto_maximo = float(presupuesto_maximo)

  def consultar_precio_mas_bajo(
    self,
    producto: Producto | dict[str, object | None],
    precios_historial: Iterable[float] | None = None,
  ) -> float | None:
    precios = [float(precio) for precio in precios_historial or [] if precio is not None]
    if precios:
      return float(min(precios))
    precio_actual = _producto_a_diccionario(producto).get("precio_actual")
    return float(precio_actual) if precio_actual is not None else None

  def hacer_analisis_precio(
    self,
    producto: Producto | dict[str, object | None],
    precios_historial: Iterable[float] | None = None,
  ) -> str:
    precio_actual = _producto_a_diccionario(producto).get("precio_actual")
    if precio_actual is None:
      return "No hay precio disponible para analizar."
    precio_bajo = self.consultar_precio_mas_bajo(producto, precios_historial)
    if precio_bajo is not None and float(precio_actual) <= precio_bajo:
      return "El producto esta en su precio mas bajo reciente."
    if self.presupuesto_maximo and float(precio_actual) > self.presupuesto_maximo:
      return "El producto supera tu presupuesto maximo."
    return "El precio se mantiene dentro de un rango razonable."

  def recomendacion_compra(
    self,
    producto: Producto | dict[str, object | None],
    precios_historial: Iterable[dict[str, object]] | None = None,
    competencia_promedio: float | None = None,
    catalogo: list[dict[str, object | None]] | None = None,
  ) -> str:
    recomendacion = calcular_recomendacion_precio(producto, precios_historial, competencia_promedio, catalogo)
    if recomendacion.get("buy_now"):
      return "Conviene comprar ahora."
    return "Conviene esperar un poco mas."

  def registrar_compra(self, venta: Venta) -> None:
    self.historial_compras.append(venta)


class Vendedor(Persona):
  """Rol operativo con acceso a inventario y precios."""

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
    productos_asignados: Sequence[Producto] | None = None,
    password_hash: str | None = None,
  ):
    super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Vendedor", password_hash=password_hash)
    self.id_vendedor = _limpiar_texto(id_vendedor)
    self.codigo_vendedor = _limpiar_texto(codigo_vendedor) or self.id_vendedor
    self.especialidad = _limpiar_texto(especialidad)
    self.objetivo_ventas = float(objetivo_ventas) if objetivo_ventas is not None else 0.0
    self.productos_asignados = list(productos_asignados or [])

  def obtener_costo_fabricacion(self, producto: Producto | dict[str, object | None]) -> float | None:
    costo = _producto_a_diccionario(producto).get("precio_fabricacion")
    return float(costo) if costo is not None else None

  def vender_producto(
    self,
    producto: Producto,
    cantidad: int,
    fecha_venta: date | datetime | None = None,
    total_pagado: float | None = None,
    id_venta: str | None = None,
  ) -> Venta:
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

  def recomendacion_de_precio(
    self,
    producto: Producto | dict[str, object | None],
    historial_precios: Iterable[dict[str, object]] | None = None,
    competencia_promedio: float | None = None,
    catalogo: list[dict[str, object | None]] | None = None,
  ) -> dict[str, object | None]:
    return calcular_recomendacion_precio(producto, historial_precios, competencia_promedio, catalogo)

  def ajustar_precio(self, producto: Producto, porcentaje: float) -> None:
    producto.ajustar_precio(porcentaje)

  def quitar_producto(self, producto: Producto) -> None:
    self.productos_asignados = [item for item in self.productos_asignados if item.id_producto != producto.id_producto]

  def generar_informe_financiero(self) -> Informe:
    ingresos_totales = 0.0
    costos_totales = 0.0
    alertas_stock_bajo: list[Producto] = []

    for producto in self.productos_asignados:
      if producto.precio_actual is not None:
        ingresos_totales += producto.precio_actual * max(producto.stock, 0)
      if producto.precio_fabricacion is not None:
        costos_totales += producto.precio_fabricacion * max(producto.stock, 0)
      if producto.stock <= 5:
        alertas_stock_bajo.append(producto)

    margen_ganancia = ingresos_totales - costos_totales
    return Informe(ingresos_totales, costos_totales, margen_ganancia, alertas_stock_bajo)

  def checar_inventario(self) -> list[Producto]:
    productos_con_alerta: list[Producto] = []
    for producto in self.productos_asignados:
      if producto.stock <= 5:
        productos_con_alerta.append(producto)
      if producto.fecha_caducidad and producto.fecha_caducidad <= date.today():
        productos_con_alerta.append(producto)
    return productos_con_alerta


def crear_usuario_desde_fila_usuario(
  fila: Sequence[object],
  password_hash: str | None = None,
) -> Persona:
  return Persona.desde_fila_usuario(fila, password_hash=password_hash)