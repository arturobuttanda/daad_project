from __future__ import annotations

from typing import List, Dict, Any
import threading
import re
import unicodedata
from difflib import SequenceMatcher
import numpy as np

try:
  from sentence_transformers import SentenceTransformer
except Exception:
  SentenceTransformer = None

try:
  import faiss
except Exception:
  faiss = None

from Backend.conexion_base import db
from Backend.recomendacion_precio import rankear_productos_similares
from Backend.recomendacion_precio.similitud import normalizar_texto_similitud, tokenizar_texto

_LOCK = threading.Lock()


def _texto_producto(product: Dict[str, Any]) -> str:
  """Construye texto normalizado (sin acentos, minúsculas) para embeddings."""
  marca = product.get("marca") or ""
  categoria = product.get("categoria") or ""
  nombre = product.get("nombre") or ""
  
  marca_norm = normalizar_texto_similitud(marca)
  categoria_norm = normalizar_texto_similitud(categoria)
  nombre_norm = normalizar_texto_similitud(nombre)
  
  return f"Marca: {marca_norm}\nCategoria: {categoria_norm}\nNombre: {nombre_norm}"


class RecomendadorFaiss:
  """Recomendador local basado en FAISS y embeddings de SentenceTransformers.

  Nombres en español para facilitar la lectura y documentación.
  """
  def __init__(self):
    self._modelo = None
    self._indice = None
    self._metadatos: List[Dict[str, Any]] = []
    self._dim = 384
    self._firma = None

  def _cargar_modelo(self):
    """Carga el modelo de embeddings si no está cargado."""
    if SentenceTransformer is None:
      raise RuntimeError("Paquete 'sentence-transformers' no está instalado.")
    if self._modelo is None:
      self._modelo = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

  def _construir_indice(self, firma: tuple[int, str]):
    """Construye o reconstruye el índice FAISS a partir del catálogo de productos."""
    if faiss is None:
      raise RuntimeError("Paquete 'faiss' no está instalado (use faiss-cpu).")

    catalogo = db.cargar_catalogo_similitud(firma)
    textos = [_texto_producto(p) for p in catalogo]
    vectores = self._modelo.encode(textos, convert_to_numpy=True)
    if vectores.ndim == 1:
      vectores = np.expand_dims(vectores, axis=0)

    # Normalizar y construir índice
    faiss.normalize_L2(vectores)
    indice = faiss.IndexFlatIP(self._dim)
    indice.add(vectores.astype("float32"))

    self._indice = indice
    self._metadatos = catalogo
    self._firma = firma

  def asegurar_indice(self):
    """Asegura que exista un índice actualizado para el catálogo actual."""
    with _LOCK:
      firma = db.obtener_firma_catalogo_similitud()
      if self._indice is None or self._firma != firma:
        self._cargar_modelo()
        self._construir_indice(firma)

  def _limpiar_texto(self, texto: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, espacios limpios."""
    return normalizar_texto_similitud(texto)

  def _similaridad_textual(self, texto_a: str, texto_b: str) -> float:
    return float(SequenceMatcher(None, texto_a, texto_b).ratio())

  def _buscar_por_fuzzy(self, texto: str, top_k: int = 20, min_ratio: float = 0.45) -> List[Dict[str, Any]]:
    texto_base = self._limpiar_texto(texto)
    if not texto_base:
      return []

    candidatos: List[Dict[str, Any]] = []
    for meta in self._metadatos:
      nombre = self._limpiar_texto(str(meta.get("nombre") or ""))
      marca = self._limpiar_texto(str(meta.get("marca") or ""))
      categoria = self._limpiar_texto(str(meta.get("categoria") or ""))
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
    faiss.normalize_L2(vec)
    return vec

  def buscar(self, texto: str, top_k: int = 20, min_sim: float = 0.25) -> List[Dict[str, Any]]:
    """Busca los productos más similares al texto y devuelve metadatos con puntuación.

    Si FAISS no encuentra suficientes resultados, cae en un filtro fuzzy basado en texto.
    """
    self.asegurar_indice()
    if self._indice.ntotal == 0:
      return self._buscar_por_fuzzy(texto, top_k=top_k, min_ratio=min_sim)

    vec = self._codificar(texto)
    D, I = self._indice.search(np.expand_dims(vec, axis=0), top_k)
    scores = D[0].tolist()
    indices = I[0].tolist()
    resultados: List[Dict[str, Any]] = []
    for score, idx in zip(scores, indices):
      if idx < 0:
        continue
      simil = float(score)
      if simil >= min_sim:
        meta = self._metadatos[idx].copy()
        meta["similitud"] = simil
        resultados.append(meta)

    if len(resultados) >= top_k:
      return resultados[:top_k]

    fuzzy = self._buscar_por_fuzzy(texto, top_k=top_k, min_ratio=min_sim)
    existing_ids = {item.get("id_producto") for item in resultados}
    for item in fuzzy:
      if item.get("id_producto") not in existing_ids:
        resultados.append(item)
      if len(resultados) >= top_k:
        break

    return resultados[:top_k]


_RECOMENDADOR: RecomendadorFaiss | None = None


def obtener_recomendador() -> RecomendadorFaiss:
  """Devuelve una instancia singleton del recomendador."""
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
  """Usa una recomendación simple basada en texto cuando FAISS no está disponible."""
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
  faiss_results: list[Dict[str, Any]],
  text_results: list[Dict[str, Any]],
  nombre_objetivo: str,
  top_k: int = 10,
) -> list[Dict[str, Any]]:
  """Fusiona resultados FAISS y textuales dando preferencia a coincidencias de token."""
  normalized_target = normalizar_texto_similitud(nombre_objetivo)
  target_tokens = tokenizar_texto(normalized_target)

  merged: dict[str, dict[str, Any]] = {}
  for item in faiss_results + text_results:
    product_id = str(item.get("id_producto") or "").strip()
    if not product_id:
      continue
    existing = merged.get(product_id, {})
    score_faiss = float(item.get("similitud") or item.get("similarity_score") or 0.0)
    score_text = float(existing.get("score_text") or 0.0)
    if item.get("similitud") is not None or item.get("similarity_score") is not None:
      if existing.get("source") == "text" and score_faiss > score_text:
        existing["source"] = "combined"
      existing["score_faiss"] = max(float(existing.get("score_faiss") or 0.0), score_faiss)
    if item in text_results:
      existing["score_text"] = max(float(existing.get("score_text") or 0.0), score_faiss)
      existing["source"] = existing.get("source", "text")
    existing.update(item)
    merged[product_id] = existing

  final_results: list[dict[str, Any]] = []
  for item in merged.values():
    normalized_name = normalizar_texto_similitud(str(item.get("nombre") or ""))
    candidate_tokens = tokenizar_texto(normalized_name)
    shared_tokens = target_tokens.intersection(candidate_tokens)
    boost = 0.0
    if shared_tokens:
      boost += 0.25 + min(0.15, 0.05 * len(shared_tokens))
    base_score = max(float(item.get("score_faiss") or 0.0), float(item.get("score_text") or 0.0))
    item["final_score"] = min(1.0, base_score + boost)
    final_results.append(item)

  final_results.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
  return final_results[:top_k]


def recomendar_precio(marca: str | None, categoria: str | None, nombre: str, top_k: int = 10, min_sim: float = 0.6) -> dict:
  """Genera una recomendación de precio para el producto dado.

  Devuelve un diccionario con `precio_sugerido`, `precio_min`, `precio_max` y `similares`.
  """
  # Normalizar texto para búsqueda consistente
  marca_norm = normalizar_texto_similitud(marca)
  categoria_norm = normalizar_texto_similitud(categoria)
  nombre_norm = normalizar_texto_similitud(nombre)
  
  texto = f"Marca: {marca_norm}\nCategoria: {categoria_norm}\nNombre: {nombre_norm}"
  similares: List[Dict[str, Any]] = []

  try:
    recomendador = obtener_recomendador()
    similares = recomendador.buscar(texto, top_k=top_k, min_sim=min_sim)
  except Exception:
    similares = []

  # Siempre obtener un respaldo de similitud basada en texto puro
  text_similares = _recomendar_precio_simple(marca, categoria, nombre, top_k=top_k)
  similares = _fusionar_resultados_similares(similares, text_similares, nombre, top_k=top_k)

  if not similares:
    similares = _recomendar_precio_simple(marca, categoria, nombre, top_k=top_k)

  similares_validos = [s for s in similares if s.get("precio_actual") is not None]
  if not similares_validos:
    return {
      "precio_sugerido": None,
      "precio_min": None,
      "precio_max": None,
      "similares": [],
    }

  precios = [float(s.get("precio_actual")) for s in similares_validos]
  sims = [float(s.get("similitud") or s.get("similarity_score") or 0.0) for s in similares_validos]

  pesos = np.array(sims, dtype=float)
  precios_arr = np.array(precios, dtype=float)
  if pesos.sum() <= 0:
    precio_sugerido = float(np.mean(precios_arr))
  else:
    precio_sugerido = float((pesos * precios_arr).sum() / pesos.sum())

  precio_min = float(np.min(precios_arr))
  precio_max = float(np.max(precios_arr))

  similares_output = [
    {
      "id_producto": s.get("id_producto"),
      "nombre": s.get("nombre"),
      "precio_actual": float(s.get("precio_actual")),
      "similitud": round(float(s.get("similitud") or s.get("similarity_score") or 0.0), 4),
    }
    for s in similares_validos
  ]

  return {
    "precio_sugerido": round(precio_sugerido, 2),
    "precio_min": round(precio_min, 2),
    "precio_max": round(precio_max, 2),
    "similares": similares_output,
  }


# Alias para compatibilidad
recommend_price = recomendar_precio
get_recommender = obtener_recomendador
