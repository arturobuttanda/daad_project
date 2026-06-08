from __future__ import annotations

from typing import Iterable

import numpy as np

try:
  from rapidfuzz import fuzz
  _HAS_RAPIDFUZZ = True
except ImportError:
  import difflib
  fuzz = None
  _HAS_RAPIDFUZZ = False


def normalizar_texto_similitud(value: object | None) -> str:
  if value is None:
    return ""
  cleaned = " ".join(str(value).replace("/", " ").replace("-", " ").split())
  return cleaned.lower()


def construir_perfil_producto(product: dict[str, object | None]) -> str:
  parts = [normalizar_texto_similitud(product.get("nombre"))]
  marca = normalizar_texto_similitud(product.get("marca"))
  categoria = normalizar_texto_similitud(product.get("categoria"))
  if marca:
    parts.append(marca)
  if categoria:
    parts.append(categoria)
  profile = " ".join(p for p in parts if p)
  return profile or normalizar_texto_similitud(product.get("id_producto")) or "producto"


def similitud_difusa(left_text: str, right_text: str) -> float:
  """Calcula una similitud difusa (token-aware) entre dos cadenas.

  Utiliza `token_sort_ratio` y `token_set_ratio` de rapidfuzz cuando está
  disponible y devuelve una puntuación normalizada en [0.0, 1.0]. Maneja
  mejor las palabras reordenadas y solapamientos parciales que la distancia
  de Levenshtein para nombres de producto.
  """
  valorIzquierdo = normalizar_texto_similitud(left_text)
  valorDerecho = normalizar_texto_similitud(right_text)
  if not valorIzquierdo and not valorDerecho:
    return 1.0
  if not valorIzquierdo or not valorDerecho:
    return 0.0

  # las proporciones basadas en tokens están en escala 0-100
  if _HAS_RAPIDFUZZ and fuzz is not None:
    try:
      ts = float(fuzz.token_sort_ratio(valorIzquierdo, valorDerecho))
      tset = float(fuzz.token_set_ratio(valorIzquierdo, valorDerecho))
    except Exception:
      ts = float(fuzz.ratio(valorIzquierdo, valorDerecho))
      tset = ts
  else:
    ratio = difflib.SequenceMatcher(None, valorIzquierdo, valorDerecho).ratio()
    ts = ratio * 100.0
    tset = ts

  # se da preferencia a token_set (maneja solapamientos parciales) pero manteniendo influencia de token_sort
  puntuacion_base = (0.6 * tset + 0.4 * ts) / 100.0

  # Los bonos por marca/categoría se aplican en la función llamante donde
  # estén disponibles los diccionarios de producto.
  return max(0.0, min(1.0, float(puntuacion_base)))


