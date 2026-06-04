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


def normalize_similarity_text(value: object | None) -> str:
  if value is None:
    return ""
  cleaned = " ".join(str(value).replace("/", " ").replace("-", " ").split())
  return cleaned.lower()


def build_product_profile(product: dict[str, object | None]) -> str:
  parts = [normalize_similarity_text(product.get("nombre"))]
  marca = normalize_similarity_text(product.get("marca"))
  categoria = normalize_similarity_text(product.get("categoria"))
  if marca:
    parts.append(marca)
  if categoria:
    parts.append(categoria)
  profile = " ".join(p for p in parts if p)
  return profile or normalize_similarity_text(product.get("id_producto")) or "producto"


def fuzzy_similarity(left_text: str, right_text: str) -> float:
  """Compute a token-aware fuzzy similarity between two strings.

  Uses `token_sort_ratio` and `token_set_ratio` from rapidfuzz and returns
  a normalized score in [0.0, 1.0]. This handles reordered words and
  partial overlaps better than raw Levenshtein for product names.
  """
  left_value = normalize_similarity_text(left_text)
  right_value = normalize_similarity_text(right_text)
  if not left_value and not right_value:
    return 1.0
  if not left_value or not right_value:
    return 0.0

  # token-based ratios are in 0-100
  if _HAS_RAPIDFUZZ and fuzz is not None:
    try:
      ts = float(fuzz.token_sort_ratio(left_value, right_value))
      tset = float(fuzz.token_set_ratio(left_value, right_value))
    except Exception:
      ts = float(fuzz.ratio(left_value, right_value))
      tset = ts
  else:
    ratio = difflib.SequenceMatcher(None, left_value, right_value).ratio()
    ts = ratio * 100.0
    tset = ts

  # prefer token_set (handles partial overlaps) but keep token_sort influence
  base_score = (0.6 * tset + 0.4 * ts) / 100.0

  # brand/category bonuses will be applied in the caller where product dicts are available
  return max(0.0, min(1.0, float(base_score)))


def rank_similar_products(
  target_product: dict[str, object | None],
  catalog: list[dict[str, object | None]],
  limit: int = 5,
  exclude_product_id: str | None = None,
) -> list[dict[str, object | None]]:
  if not catalog:
    return []

  target_name = build_product_profile(target_product)
  target_id = str(exclude_product_id or "").strip().upper() or None

  scored_products: list[tuple[float, dict[str, object | None]]] = []
  for candidate in catalog:
    candidate_id = str(candidate.get("id_producto") or "").strip().upper()
    if target_id and candidate_id == target_id:
      continue

    raw_score = fuzzy_similarity(target_name, build_product_profile(candidate))

    # apply brand/category bonuses
    bonus = 0.0
    try:
      target_brand = normalize_similarity_text(target_product.get("marca"))
      cand_brand = normalize_similarity_text(candidate.get("marca"))
      if target_brand and cand_brand and target_brand == cand_brand:
        bonus += 0.25
    except Exception:
      pass
    try:
      target_cat = normalize_similarity_text(target_product.get("categoria"))
      cand_cat = normalize_similarity_text(candidate.get("categoria"))
      if target_cat and cand_cat and target_cat == cand_cat:
        bonus += 0.15
    except Exception:
      pass

    score = min(1.0, raw_score + bonus)

    # enforce a minimum similarity to avoid unrelated results (tunable)
    MIN_SIMILARITY = 0.50
    if score < MIN_SIMILARITY:
      continue
    if score <= 0:
      continue

    scored_products.append((score, candidate))

  scored_products.sort(key=lambda item: item[0], reverse=True)

  similar_products: list[dict[str, object | None]] = []
  for score, candidate in scored_products:
    candidate_price = candidate.get("precio_actual")
    target_price = target_product.get("precio_actual")
    price_gap = None
    if candidate_price not in (None, 0) and target_price not in (None, 0):
      price_gap = round(((float(target_price) - float(candidate_price)) / float(candidate_price)) * 100, 2)

    similar_products.append(
      {
        "id_producto": candidate.get("id_producto"),
        "nombre": candidate.get("nombre"),
        "marca": candidate.get("marca"),
        "categoria": candidate.get("categoria"),
        "precio_actual": candidate_price,
        "precio_fabricacion": candidate.get("precio_fabricacion"),
        "stock": candidate.get("stock"),
        "fecha_actualizacion": candidate.get("fecha_actualizacion"),
        "similarity_score": round(score, 4),
        "price_gap_percent": price_gap,
      }
    )

    if len(similar_products) >= limit:
      break

  return similar_products


def summarize_similarity_prices(similar_products: Iterable[dict[str, object | None]]) -> tuple[float | None, float | None, float | None]:
  priced_items = [item for item in similar_products if item.get("precio_actual") is not None]
  if not priced_items:
    return None, None, None

  weights = np.array([max(float(item.get("similarity_score") or 0.0), 0.01) for item in priced_items], dtype=float)
  prices = np.array([float(item["precio_actual"]) for item in priced_items], dtype=float)
  weighted_average = float(np.average(prices, weights=weights))
  minimum_price = float(np.min(prices))
  maximum_price = float(np.max(prices))
  return weighted_average, minimum_price, maximum_price