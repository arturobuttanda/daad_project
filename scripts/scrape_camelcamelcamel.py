#!/usr/bin/env python3
"""
Extracción de productos populares e historial de precios desde camelcamelcamel.com.

Requisitos (entorno):
  python -m venv .venv
  .venv\\Scripts\\activate          # Windows
  pip install -r scripts/requirements-camelcamelcamel.txt
  python -m playwright install chromium

Nota: camelcamelcamel.com usa Cloudflare. El script orquesta con Playwright
(navegación, pausas, interceptación de red) y usa curl_cffi como capa TLS de
respaldo cuando el navegador automatizado recibe 403.

En WSL/Linux, si Chromium falla con "libnspr4.so: cannot open shared object file",
instale dependencias (`sudo playwright install-deps chromium`) o use --tls-only.

Uso:
  # Primera ejecución: resolver Cloudflare en ventana visible (una vez)
  python scripts/scrape_camelcamelcamel.py --init-session

  # Extracción completa (100 productos, salida JSON)
  python scripts/scrape_camelcamelcamel.py --output productos_camel.json

  # Prueba rápida
  python scripts/scrape_camelcamelcamel.py --limit 3 --output prueba.json
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

import numpy as np
from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import (
    BrowserContext,
    Page,
    Response,
    sync_playwright,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_URL = "https://camelcamelcamel.com"
CHARTS_BASE = "https://charts.camelcamelcamel.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
ASIN_RE = re.compile(r"^B[0-9A-Z]{9}$")
PRODUCT_LINK_RE = re.compile(r"/product/([A-Z0-9]{10})")
MONTH_DATE_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})",
    re.I,
)
PRICE_IN_CELL_RE = re.compile(
    r"\$\s*([\d,]+\.?\d*)\s*(?:\(\s*([A-Z][a-z]{2,8})\s+(\d{1,2}),?\s+(\d{4})\s*\))?",
    re.I,
)
MONITORING_SINCE_RE = re.compile(
    r"monitoring it on(?: on)?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})",
    re.I,
)

# Colores de la línea Amazon en charts.camelcamelcamel.com (el sitio cambió el tono en 2025+)
CHART_AMAZON_COLORS = (
    (99, 168, 94),   # verde actual
    (99, 168, 164),  # cian histórico
)
CHART_COLOR_TOLERANCE = 35
CHART_WIDTH = 2400
CHART_HEIGHT = 800

LISTING_PATHS = (
    ("/popular?deal=0&p={page}", "popular"),
    ("/top_drops?t=recent&p={page}", "top_drops"),
)

log = logging.getLogger("camelcamelcamel")


@dataclass
class ProductStub:
    asin: str
    nombre: str
    categoria: str = "Sin categoría"
    precio_actual: float | None = None
    fuente: str = ""


@dataclass
class PricePoint:
    fecha: date
    precio: float


@dataclass
class ScrapeConfig:
    output: Path
    limit: int = 100
    history_start_date: date = date(2024, 1, 1)
    profile_dir: Path = field(default_factory=lambda: Path(".camelcamel_playwright_profile"))
    headed: bool = False
    init_session: bool = False
    delay_min: float = 2.0
    delay_max: float = 5.0
    timeout_ms: int = 120_000
    use_chart_fallback: bool = True
    tls_only: bool = False
    granularity: str = "daily"  # daily | weekly
    fill_daily_gaps: bool = True


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def human_pause(cfg: ScrapeConfig) -> None:
    time.sleep(random.uniform(cfg.delay_min, cfg.delay_max))


def parse_us_price(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d,]+\.?\d*)", text.replace("$", "").replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_month_date(month: str, day: str, year: str) -> date:
    return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()


def is_cloudflare_challenge(html: str, title: str = "") -> bool:
    blob = (title + html).lower()
    return "just a moment" in blob or "cf-chl" in blob or "checking your browser" in blob


def _cffi_session():
    from curl_cffi import requests as cffi_requests

    return cffi_requests


def fetch_html_tls(url: str, max_retries: int = 3) -> str:
    """HTTP con curl_cffi (impersonate Chrome) con reintentos y backoff exponencial."""
    cffi = _cffi_session()
    backoff_delays = [10, 30, 60]  # segundos de espera entre reintentos
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = cffi.get(url, impersonate="chrome", timeout=60)
            if resp.status_code == 403:
                raise RuntimeError(f"HTTP 403 Forbidden en {url}")
            resp.raise_for_status()
            if is_cloudflare_challenge(resp.text):
                raise RuntimeError(f"Cloudflare activo en {url}")
            return resp.text
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                log.warning(
                    "Intento %s/%s fallido para %s (%s). Reintentando en %ss...",
                    attempt + 1, max_retries + 1, url, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error("Todos los reintentos agotados para %s: %s", url, exc)

    raise last_exc  # type: ignore[misc]


def fetch_bytes_tls(url: str, max_retries: int = 3) -> bytes:
    """Descarga binaria con curl_cffi con reintentos y backoff exponencial."""
    cffi = _cffi_session()
    backoff_delays = [10, 30, 60]
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = cffi.get(url, impersonate="chrome", timeout=60)
            if resp.status_code == 403:
                raise RuntimeError(f"HTTP 403 Forbidden en {url}")
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                log.warning(
                    "Intento %s/%s fallido (bytes) para %s (%s). Reintentando en %ss...",
                    attempt + 1, max_retries + 1, url, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error("Todos los reintentos agotados (bytes) para %s: %s", url, exc)

    raise last_exc  # type: ignore[misc]


def fetch_html(
    context: BrowserContext | None,
    page: Page | None,
    url: str,
    cfg: ScrapeConfig,
) -> str:
    """Obtiene HTML: APIRequest de Playwright y, si hace falta, curl_cffi (TLS)."""
    if cfg.tls_only or context is None:
        log.debug("TLS: %s", url)
        return fetch_html_tls(url)

    try:
        resp = context.request.get(url, timeout=min(cfg.timeout_ms, 45_000))
        if resp.ok and not is_cloudflare_challenge(resp.text()):
            return resp.text()
    except Exception as exc:
        log.debug("Playwright request falló para %s: %s", url, exc)

    log.info("Respaldo TLS (curl_cffi): %s", url)
    return fetch_html_tls(url)


def fetch_bytes(url: str, context: BrowserContext | None, cfg: ScrapeConfig) -> bytes:
    if cfg.tls_only or context is None:
        return fetch_bytes_tls(url)

    try:
        resp = context.request.get(url, timeout=cfg.timeout_ms)
        if resp.ok:
            body = resp.body()
            if len(body) > 500:
                return body
    except Exception as exc:
        log.debug("Playwright bytes falló para %s: %s", url, exc)

    log.debug("Respaldo TLS para binario: %s", url)
    return fetch_bytes_tls(url)


def bootstrap_cloudflare_cookies(context: BrowserContext) -> None:
    """
    Obtiene cookies válidas vía TLS fingerprint (curl_cffi) y las inyecta
    en el contexto Playwright antes de la primera navegación.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        log.warning("curl_cffi no instalado; omitiendo bootstrap de cookies.")
        return

    try:
        resp = cffi_requests.get(BASE_URL + "/popular", impersonate="chrome", timeout=60)
        cookies = [
            {
                "name": name,
                "value": value,
                "domain": ".camelcamelcamel.com",
                "path": "/",
                "secure": True,
                "httpOnly": name.startswith("cf_") or name == "cf_clearance",
            }
            for name, value in resp.cookies.items()
        ]
        if cookies:
            context.add_cookies(cookies)
            log.info("Cookies de sesión inyectadas (%s).", len(cookies))
    except Exception as exc:
        log.warning("No se pudieron obtener cookies de bootstrap: %s", exc)