def rankear_productos_similares(
  target_product: dict[str, object | None],
  catalog: list[dict[str, object | None]],
  limit: int = 5,
  exclude_product_id: str | None = None,
) -> list[dict[str, object | None]]:
  if not catalog:
    return []

  nombre_objetivo = construir_perfil_producto(target_product)
  id_excluido = str(exclude_product_id or "").strip().upper() or None

  productos_puntuados: list[tuple[float, dict[str, object | None]]] = []
  for candidato in catalog:
    id_candidato = str(candidato.get("id_producto") or "").strip().upper()
    if id_excluido and id_candidato == id_excluido:
      continue

    puntuacion_bruta = similitud_difusa(nombre_objetivo, construir_perfil_producto(candidato))

    # aplicar bonos por marca/categoría
    bono = 0.0
    try:
      marca_objetivo = normalizar_texto_similitud(target_product.get("marca"))
      marca_candidato = normalizar_texto_similitud(candidato.get("marca"))
      if marca_objetivo and marca_candidato and marca_objetivo == marca_candidato:
        bono += 0.25
    except Exception:
      pass
    try:
      cat_objetivo = normalizar_texto_similitud(target_product.get("categoria"))
      cat_candidato = normalizar_texto_similitud(candidato.get("categoria"))
      if cat_objetivo and cat_candidato and cat_objetivo == cat_candidato:
        bono += 0.15
    except Exception:
      pass

    puntuacion = min(1.0, puntuacion_bruta + bono)

    # similitud mínima para evitar resultados no relacionados (ajustable)
    SIMILITUD_MINIMA = 0.50
    if puntuacion < SIMILITUD_MINIMA:
      continue
    if puntuacion <= 0:
      continue

    productos_puntuados.append((puntuacion, candidato))

  productos_puntuados.sort(key=lambda elemento: elemento[0], reverse=True)

  productos_similares: list[dict[str, object | None]] = []
  for puntuacion, candidato in productos_puntuados:
    precio_candidato = candidato.get("precio_actual")
    precio_objetivo = target_product.get("precio_actual")
    diferencia_precio = None
    if precio_candidato not in (None, 0) and precio_objetivo not in (None, 0):
      diferencia_precio = round(((float(precio_objetivo) - float(precio_candidato)) / float(precio_candidato)) * 100, 2)

    productos_similares.append(
      {
        "id_producto": candidato.get("id_producto"),
        "nombre": candidato.get("nombre"),
        "marca": candidato.get("marca"),
        "categoria": candidato.get("categoria"),
        "precio_actual": precio_candidato,
        "precio_fabricacion": candidato.get("precio_fabricacion"),
        "stock": candidato.get("stock"),
        "fecha_actualizacion": candidato.get("fecha_actualizacion"),
        "similarity_score": round(puntuacion, 4),
        "price_gap_percent": diferencia_precio,
      }
    )

    if len(productos_similares) >= limit:
      break

  return productos_similares

    # aplicar bonos por marca/categoría
    bono = 0.0
    try:
      marca_objetivo = normalizar_texto_similitud(target_product.get("marca"))
      marca_candidato = normalizar_texto_similitud(candidato.get("marca"))
      if marca_objetivo and marca_candidato and marca_objetivo == marca_candidato:
        bono += 0.25
    except Exception:
      pass
    try:
      cat_objetivo = normalizar_texto_similitud(target_product.get("categoria"))
      cat_candidato = normalizar_texto_similitud(candidato.get("categoria"))
      if cat_objetivo and cat_candidato and cat_objetivo == cat_candidato:
        bono += 0.15
    except Exception:
      pass

    puntuacion = min(1.0, puntuacion_bruta + bono)

    # similitud mínima para evitar resultados no relacionados (ajustable)
    SIMILITUD_MINIMA = 0.50
    if puntuacion < SIMILITUD_MINIMA:
      continue
    if puntuacion <= 0:
      continue

    productos_puntuados.append((puntuacion, candidato))

  productos_puntuados.sort(key=lambda elemento: elemento[0], reverse=True)

  productos_similares: list[dict[str, object | None]] = []
  for puntuacion, candidato in productos_puntuados:
    precio_candidato = candidato.get("precio_actual")
    precio_objetivo = target_product.get("precio_actual")
    diferencia_precio = None
    if precio_candidato not in (None, 0) and precio_objetivo not in (None, 0):
      diferencia_precio = round(((float(precio_objetivo) - float(precio_candidato)) / float(precio_candidato)) * 100, 2)

    productos_similares.append(
      {
        "id_producto": candidato.get("id_producto"),
        "nombre": candidato.get("nombre"),
        "marca": candidato.get("marca"),
        "categoria": candidato.get("categoria"),
        "precio_actual": precio_candidato,
        "precio_fabricacion": candidato.get("precio_fabricacion"),
        "stock": candidato.get("stock"),
        "fecha_actualizacion": candidato.get("fecha_actualizacion"),
        "similarity_score": round(puntuacion, 4),
        "price_gap_percent": diferencia_precio,
      }
    )

    if len(productos_similares) >= limit:
      break

  return productos_similares


def resumir_precios_similares(similar_products: Iterable[dict[str, object | None]]) -> tuple[float | None, float | None, float | None]:
  elementos_con_precio = [elemento for elemento in similar_products if elemento.get("precio_actual") is not None]
  if not elementos_con_precio:
    return None, None, None

  pesos = np.array([max(float(elemento.get("similarity_score") or 0.0), 0.01) for elemento in elementos_con_precio], dtype=float)
  precios = np.array([float(elemento["precio_actual"]) for elemento in elementos_con_precio], dtype=float)
  promedio_ponderado = float(np.average(precios, weights=pesos))
  precio_minimo = float(np.min(precios))
  precio_maximo = float(np.max(precios))
  return promedio_ponderado, precio_minimo, precio_maximo


# Las funciones ahora usan nombres nativos en español (sin alias en inglés)