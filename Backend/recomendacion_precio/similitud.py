from __future__ import annotations

from typing import Iterable
import re
import unicodedata

import numpy as np

try:
  from rapidfuzz import fuzz
  _HAS_RAPIDFUZZ = True
except ImportError:
  import difflib
  fuzz = None
  _HAS_RAPIDFUZZ = False


def normalizar_texto_similitud(value: object | None) -> str:
  """Normaliza texto para comparación: minúsculas, sin acentos, espacios limpios."""
  if value is None:
    return ""
  
  # Convertir a string y hacer minúsculas
  texto = str(value).lower()
  
  # Remover acentos usando descomposición NFD
  texto_nfd = unicodedata.normalize("NFD", texto)
  texto_sin_acentos = "".join(
    c for c in texto_nfd 
    if unicodedata.category(c) != "Mn"  # Mn = Nonspacing_Mark (acentos, diacríticos)
  )
  
  # Limpiar caracteres especiales y espacios
  cleaned = " ".join(
    texto_sin_acentos.replace("/", " ").replace("-", " ").split()
  )
  
  return cleaned


def tokenizar_texto(texto: str) -> set[str]:
  """Convierte una cadena normalizada en un conjunto de tokens limpios."""
  if not texto:
    return set()
  tokens = re.split(r"[^a-z0-9]+", texto)
  return {token for token in tokens if token}


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
  """Busca productos similares usando enfoque tipo 'Filtro de Excel'.
  
  Funciona como un filtro: busca productos que CONTENGAN las palabras clave
  del producto objetivo en su nombre, marca o categoría.
  
  Criterios de ranking:
  1. Cantidad de palabras clave significativas coincidentes (3+ caracteres)
  2. Coincidencia de marca exacta
  3. Coincidencia de categoría exacta
  """
  if not catalog:
    return []

  id_excluido = str(exclude_product_id or "").strip().upper() or None

  # Obtener palabras clave del producto objetivo (solo del nombre, sin acentos)
  nombre_objetivo = normalizar_texto_similitud(target_product.get("nombre"))
  tokens_objetivo = tokenizar_texto(nombre_objetivo)
  
  # Filtrar tokens muy cortos (< 3 caracteres) para enfocarse en palabras significativas
  tokens_objetivo_significativos = {t for t in tokens_objetivo if len(t) >= 3}
  
  # Si no hay tokens significativos, usar todos pero con peso menor
  if not tokens_objetivo_significativos:
    tokens_objetivo_significativos = {t for t in tokens_objetivo if len(t) > 1}
  
  if not tokens_objetivo_significativos:
    # Si no hay tokens válidos, devolver los primeros productos con precio
    return [
      {
        "id_producto": p.get("id_producto"),
        "nombre": p.get("nombre"),
        "marca": p.get("marca"),
        "categoria": p.get("categoria"),
        "precio_actual": p.get("precio_actual"),
        "precio_fabricacion": p.get("precio_fabricacion"),
        "stock": p.get("stock"),
        "fecha_actualizacion": p.get("fecha_actualizacion"),
        "similarity_score": 0.0,
        "price_gap_percent": None,
      }
      for p in catalog if p.get("precio_actual") is not None
    ][:limit]

  # Obtener marca y categoría objetivo normalizadas para comparación exacta
  marca_objetivo = normalizar_texto_similitud(target_product.get("marca"))
  categoria_objetivo = normalizar_texto_similitud(target_product.get("categoria"))

  productos_puntuados: list[tuple[tuple[int, int, int, float], dict[str, object | None]]] = []

  for candidato in catalog:
    id_candidato = str(candidato.get("id_producto") or "").strip().upper()
    if id_excluido and id_candidato == id_excluido:
      continue

    # Obtener tokens del producto candidato
    nombre_candidato = normalizar_texto_similitud(candidato.get("nombre"))
    tokens_candidato = tokenizar_texto(nombre_candidato)
    tokens_candidato_significativos = {t for t in tokens_candidato if len(t) >= 3}
    
    # Contar coincidencias de tokens significativos
    tokens_comunes_significativos = tokens_objetivo_significativos.intersection(tokens_candidato_significativos)
    num_tokens_coincidentes = len(tokens_comunes_significativos)
    
    # No incluir si no hay coincidencias en tokens significativos
    if num_tokens_coincidentes == 0:
      # Fallback: buscar al menos algún token en común (incluso cortos)
      tokens_comunes_todos = tokens_objetivo.intersection(tokens_candidato)
      if not tokens_comunes_todos:
        continue
      # Contar solo para ranking, pero con baja prioridad
      num_tokens_coincidentes = len(tokens_comunes_todos) * 0.5
    

    # Verificar coincidencia de marca (exacta)
    marca_coincide = 0
    if marca_objetivo and marca_objetivo == normalizar_texto_similitud(candidato.get("marca")):
      marca_coincide = 1

    # Verificar coincidencia de categoría (exacta)
    categoria_coincide = 0
    if categoria_objetivo and categoria_objetivo == normalizar_texto_similitud(candidato.get("categoria")):
      categoria_coincide = 1

    # Proporción de tokens coincidentes vs totales (mayor = mejor)
    total_tokens_objetivo = len(tokens_objetivo_significativos)
    proporcion_tokens = num_tokens_coincidentes / max(total_tokens_objetivo, 1)

    # Tuple para ordenamiento: 
    # (más tokens significativos, marca coincide, categoría coincide, proporción)
    # Usamos negativo para ordenar descendente en los primeros 3
    clave_ordenamiento = (-num_tokens_coincidentes, -marca_coincide, -categoria_coincide, -proporcion_tokens)
    
    productos_puntuados.append((clave_ordenamiento, candidato))

  # Ordenar por relevancia
  productos_puntuados.sort(key=lambda x: x[0])

  # Construir resultado
  productos_similares: list[dict[str, object | None]] = []
  for clave, candidato in productos_puntuados:
    precio_candidato = candidato.get("precio_actual")
    
    # Filtrar solo productos con precio válido
    if precio_candidato is None or precio_candidato == 0:
      continue

    precio_objetivo = target_product.get("precio_actual")
    diferencia_precio = None
    if precio_objetivo not in (None, 0):
      diferencia_precio = round(((float(precio_objetivo) - float(precio_candidato)) / float(precio_candidato)) * 100, 2)

    # Calcular similarity_score basado en tokens coincidentes significativos
    # Máximo 1.0 si coinciden todos los tokens significativos
    num_coincidentes = -clave[0]  # Recuperar valor original (fue negado para ordenar)
    num_total = len(tokens_objetivo_significativos)
    
    # Si num_coincidentes es fraccionario (0.5, 1.5, etc), es porque usamos fallback
    # En ese caso, normalizar a rango 0-1
    if num_total > 0:
      similarity_score = min(1.0, num_coincidentes / num_total)
    else:
      similarity_score = 0.0

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
        "similarity_score": round(similarity_score, 4),
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