def wait_for_real_page(page: Page, cfg: ScrapeConfig) -> bool:
    deadline = time.time() + cfg.timeout_ms / 1000
    while time.time() < deadline:
        title = page.title()
        html = page.content()
        if not is_cloudflare_challenge(html, title):
            if "camelcamelcamel" in page.url and (
                "/popular" in page.url
                or "/top_drops" in page.url
                or "/product/" in page.url
                or "Popular Products" in html
                or "Top Amazon Price Drops" in html
            ):
                return True
        page.wait_for_timeout(2_000)
    return False


# ---------------------------------------------------------------------------
# Paso 1 — Descubrimiento de productos
# ---------------------------------------------------------------------------


def parse_listing_products(html: str, source: str) -> list[ProductStub]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, ProductStub] = {}

    for anchor in soup.select("a[href*='/product/']"):
        href = anchor.get("href") or ""
        m = PRODUCT_LINK_RE.search(href)
        if not m:
            continue
        asin = m.group(1)
        if not ASIN_RE.match(asin):
            continue

        nombre = anchor.get_text(" ", strip=True)
        if len(nombre) < 8 or nombre.lower() == "view at amazon":
            continue

        parent = anchor.find_parent(["article", "li", "div", "tr"])
        precio = None
        if parent:
            pm = re.search(r"\$\s*([\d,]+\.?\d*)", parent.get_text(" ", strip=True))
            if pm:
                precio = parse_us_price(pm.group(0))

        if asin not in found or len(nombre) > len(found[asin].nombre):
            found[asin] = ProductStub(
                asin=asin,
                nombre=nombre,
                precio_actual=precio,
                fuente=source,
            )

    return list(found.values())


