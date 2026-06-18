from __future__ import annotations

"""Funciones de similitud textual para recomendacion de precios.

Proporciona normalizacion de texto, tokenizacion, calculo de similitud
difusa y ranking de productos similares usando enfoque de filtro.
"""

from typing import Iterable
import re
import unicodedata

import numpy as np

try:
  from rapidfuzz import fuzz
  _TIENE_RAPIDFUZZ = True
except ImportError:
  import difflib
  fuzz = None
  _TIENE_RAPIDFUZZ = False

# Tokenes genericos que no aportan significado en la busqueda de similitud
_TOKENS_IRRELEVANTES = frozenset({
  "the", "a", "an", "and", "or", "for", "with", "without", "but", "not",
  "up", "to", "in", "on", "at", "by", "is", "it", "of", "be", "as", "from",
  "all", "any", "can", "do", "has", "had", "its", "may", "was", "were",
  "will", "would", "could", "should", "than", "that", "this", "these",
  "each", "every", "more", "most", "some", "such", "into", "over",
  "very", "just", "also", "been", "both", "does", "have", "like",
  "made", "much", "only", "other", "same", "so", "too", "well",
  "you", "your", "new", "gen", "v2", "v3", "x", "type",
})


def normalizar_texto_similitud(valor: object | None) -> str:
  """Normaliza texto para comparacion: minusculas, sin acentos, espacios limpios."""
  if valor is None:
    return ""

  texto = str(valor).lower()
  texto_nfd = unicodedata.normalize("NFD", texto)
  texto_sin_acentos = "".join(
    c for c in texto_nfd
    if unicodedata.category(c) != "Mn"
  )

  limpio = " ".join(
    texto_sin_acentos.replace("/", " ").replace("-", " ").split()
  )

  return limpio


def tokenizar_texto(texto: str) -> set[str]:
  """Convierte una cadena normalizada en un conjunto de tokens limpios."""
  if not texto:
    return set()
  tokens = re.split(r"[^a-z0-9]+", texto)
  return {token for token in tokens if token and token not in _TOKENS_IRRELEVANTES}


def _extraer_token_tipo(producto_str: str) -> str | None:
  """Extrae el token que define el tipo de producto (tv, ssd, earbuds, etc)."""
  tipos_prioritarios = re.findall(
    r"\b(televisor|television|tv|pantalla|monitor|smartwatch|"
    r"audifonos|earbuds|headphone|headphones|"
    r"ssd|hdd|disco|unidad|hard drive|"
    r"laptop|computadora|notebook|"
    r"celular|smartphone|telefono|"
    r"camara|lente|lens|"
    r"bocina|speaker|soundbar|"
    r"tablet|kindle|"
    r"impresora|printer|"
    r"consola|xbox|playstation|nintendo|"
    r"grafica|graphics|radeon|geforce|"
    r"procesador|processor|cpu|ryzen|core|"
    r"memoria|ram|ddr|"
    r"tarjeta|card|"
    r"cargador|charger|cable|"
    r"filtro|purificador|purifier|"
    r"ropa|shirt|pants|zapato|shoe|"
    r"perfume|cologne|"
    r"juguete|toy|"
    r"mueble|furniture|silla|chair|mesa|table|cama|bed|"
    r"libro|book|"
    r"bicicleta|bike|"
    r"licuadora|blender|air fryer|"
    r"parlante|speaker)\b",
    producto_str.lower(),
  )
  if tipos_prioritarios:
    return tipos_prioritarios[0]
  return None


def _calcular_penalizacion_categoria(
  cat_objetivo: str, cat_candidato: str, marca_coincide: bool
) -> float:
  """Calcula penalizacion cuando las categorias no coinciden.

  Retorna un factor multiplicativo entre 0.0 y 1.0.
  """
  if not cat_objetivo or not cat_candidato:
    return 1.0
  if cat_objetivo == cat_candidato:
    return 1.0

  # Penalizar significativamente si es diferente categoria
  # Si ademas la marca no coincide, la penalizacion es maxima
  return 0.25 if marca_coincide else 0.15


