from __future__ import annotations

"""Recomendador de precios basado en FAISS y SentenceTransformers.

Usa embeddings semanticos para encontrar productos similares y sugerir
precios basados en el comportamiento del mercado.
"""

from typing import List, Dict, Any
import threading
from difflib import SequenceMatcher
import numpy as np

# Importaciones perezosas para evitar cuelgues durante la carga del módulo
SentenceTransformer = None
faiss = None

def _cargar_sentence_transformer():
  """Carga SentenceTransformer de forma perezosa."""
  global SentenceTransformer
  if SentenceTransformer is None or SentenceTransformer is True:
    try:
      from sentence_transformers import SentenceTransformer as ST
      SentenceTransformer = ST
    except Exception:
      SentenceTransformer = False
  return SentenceTransformer if SentenceTransformer not in (True, False, None) else None

def _cargar_faiss():
  """Carga FAISS de forma perezosa."""
  global faiss
  if faiss is None or faiss is True:
    try:
      import faiss as f
      faiss = f
    except Exception:
      faiss = False
  return faiss if faiss not in (True, False, None) else None

from Backend.conexion_base import db
from Backend.recomendacion_precio import rankear_productos_similares
from Backend.recomendacion_precio.similitud import normalizar_texto_similitud, tokenizar_texto

_CANDADO = threading.Lock()


def _texto_producto(producto: Dict[str, Any]) -> str:
  """Construye texto normalizado para embeddings desde un producto."""
  marca = producto.get("marca") or ""
  categoria = producto.get("categoria") or ""
  nombre = producto.get("nombre") or ""

  marca_norm = normalizar_texto_similitud(marca)
  categoria_norm = normalizar_texto_similitud(categoria)
  nombre_norm = normalizar_texto_similitud(nombre)

  return f"Marca: {marca_norm}\nCategoria: {categoria_norm}\nNombre: {nombre_norm}"


class RecomendadorFaiss:
  """Recomendador local basado en FAISS y embeddings de SentenceTransformers."""

  def __init__(self):
    self._modelo = None
    self._indice = None
    self._metadatos: List[Dict[str, Any]] = []
    self._dim = 384
    self._firma = None

  def _cargar_modelo(self):
    """Carga el modelo de embeddings si no esta cargado."""
    st = _cargar_sentence_transformer()
    if st is None:
      raise RuntimeError("Paquete 'sentence-transformers' no esta instalado.")
    if self._modelo is None:
      self._modelo = st("sentence-transformers/all-MiniLM-L6-v2")

  def _construir_indice(self, firma: tuple[int, str]):
    """Construye o reconstruye el indice FAISS desde el catalogo de productos."""
    f = _cargar_faiss()
    if f is None:
      raise RuntimeError("Paquete 'faiss' no esta instalado (use faiss-cpu).")

    catalogo = db.cargar_catalogo_similitud(firma)
    textos = [_texto_producto(p) for p in catalogo]
    vectores = self._modelo.encode(textos, convert_to_numpy=True)
    if vectores.ndim == 1:
      vectores = np.expand_dims(vectores, axis=0)

    f.normalize_L2(vectores)
    indice = f.IndexFlatIP(self._dim)
    indice.add(vectores.astype("float32"))

    self._indice = indice
    self._metadatos = catalogo
    self._firma = firma

  def asegurar_indice(self):
    """Asegura que exista un indice actualizado para el catalogo actual."""
    with _CANDADO:
      firma = db.obtener_firma_catalogo_similitud()
      if self._indice is None or self._firma != firma:
        self._cargar_modelo()
        self._construir_indice(firma)

  def _similaridad_textual(self, texto_a: str, texto_b: str) -> float:
    return float(SequenceMatcher(None, texto_a, texto_b).ratio())

  def _buscar_por_texto(self, texto: str, top_k: int = 20, min_ratio: float = 0.45) -> List[Dict[str, Any]]:
    """Busqueda alternativa por similitud textual cuando FAISS no esta disponible."""
    texto_base = normalizar_texto_similitud(texto)
    if not texto_base:
      return []

    candidatos: List[Dict[str, Any]] = []
    for meta in self._metadatos:
      nombre = normalizar_texto_similitud(str(meta.get("nombre") or ""))
      marca = normalizar_texto_similitud(str(meta.get("marca") or ""))
      categoria = normalizar_texto_similitud(str(meta.get("categoria") or ""))
      textos_comparar = [nombre, marca, categoria]
      mejor_sim = max(self._similaridad_textual(texto_base, campo) for campo in textos_comparar if campo)
      if mejor_sim >= min_ratio:
        fila = meta.copy()
        fila["similitud"] = mejor_sim
        candidatos.append(fila)

    candidatos.sort(key=lambda item: item["similitud"], reverse=True)
    return candidatos[:top_k]

  def _codificar(self, texto: str) -> np.ndarray:
    """Genera el vector embedding para un texto dado."""
    self._cargar_modelo()
    vec = self._modelo.encode([texto], convert_to_numpy=True)
    if vec.ndim > 1:
      vec = vec[0]
    vec = vec.astype("float32")
    f = _cargar_faiss()
    if f:
      f.normalize_L2(vec)
    return vec

  def buscar(self, texto: str, top_k: int = 20, min_sim: float = 0.25) -> List[Dict[str, Any]]:
    """Busca productos similares al texto y devuelve metadatos con puntuacion.

    Usa FAISS para busqueda semantica; si no encuentra suficientes resultados,
    complementa con busqueda textual.
    """
    self.asegurar_indice()
    if self._indice.ntotal == 0:
      return self._buscar_por_texto(texto, top_k=top_k, min_ratio=min_sim)

    vec = self._codificar(texto)
    D, I = self._indice.search(np.expand_dims(vec, axis=0), top_k)
    puntuaciones = D[0].tolist()
    indices = I[0].tolist()
    resultados: List[Dict[str, Any]] = []
    for puntuacion, idx in zip(puntuaciones, indices):
      if idx < 0:
        continue
      simil = float(puntuacion)
      if simil >= min_sim:
        meta = self._metadatos[idx].copy()
        meta["similitud"] = simil
        resultados.append(meta)

    if len(resultados) >= top_k:
      return resultados[:top_k]

    # Complementar con busqueda textual
    textual = self._buscar_por_texto(texto, top_k=top_k, min_ratio=min_sim)
    ids_existentes = {item.get("id_producto") for item in resultados}
    for item in textual:
      if item.get("id_producto") not in ids_existentes:
        resultados.append(item)
        ids_existentes.add(item.get("id_producto"))
      if len(resultados) >= top_k:
        break

    return resultados[:top_k]