def discover_products(
    page: Page | None, context: BrowserContext | None, cfg: ScrapeConfig
) -> list[ProductStub]:
    collected: dict[str, ProductStub] = {}
    page_num = 1

    while len(collected) < cfg.limit and page_num <= 30:
        for path_tpl, source in LISTING_PATHS:
            if len(collected) >= cfg.limit:
                break
            url = urljoin(BASE_URL, path_tpl.format(page=page_num))
            log.info("Listado %s (página %s)", source, page_num)
            html = fetch_html(context, page, url, cfg)
            human_pause(cfg)
            for stub in parse_listing_products(html, source):
                if stub.asin not in collected:
                    collected[stub.asin] = stub
                if len(collected) >= cfg.limit:
                    break
        page_num += 1

    products = list(collected.values())[: cfg.limit]
    log.info("Productos únicos descubiertos: %s", len(products))
    return products


# ---------------------------------------------------------------------------
# Paso 2 — Historial de precios
# ---------------------------------------------------------------------------


def parse_product_metadata(html: str, asin: str) -> tuple[str, str, float | None, date | None, float | None, float | None]:
    """nombre, categoría, precio actual, fecha inicio tracking, min amazon, max amazon."""
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.find("h1")
    nombre = h1.get_text(" ", strip=True) if h1 else asin
    if "|" in nombre:
        nombre = nombre.split("|")[0].strip()

    categoria = "Sin categoría"
    for tr in soup.select("table.product_fields tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0].lower() == "category":
            categoria = " ".join(cells[1].split())
            break

    precio_actual = None
    min_amazon = max_amazon = None
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or cells[0] != "Amazon":
            continue
        # Current+ suele ser la 4ª columna
        if len(cells) >= 4:
            precio_actual = parse_us_price(cells[3])
        min_amazon = parse_us_price(cells[1])
        max_amazon = parse_us_price(cells[2])
        break

    tracking_start = None
    for p in soup.select("p, div"):
        text = p.get_text(" ", strip=True)
        m = MONITORING_SINCE_RE.search(text)
        if m:
            tracking_start = parse_month_date(m.group(1), m.group(2), m.group(3))
            break

    return nombre, categoria, precio_actual, tracking_start, min_amazon, max_amazon


def extract_points_from_summary_table(html: str) -> list[PricePoint]:
    """Puntos discretos de la tabla resumen (lowest/highest/current)."""
    soup = BeautifulSoup(html, "lxml")
    points: list[PricePoint] = []

    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or cells[0] != "Amazon":
            continue
        for cell in cells[1:]:
            price_m = re.search(r"\$\s*([\d,]+\.?\d*)", cell)
            if not price_m:
                continue
            precio = parse_us_price(price_m.group(0))
            dm = MONTH_DATE_RE.search(cell)
            if precio is not None and dm:
                d = parse_month_date(dm.group(1), dm.group(2), dm.group(3))
                points.append(PricePoint(d, precio))
    return points


def extract_points_from_raw_table(html: str) -> list[PricePoint]:
    """Tabla en bruto bajo la gráfica (si existe): columnas fecha + precio."""
    soup = BeautifulSoup(html, "lxml")
    points: list[PricePoint] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 5:
            continue
        header = [c.get_text(" ", strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        if not header:
            continue
        date_idx = price_idx = None
        for i, h in enumerate(header):
            if any(k in h for k in ("date", "fecha", "time", "day")):
                date_idx = i
            if any(k in h for k in ("price", "precio", "amazon")):
                price_idx = i
        if date_idx is None or price_idx is None:
            continue

        for tr in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) <= max(date_idx, price_idx):
                continue
            dm = MONTH_DATE_RE.search(cells[date_idx]) or re.search(
                r"(\d{4}-\d{2}-\d{2})", cells[date_idx]
            )
            precio = parse_us_price(cells[price_idx])
            if not precio:
                continue
            if dm:
                if dm.lastindex == 3:
                    d = parse_month_date(dm.group(1), dm.group(2), dm.group(3))
                else:
                    d = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
                points.append(PricePoint(d, precio))

    return points


def try_parse_network_payload(body: bytes, content_type: str) -> list[PricePoint]:
    points: list[PricePoint] = []
    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return points

    payload: Any = None
    if "json" in content_type or text.startswith("{") or text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
    elif "csv" in content_type or text.count(",") > 3:
        return parse_csv_points(text)

    if payload is None:
        # series Flot: [[ts_ms, price], ...]
        flot = re.findall(r"\[\s*(\d{9,13})\s*,\s*([\d.]+)\s*\]", text)
        for ts, price in flot:
            d = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).date()
            points.append(PricePoint(d, float(price)))
        return points

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
                ts, val = node[0], node[1]
                if ts > 1_000_000_000_000:
                    ts /= 1000
                if 10 < val < 1_000_000:
                    points.append(
                        PricePoint(
                            datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                            float(val),
                        )
                    )
                return
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)

    walk(payload)
    return points