def construir_perfil_producto(producto: dict[str, object | None]) -> str:
  """Construye un perfil textual del producto para busqueda de similitud."""
  partes = [normalizar_texto_similitud(producto.get("nombre"))]
  marca = normalizar_texto_similitud(producto.get("marca"))
  categoria = normalizar_texto_similitud(producto.get("categoria"))
  if marca:
    partes.append(marca)
  if categoria:
    partes.append(categoria)
  perfil = " ".join(p for p in partes if p)
  return perfil or normalizar_texto_similitud(producto.get("id_producto")) or "producto"


def similitud_difusa(texto_izquierdo: str, texto_derecho: str) -> float:
  """Calcula similitud difusa (token-aware) entre dos cadenas.

  Usa token_sort_ratio y token_set_ratio de rapidfuzz cuando esta disponible.
  Retorna un valor normalizado en [0.0, 1.0].
  """
  valor_izquierdo = normalizar_texto_similitud(texto_izquierdo)
  valor_derecho = normalizar_texto_similitud(texto_derecho)
  if not valor_izquierdo and not valor_derecho:
    return 1.0
  if not valor_izquierdo or not valor_derecho:
    return 0.0

  if _TIENE_RAPIDFUZZ and fuzz is not None:
    try:
      ts = float(fuzz.token_sort_ratio(valor_izquierdo, valor_derecho))
      tset = float(fuzz.token_set_ratio(valor_izquierdo, valor_derecho))
    except Exception:
      ts = float(fuzz.ratio(valor_izquierdo, valor_derecho))
      tset = ts
  else:
    proporcion = difflib.SequenceMatcher(None, valor_izquierdo, valor_derecho).ratio()
    ts = proporcion * 100.0
    tset = ts

  # Prioriza token_set (mejor para solapamientos parciales) con influencia de token_sort
  puntuacion_base = (0.6 * tset + 0.4 * ts) / 100.0
  return max(0.0, min(1.0, float(puntuacion_base)))


def _coincide_marca(marca_objetivo: str, candidato: dict) -> bool:
  """Verifica si la marca del candidato coincide con la marca objetivo."""
  if not marca_objetivo:
    return False
  marca_candidato = normalizar_texto_similitud(candidato.get("marca"))
  return bool(marca_candidato) and marca_objetivo == marca_candidato


def _tokens_significativos(tokens: set[str]) -> set[str]:
  """Filtra solo tokens de 3+ caracteres, excluyendo irrelevantes."""
  return {t for t in tokens if len(t) >= 3 and t not in _TOKENS_IRRELEVANTES}