_RECOMENDADOR: RecomendadorFaiss | None = None


def obtener_recomendador() -> RecomendadorFaiss:
  """Devuelve una instancia singleton del recomendador FAISS."""
  global _RECOMENDADOR
  if _RECOMENDADOR is None:
    _RECOMENDADOR = RecomendadorFaiss()
  return _RECOMENDADOR


def _recomendar_precio_simple(
  marca: str | None,
  categoria: str | None,
  nombre: str,
  top_k: int = 10,
) -> List[Dict[str, Any]]:
  """Recomendacion simple basada en texto cuando FAISS no esta disponible."""
  firma = db.obtener_firma_catalogo_similitud()
  catalogo = db.cargar_catalogo_similitud(firma)
  objetivo = {
    "id_producto": None,
    "nombre": nombre,
    "marca": marca,
    "categoria": categoria,
    "precio_actual": None,
  }
  similares = rankear_productos_similares(objetivo, catalogo, limit=top_k)

  if not similares:
    candidatos = [item for item in catalogo if item.get("precio_actual") is not None]
    return candidatos[:top_k]

  for item in similares:
    if item.get("similitud") is None and item.get("similarity_score") is not None:
      item["similitud"] = float(item.get("similarity_score"))
  return similares


def _fusionar_resultados_similares(
  resultados_faiss: list[Dict[str, Any]],
  resultados_texto: list[Dict[str, Any]],
  nombre_objetivo: str,
  top_k: int = 10,
) -> list[Dict[str, Any]]:
  """Fusiona resultados FAISS y textuales con boosting por tokens coincidentes.

  Primero identifica cada resultado por su id_producto, luego combina
  puntuaciones y aplica un boost si hay tokens compartidos con el objetivo.
  """
  texto_normalizado = normalizar_texto_similitud(nombre_objetivo)
  tokens_objetivo = tokenizar_texto(texto_normalizado)

  ids_texto = {str(item.get("id_producto") or "").strip() for item in resultados_texto if item.get("id_producto")}

  fusionados: dict[str, dict[str, Any]] = {}
  for item in resultados_faiss + resultados_texto:
    id_producto = str(item.get("id_producto") or "").strip()
    if not id_producto:
      continue
    existente = fusionados.get(id_producto, {})
    puntuacion_faiss = float(item.get("similitud") or item.get("similarity_score") or 0.0)
    puntuacion_texto = float(existente.get("puntuacion_texto") or 0.0)

    # Si el item viene de FAISS, usar su puntuacion FAISS
    if item.get("similitud") is not None or item.get("similarity_score") is not None:
      existente["puntuacion_faiss"] = max(float(existente.get("puntuacion_faiss") or 0.0), puntuacion_faiss)
      if id_producto in ids_texto:
        existente["fuente"] = "combinada"

    # Si el item viene de texto
    if id_producto in ids_texto:
      existente["puntuacion_texto"] = max(float(existente.get("puntuacion_texto") or 0.0), puntuacion_faiss)
      existente["fuente"] = existente.get("fuente", "texto")

    existente.update(item)
    fusionados[id_producto] = existente

  resultados_finales: list[dict[str, Any]] = []
  for item in fusionados.values():
    nombre_normalizado = normalizar_texto_similitud(str(item.get("nombre") or ""))
    tokens_candidato = tokenizar_texto(nombre_normalizado)
    tokens_compartidos = tokens_objetivo.intersection(tokens_candidato)
    boost = 0.0
    if tokens_compartidos:
      boost += 0.25 + min(0.15, 0.05 * len(tokens_compartidos))
    puntuacion_base = max(float(item.get("puntuacion_faiss") or 0.0), float(item.get("puntuacion_texto") or 0.0))
    item["puntuacion_final"] = min(1.0, puntuacion_base + boost)
    resultados_finales.append(item)

  resultados_finales.sort(key=lambda x: x.get("puntuacion_final", 0.0), reverse=True)
  return resultados_finales[:top_k]