def parse_csv_points(text: str) -> list[PricePoint]:
    points: list[PricePoint] = []
    for line in text.splitlines():
        if not line.strip() or line.lower().startswith("date"):
            continue
        parts = [p.strip() for p in re.split(r"[,;\t]", line) if p.strip()]
        if len(parts) < 2:
            continue
        precio = parse_us_price(parts[-1])
        dm = MONTH_DATE_RE.search(line) or re.search(r"(\d{4}-\d{2}-\d{2})", line)
        if precio and dm:
            if dm.lastindex == 3:
                d = parse_month_date(dm.group(1), dm.group(2), dm.group(3))
            else:
                d = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
            points.append(PricePoint(d, precio))
    return points


def build_chart_png_url(
    asin: str, width: int = CHART_WIDTH, height: int = CHART_HEIGHT
) -> str:
    params = urlencode(
        {
            "force": "1",
            "zero": "0",
            "w": width,
            "h": height,
            "desired": "false",
            "legend": "1",
            "ilt": "1",
            "tp": "all",
            "fo": "0",
            "lang": "en",
        }
    )
    return f"{CHARTS_BASE}/us/{asin}/amazon.png?{params}"


def _chart_line_mask(arr: np.ndarray) -> np.ndarray | None:
    """Máscara de píxeles de la línea de precio Amazon en el PNG del chart."""
    for rgb in CHART_AMAZON_COLORS:
        mask = (
            (np.abs(arr[:, :, 0].astype(int) - rgb[0]) <= CHART_COLOR_TOLERANCE)
            & (np.abs(arr[:, :, 1].astype(int) - rgb[1]) <= CHART_COLOR_TOLERANCE)
            & (np.abs(arr[:, :, 2].astype(int) - rgb[2]) <= CHART_COLOR_TOLERANCE)
        )
        if mask.sum() > 500:
            return mask
    return None


def _y_to_price(y: float, y_min: float, y_max: float, min_price: float, max_price: float) -> float:
    price_span = max(max_price - min_price, 0.01)
    return max_price - (y - y_min) / max(y_max - y_min, 1) * price_span