def rankear_productos_similares(
  producto_objetivo: dict[str, object | None],
  catalogo: list[dict[str, object | None]],
  limit: int = 5,
  exclude_product_id: str | None = None,
) -> list[dict[str, object | None]]:
  """Busca productos similares usando enfoque de filtro textual.

  Funciona como un filtro de Excel: busca productos que contengan las
  palabras clave del producto objetivo en nombre, marca o categoria.

  Criterios de ranking:
  1. Cantidad de tokens significativos coincidentes (3+ caracteres)
  2. Coincidencia exacta de marca
  3. Penalizacion por categoria diferente
  4. Coincidencia de tipo de producto
  """
  if not catalogo:
    return []

  id_excluido = str(exclude_product_id or "").strip().upper() or None
  nombre_objetivo = normalizar_texto_similitud(producto_objetivo.get("nombre"))
  tokens_objetivo = tokenizar_texto(nombre_objetivo)

  tokens_objetivo_significativos = _tokens_significativos(tokens_objetivo)
  if not tokens_objetivo_significativos:
    tokens_objetivo_significativos = {t for t in tokens_objetivo if len(t) > 1 and t not in _TOKENS_IRRELEVANTES}
  if not tokens_objetivo_significativos:
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
      for p in catalogo if p.get("precio_actual") is not None
    ][:limit]

  marca_objetivo = normalizar_texto_similitud(producto_objetivo.get("marca"))
  categoria_objetivo = normalizar_texto_similitud(producto_objetivo.get("categoria"))
  nombre_objetivo_largo = (nombre_objetivo + " " + marca_objetivo + " " + categoria_objetivo).strip()
  tipo_objetivo = _extraer_token_tipo(nombre_objetivo_largo)

  total_tokens_objetivo = max(len(tokens_objetivo_significativos), 1)
  productos_puntuados: list[tuple[tuple[float, int, int, float], dict[str, object | None], int]] = []

  for candidato in catalogo:
    id_candidato = str(candidato.get("id_producto") or "").strip().upper()
    if id_excluido and id_candidato == id_excluido:
      continue

    nombre_candidato = normalizar_texto_similitud(candidato.get("nombre"))
    tokens_candidato = tokenizar_texto(nombre_candidato)
    tokens_candidato_significativos = _tokens_significativos(tokens_candidato)

    tokens_comunes = tokens_objetivo_significativos.intersection(tokens_candidato_significativos)
    num_coincidentes = len(tokens_comunes)

    if num_coincidentes == 0:
      tokens_comunes_todos = tokens_objetivo.intersection(tokens_candidato)
      if not tokens_comunes_todos:
        continue
      num_coincidentes = len(tokens_comunes_todos) * 0.3

    marca_coincide = _coincide_marca(marca_objetivo, candidato)

    # Penalizacion por categoria diferente
    cat_candidato = normalizar_texto_similitud(candidato.get("categoria"))
    factor_categoria = _calcular_penalizacion_categoria(categoria_objetivo, cat_candidato, marca_coincide)

    # Umbral minimo segun categoria
    umbral_minimo = 3 if factor_categoria < 0.5 else 2
    if not marca_coincide and num_coincidentes < umbral_minimo:
      continue

    # Coincidencia de tipo de producto
    nombre_candidato_largo = (nombre_candidato + " " + normalizar_texto_similitud(candidato.get("marca") or "")).strip()
    tipo_candidato = _extraer_token_tipo(nombre_candidato_largo)
    tipo_coincide = 1 if (tipo_objetivo and tipo_candidato and tipo_objetivo == tipo_candidato) else 0

    coincidencia_exacta_categoria = 1 if (categoria_objetivo and cat_candidato and categoria_objetivo == cat_candidato) else 0

    proporcion_tokens = num_coincidentes / total_tokens_objetivo

    # Puntuacion compuesta: prioriza tokens coincidentes, tipo de producto, marca, categoria
    puntuacion_compuesta = (
      num_coincidentes * 10.0
      + tipo_coincide * 5.0
      + int(marca_coincide) * 3.0
      + coincidencia_exacta_categoria * 2.0
      + proporcion_tokens * 1.0
    ) * factor_categoria

    clave_ordenamiento = (-puntuacion_compuesta, -num_coincidentes, -tipo_coincide, -coincidencia_exacta_categoria, -proporcion_tokens)
    productos_puntuados.append((clave_ordenamiento, candidato, num_coincidentes))

  productos_puntuados.sort(key=lambda x: x[0])

  productos_similares: list[dict[str, object | None]] = []
  for clave, candidato, n_coincidentes in productos_puntuados:
    precio_candidato = candidato.get("precio_actual")
    if precio_candidato is None or precio_candidato == 0:
      continue

    precio_objetivo = producto_objetivo.get("precio_actual")
    diferencia_precio = None
    if precio_objetivo not in (None, 0):
      diferencia_precio = round(((float(precio_objetivo) - float(precio_candidato)) / float(precio_candidato)) * 100, 2)

    # Similarity basado en tokens coincidentes sobre total objetivo
    similarity_score = min(1.0, n_coincidentes / total_tokens_objetivo) if total_tokens_objetivo > 0 else 0.0

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


def resumir_precios_similares(productos_similares: Iterable[dict[str, object | None]]) -> tuple[float | None, float | None, float | None]:
  """Calcula precio promedio ponderado, minimo y maximo de productos similares.

  Los pesos se basan en el similarity_score de cada producto.
  """
  elementos_con_precio = [elemento for elemento in productos_similares if elemento.get("precio_actual") is not None]
  if not elementos_con_precio:
    return None, None, None

  pesos = np.array([max(float(elemento.get("similarity_score") or 0.0), 0.01) for elemento in elementos_con_precio], dtype=float)
  precios = np.array([float(elemento["precio_actual"]) for elemento in elementos_con_precio], dtype=float)
  promedio_ponderado = float(np.average(precios, weights=pesos))
  precio_minimo = float(np.min(precios))
  precio_maximo = float(np.max(precios))
  return promedio_ponderado, precio_minimo, precio_maximo