def recomendar_precio(marca: str | None, categoria: str | None, nombre: str, top_k: int = 10, min_sim: float = 0.6) -> dict:
  """Genera una recomendacion de precio para el producto dado.

  Busca productos similares usando FAISS (si disponible) o similitud textual,
  calcula un precio sugerido como promedio ponderado de los similares.

  Retorna:
    dict con precio_sugerido, precio_min, precio_max y lista de similares.
  """
  marca_norm = normalizar_texto_similitud(marca)
  categoria_norm = normalizar_texto_similitud(categoria)
  nombre_norm = normalizar_texto_similitud(nombre)

  texto = f"Marca: {marca_norm}\nCategoria: {categoria_norm}\nNombre: {nombre_norm}"
  similares: List[Dict[str, Any]] = []

  # Intentar con FAISS
  try:
    recomendador = obtener_recomendador()
    similares = recomendador.buscar(texto, top_k=top_k, min_sim=min_sim)
  except Exception:
    similares = []

  # Complementar con busqueda textual
  texto_similares = _recomendar_precio_simple(marca, categoria, nombre, top_k=top_k)
  similares = _fusionar_resultados_similares(similares, texto_similares, nombre, top_k=top_k)

  if not similares:
    similares = _recomendar_precio_simple(marca, categoria, nombre, top_k=top_k)

  # Filtrar solo los que tienen precio
  similares_validos = [s for s in similares if s.get("precio_actual") is not None]
  if not similares_validos:
    return {
      "precio_sugerido": None,
      "precio_min": None,
      "precio_max": None,
      "similares": [],
    }

  precios = [float(s.get("precio_actual")) for s in similares_validos]
  sims = [float(s.get("similitud") or s.get("similarity_score") or s.get("puntuacion_final") or 0.0) for s in similares_validos]

  pesos = np.array(sims, dtype=float)
  precios_arr = np.array(precios, dtype=float)
  if pesos.sum() <= 0:
    precio_sugerido = float(np.mean(precios_arr))
  else:
    precio_sugerido = float((pesos * precios_arr).sum() / pesos.sum())

  precio_min = float(np.min(precios_arr))
  precio_max = float(np.max(precios_arr))

  similares_salida = [
    {
      "id_producto": s.get("id_producto"),
      "nombre": s.get("nombre"),
      "precio_actual": float(s.get("precio_actual")),
      "similitud": round(float(s.get("similitud") or s.get("similarity_score") or s.get("puntuacion_final") or 0.0), 4),
    }
    for s in similares_validos
  ]

  return {
    "precio_sugerido": round(precio_sugerido, 2),
    "precio_min": round(precio_min, 2),
    "precio_max": round(precio_max, 2),
    "similares": similares_salida,
  }