def sanitize_price_series(
    points: list[PricePoint],
    min_price: float | None,
    max_price: float | None,
    *,
    margin: float = 0.12,
) -> list[PricePoint]:
    """Elimina valores fuera del rango Amazon declarado en la ficha del producto."""
    if not points or min_price is None or max_price is None:
        return points
    lo = min_price * (1 - margin)
    hi = max_price * (1 + margin)
    cleaned = [p for p in points if lo <= p.precio <= hi]
    return cleaned if len(cleaned) >= 10 else points


def extract_points_from_chart_png(
    png_bytes: bytes,
    *,
    start: date,
    end: date,
    min_price: float,
    max_price: float,
) -> list[PricePoint]:
    """
    Traza la línea Amazon del PNG (charts.camelcamelcamel.com).
    Por columna X elige el tramo coherente con el precio del día anterior (evita saltos
    por leyenda/rejilla). Un punto por día calendario en el eje temporal del gráfico.
    """
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape

    mask = _chart_line_mask(arr)
    if mask is None:
        return []

    columns: dict[int, list[int]] = {}
    for x in range(w):
        ys = np.where(mask[:, x])[0]
        if len(ys) > 0:
            columns[x] = ys.tolist()

    if len(columns) < 10:
        return []

    all_ys = [y for ys in columns.values() for y in ys]
    y_min, y_max = float(min(all_ys)), float(max(all_ys))
    x_min, x_max = min(columns), max(columns)
    total_days = max((end - start).days, 1)

    by_date: dict[date, float] = {}
    prev_price: float | None = None

    for x in sorted(columns):
        day_offset = (x - x_min) / max(x_max - x_min, 1) * total_days
        d = start + timedelta(days=int(day_offset))
        candidates = [
            _y_to_price(float(y), y_min, y_max, min_price, max_price) for y in columns[x]
        ]
        if prev_price is None:
            price = float(np.median(candidates))
        else:
            price = min(candidates, key=lambda p: abs(p - prev_price))
        prev_price = price
        by_date[d] = round(price, 2)

    return [PricePoint(d, p) for d, p in sorted(by_date.items())]


def merge_points(*series: list[PricePoint]) -> list[PricePoint]:
    merged: dict[date, float] = {}
    for seq in series:
        for pt in seq:
            merged[pt.fecha] = pt.precio
    return [PricePoint(d, p) for d, p in sorted(merged.items())]


def filter_history_window(points: list[PricePoint], start_date: date) -> list[PricePoint]:
    if not points:
        return []
    filtered = [p for p in points if p.fecha >= start_date]
    return filtered if filtered else sorted(points, key=lambda p: p.fecha)


def format_daily_history(
    points: list[PricePoint],
    start_date: date,
    *,
    fill_gaps: bool = True,
) -> list[dict[str, Any]]:
    """
    Serie diaria. Camelcamelcamel registra cambios de precio (escalones);
    con fill_gaps=True propaga el último precio conocido a cada día calendario.
    """
    filtered = filter_history_window(points, start_date)
    if not filtered:
        return []

    by_date: dict[date, float] = {}
    for pt in filtered:
        by_date[pt.fecha] = pt.precio

    if not fill_gaps:
        return [
            {"fecha": d.isoformat(), "precio_registrado": round(p, 2)}
            for d, p in sorted(by_date.items())
        ]

    start = min(by_date)
    end = min(max(by_date), date.today())
    out: list[dict[str, Any]] = []
    last: float | None = None
    d = start
    while d <= end:
        if d in by_date:
            last = by_date[d]
        if last is not None:
            out.append({"fecha": d.isoformat(), "precio_registrado": round(last, 2)})
        d += timedelta(days=1)
    return out


def resample_weekly(points: list[PricePoint], start_date: date) -> list[dict[str, Any]]:
    filtered = filter_history_window(points, start_date)
    if not filtered:
        return []

    buckets: dict[tuple[int, int], list[PricePoint]] = defaultdict(list)
    for pt in filtered:
        iso = pt.fecha.isocalendar()
        buckets[(iso.year, iso.week)].append(pt)

    weekly: list[dict[str, Any]] = []
    for key in sorted(buckets):
        bucket = buckets[key]
        chosen = max(bucket, key=lambda p: p.fecha)
        weekly.append(
            {
                "fecha": chosen.fecha.isoformat(),
                "precio_registrado": round(chosen.precio, 2),
            }
        )
    return weekly


def format_history(points: list[PricePoint], cfg: ScrapeConfig) -> list[dict[str, Any]]:
    if cfg.granularity == "weekly":
        return resample_weekly(points, cfg.history_start_date)
    return format_daily_history(
        points,
        cfg.history_start_date,
        fill_gaps=cfg.fill_daily_gaps,
    )


def fetch_price_history(
    page: Page | None,
    context: BrowserContext | None,
    product: ProductStub,
    cfg: ScrapeConfig,
) -> tuple[list[dict[str, Any]], date | None]:
    captured: list[tuple[bytes, str]] = []
    capture_active = {"on": True}

    product_url = (
        f"{BASE_URL}/product/{product.asin}"
        "?active=price_amazon&context=price_history&tp=all"
    )
    log.info("Producto %s — historial", product.asin)

    if page is not None and not cfg.tls_only:

        def on_response(response: Response) -> None:
            if not capture_active["on"]:
                return
            try:
                url = response.url.lower()
                if response.status != 200:
                    return
                if not any(
                    k in url
                    for k in (
                        "camelcamelcamel",
                        "chart",
                        "price",
                        "history",
                        "amazon",
                        "csv",
                        "json",
                    )
                ):
                    return
                body = response.body()
                if len(body) < 30 or len(body) > 8_000_000:
                    return
                ct = (response.headers.get("content-type") or "").lower()
                if any(t in ct for t in ("json", "csv", "javascript", "text")) or url.endswith(
                    (".json", ".csv", ".js")
                ):
                    captured.append((body, ct))
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)
            page.wait_for_timeout(2_000)
        except Exception as exc:
            log.debug("goto producto %s: %s", product.asin, exc)

    human_pause(cfg)
    html = fetch_html(context, page, product_url, cfg)

    nombre, categoria, precio_tabla, tracking_start, min_p, max_p = parse_product_metadata(
        html, product.asin
    )
    product.nombre = nombre or product.nombre
    product.categoria = categoria
    if precio_tabla is not None:
        product.precio_actual = precio_tabla

    network_pts: list[PricePoint] = []
    for body, ct in captured:
        network_pts.extend(try_parse_network_payload(body, ct))

    table_pts = extract_points_from_raw_table(html)
    summary_pts = extract_points_from_summary_table(html)
    all_pts = merge_points(network_pts, table_pts, summary_pts)

    # Serie densa desde PNG Amazon (única fuente con granularidad diaria en camelcamelcamel)
    if cfg.use_chart_fallback:
        bounds_min, bounds_max = min_p, max_p
        if bounds_min is None or bounds_max is None:
            prices = [p.precio for p in all_pts]
            if prices:
                bounds_min, bounds_max = min(prices), max(prices)
            else:
                bounds_min, bounds_max = 1.0, 100.0
        start = tracking_start or (
            all_pts[0].fecha if all_pts else date.today() - timedelta(days=365 * 3)
        )
        end = date.today()
        chart_url = build_chart_png_url(product.asin)
        try:
            png_bytes = fetch_bytes(chart_url, context, cfg)
            chart_pts = extract_points_from_chart_png(
                png_bytes,
                start=start,
                end=end,
                min_price=bounds_min,
                max_price=bounds_max,
            )
            chart_pts = sanitize_price_series(chart_pts, min_p, max_p)
            if chart_pts:
                log.info(
                    "%s: %s puntos desde chart Amazon (tracking desde %s).",
                    product.asin,
                    len(chart_pts),
                    start.isoformat(),
                )
                if len(chart_pts) >= len(all_pts):
                    all_pts = chart_pts
                else:
                    all_pts = merge_points(all_pts, chart_pts)
        except Exception as exc:
            log.warning("%s: fallo al descargar chart PNG: %s", product.asin, exc)

    all_pts = sanitize_price_series(all_pts, min_p, max_p)
    capture_active["on"] = False

    earliest = min((p.fecha for p in all_pts), default=None)
    historial = format_history(all_pts, cfg)
    log.info(
        "%s: historial %s → %s registros.",
        product.asin,
        cfg.granularity,
        len(historial),
    )
    return historial, earliest


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

LINUX_BROWSER_DEPS_HINT = """
Chromium de Playwright no pudo arrancar (faltan librerías del sistema).

En WSL/Ubuntu/Debian instale dependencias y vuelva a intentar:
  sudo apt-get update
  sudo playwright install-deps chromium

O ejecute sin navegador (solo curl_cffi, suficiente para este scraper):
  python scripts/scrape_camelcamelcamel.py --tls-only --limit 3 --output prueba.json
"""


def _incremental_save(productos: list[dict[str, Any]], output: Path) -> None:
    """Guardado incremental para no perder progreso si el scraper falla."""
    partial_path = output.with_suffix(".partial.json")
    with partial_path.open("w", encoding="utf-8") as fh:
        json.dump({"productos": productos}, fh, ensure_ascii=False, indent=2)
    log.info("Guardado incremental: %s productos en %s", len(productos), partial_path)


def run_scraper_tls_only(cfg: ScrapeConfig) -> dict[str, Any]:
    """Modo sin Chromium: útil en WSL si falta libnspr4/libnss3."""
    if cfg.init_session:
        raise RuntimeError("--init-session requiere navegador; omita --tls-only.")

    log.info("Modo --tls-only (sin Chromium / Playwright browser)")
    cfg.tls_only = True
    productos: list[dict[str, Any]] = []
    skipped: list[str] = []

    stubs = discover_products(None, None, cfg)
    for idx, stub in enumerate(stubs, start=1):
        log.info("[%s/%s] Procesando %s", idx, len(stubs), stub.asin)
        try:
            historial, earliest = fetch_price_history(None, None, stub, cfg)
        except Exception as exc:
            log.error(
                "[%s/%s] SALTANDO producto %s por error irrecuperable: %s",
                idx, len(stubs), stub.asin, exc,
            )
            skipped.append(stub.asin)
            # Pausa larga tras un bloqueo para enfriar el rate-limit
            cooldown = random.uniform(30, 60)
            log.info("Cooldown de %.0fs antes del siguiente producto...", cooldown)
            time.sleep(cooldown)
            continue

        if earliest and earliest > cfg.history_start_date:
            print(
                f"ALERTA: El producto {stub.asin} ({stub.nombre[:50]}...) "
                f"solo tiene historial desde {earliest.isoformat()} "
                f"(deseado desde {cfg.history_start_date.isoformat()}). "
                f"Se exportan {len(historial)} registros {cfg.granularity} disponibles.",
                file=sys.stderr,
            )
        elif not historial:
            print(f"ALERTA: Sin historial de precios para {stub.asin}.", file=sys.stderr)

        precio_actual = stub.precio_actual
        if precio_actual is None and historial:
            precio_actual = historial[-1]["precio_registrado"]

        productos.append(
            {
                "id_producto": stub.asin,
                "nombre": stub.nombre,
                "categoria": stub.categoria,
                "precio_actual": round(float(precio_actual), 2)
                if precio_actual is not None
                else 0.0,
                "historial_precios": historial,
            }
        )

        # Guardado incremental cada 10 productos
        if len(productos) % 10 == 0:
            _incremental_save(productos, cfg.output)

        human_pause(cfg)

    if skipped:
        log.warning(
            "Productos saltados por errores (%s): %s", len(skipped), ", ".join(skipped)
        )

    return {"productos": productos}


def run_scraper(cfg: ScrapeConfig) -> dict[str, Any]:
    if cfg.tls_only:
        return run_scraper_tls_only(cfg)
    cfg.profile_dir.mkdir(parents=True, exist_ok=True)

    productos: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(cfg.profile_dir.resolve()),
            headless=not (cfg.headed or cfg.init_session),
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1366, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.pages[0] if context.pages else context.new_page()
        bootstrap_cloudflare_cookies(context)

        if cfg.init_session:
            log.info("Modo init-session: abra la ventana y complete Cloudflare si aparece.")
            page.goto(f"{BASE_URL}/popular", wait_until="domcontentloaded", timeout=cfg.timeout_ms)
            wait_for_real_page(page, cfg)
            log.info("Sesión inicializada. Vuelva a ejecutar sin --init-session.")
            if cfg.headed or cfg.init_session:
                context.close()
                return {"productos": []}

        stubs = discover_products(page, context, cfg)

        for idx, stub in enumerate(stubs, start=1):
            log.info("[%s/%s] Procesando %s", idx, len(stubs), stub.asin)
            historial, earliest = fetch_price_history(page, context, stub, cfg)

            if earliest and earliest > cfg.history_start_date:
                print(
                    f"ALERTA: El producto {stub.asin} ({stub.nombre[:50]}...) "
                    f"solo tiene historial desde {earliest.isoformat()} "
                    f"(deseado desde {cfg.history_start_date.isoformat()}). "
                    f"Se exportan {len(historial)} registros {cfg.granularity} disponibles.",
                    file=sys.stderr,
                )
            elif not historial:
                print(
                    f"ALERTA: Sin historial de precios para {stub.asin}.",
                    file=sys.stderr,
                )

            precio_actual = stub.precio_actual
            if precio_actual is None and historial:
                precio_actual = historial[-1]["precio_registrado"]

            productos.append(
                {
                    "id_producto": stub.asin,
                    "nombre": stub.nombre,
                    "categoria": stub.categoria,
                    "precio_actual": round(float(precio_actual), 2)
                    if precio_actual is not None
                    else 0.0,
                    "historial_precios": historial,
                }
            )
            human_pause(cfg)

        context.close()

    return {"productos": productos}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extrae productos populares e historial de precios desde camelcamelcamel.com"
    )
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("productos_camel.json"),
        help="Ruta del JSON de salida",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Número de productos únicos a extraer (default: 100)",
    )
    p.add_argument(
        "--profile-dir",
        type=Path,
        default=Path(".camelcamel_playwright_profile"),
        help="Perfil persistente de Chromium (cookies / Cloudflare)",
    )
    p.add_argument(
        "--init-session",
        action="store_true",
        help="Abre el navegador para validar Cloudflare y guardar la sesión",
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Navegador visible (útil si hay bloqueos)",
    )
    p.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Fecha de inicio del historial (YYYY-MM-DD, default: 2024-01-01)",
    )
    p.add_argument(
        "--no-chart-fallback",
        action="store_true",
        help="No usar el PNG de charts como respaldo de serie temporal",
    )
    p.add_argument(
        "--delay-min",
        type=float,
        default=2.0,
        help="Pausa mínima entre peticiones (segundos)",
    )
    p.add_argument(
        "--delay-max",
        type=float,
        default=5.0,
        help="Pausa máxima entre peticiones (segundos)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Logs detallados")
    p.add_argument(
        "--tls-only",
        action="store_true",
        help="No lanzar Chromium (solo curl_cffi). Útil en WSL sin libnspr4/libnss3",
    )
    p.add_argument(
        "--granularity",
        choices=("daily", "weekly"),
        default="daily",
        help="Granularidad del historial exportado (default: daily)",
    )
    p.add_argument(
        "--no-fill-daily-gaps",
        action="store_true",
        help="Solo días con cambio de precio (sin propagar el último precio a días intermedios)",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = ScrapeConfig(
        output=args.output,
        limit=args.limit,
        profile_dir=args.profile_dir,
        headed=args.headed,
        init_session=args.init_session,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        use_chart_fallback=not args.no_chart_fallback,
        tls_only=args.tls_only,
        granularity=args.granularity,
        fill_daily_gaps=not args.no_fill_daily_gaps,
        history_start_date=args.start_date if args.start_date is not None else date(2024, 1, 1),
    )

    if cfg.delay_max < cfg.delay_min:
        parser.error("--delay-max debe ser >= --delay-min")

    try:
        result = run_scraper(cfg)
    except Exception as exc:
        err = f"{type(exc).__name__} {exc}".lower()
        if any(
            needle in err
            for needle in ("libnspr", "shared libraries", "targetclosed", "exitcode=127")
        ):
            print(LINUX_BROWSER_DEPS_HINT, file=sys.stderr)
        raise

    if cfg.init_session and not result["productos"]:
        return 0

    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    with cfg.output.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    log.info("JSON guardado en %s (%s productos)", cfg.output.resolve(), len(result["productos"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
