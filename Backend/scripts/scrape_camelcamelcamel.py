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

# Colores de la línea Amazon en charts.camelcamelcamel.com
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
class ProductoBase:
    asin: str
    nombre: str
    categoria: str = "Sin categoría"
    precio_actual: float | None = None
    fuente: str = ""


@dataclass
class PuntoPrecio:
    fecha: date
    precio: float


@dataclass
class ConfigExtraccion:
    salida: Path
    limite: int = 100
    fecha_inicio_historial: date = date(2024, 1, 1)
    directorio_perfil: Path = field(default_factory=lambda: Path(".camelcamel_playwright_profile"))
    con_navegador_visible: bool = False
    iniciar_sesion: bool = False
    espera_min: float = 2.0
    espera_max: float = 5.0
    tiempo_espera_ms: int = 120_000
    usar_respaldo_grafico: bool = True
    solo_tls: bool = False
    granularidad: str = "daily"  # daily | weekly
    llenar_vacios_diarios: bool = True


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def pausa_humana(cfg: ConfigExtraccion) -> None:
    time.sleep(random.uniform(cfg.espera_min, cfg.espera_max))


def parsear_precio_us(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d,]+\.?\d*)", text.replace("$", "").replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parsear_fecha_mes(month: str, day: str, year: str) -> date:
    return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()


def es_challenge_cloudflare(html: str, titulo: str = "") -> bool:
    contenido = (titulo + html).lower()
    return "just a moment" in contenido or "cf-chl" in contenido or "checking your browser" in contenido


def _sesion_cffi():
    from curl_cffi import requests as cffi_requests

    return cffi_requests


def obtener_html_tls(url: str, max_reintentos: int = 3) -> str:
    """HTTP con curl_cffi (impersonate Chrome) con reintentos y backoff exponencial."""
    cffi = _sesion_cffi()
    esperas_reintento = [10, 30, 60]  # segundos de espera entre reintentos
    ultima_excepcion: Exception | None = None

    for intento in range(max_reintentos + 1):
        try:
            respuesta = cffi.get(url, impersonate="chrome", timeout=60)
            if respuesta.status_code == 403:
                raise RuntimeError(f"HTTP 403 Forbidden en {url}")
            respuesta.raise_for_status()
            if es_challenge_cloudflare(respuesta.text):
                raise RuntimeError(f"Cloudflare activo en {url}")
            return respuesta.text
        except Exception as exc:
            ultima_excepcion = exc
            if intento < max_reintentos:
                espera = esperas_reintento[min(intento, len(esperas_reintento) - 1)]
                log.warning(
                    "Intento %s/%s fallido para %s (%s). Reintentando en %ss...",
                    intento + 1, max_reintentos + 1, url, exc, espera,
                )
                time.sleep(espera)
            else:
                log.error("Todos los reintentos agotados para %s: %s", url, exc)

    raise ultima_excepcion  # type: ignore[misc]


def obtener_bytes_tls(url: str, max_reintentos: int = 3) -> bytes:
    """Descarga binaria con curl_cffi con reintentos y backoff exponencial."""
    cffi = _sesion_cffi()
    esperas_reintento = [10, 30, 60]
    ultima_excepcion: Exception | None = None

    for intento in range(max_reintentos + 1):
        try:
            respuesta = cffi.get(url, impersonate="chrome", timeout=60)
            if respuesta.status_code == 403:
                raise RuntimeError(f"HTTP 403 Forbidden en {url}")
            respuesta.raise_for_status()
            return respuesta.content
        except Exception as exc:
            ultima_excepcion = exc
            if intento < max_reintentos:
                espera = esperas_reintento[min(intento, len(esperas_reintento) - 1)]
                log.warning(
                    "Intento %s/%s fallido (bytes) para %s (%s). Reintentando en %ss...",
                    intento + 1, max_reintentos + 1, url, exc, espera,
                )
                time.sleep(espera)
            else:
                log.error("Todos los reintentos agotados (bytes) para %s: %s", url, exc)

    raise ultima_excepcion  # type: ignore[misc]


def obtener_html(
    contexto: BrowserContext | None,
    pagina: Page | None,
    url: str,
    cfg: ConfigExtraccion,
) -> str:
    # Obtiene HTML: APIRequest de Playwright y, si hace falta, curl_cffi (TLS)
    if cfg.solo_tls or contexto is None:
        log.debug("TLS: %s", url)
        return obtener_html_tls(url)

    try:
        respuesta = contexto.request.get(url, timeout=min(cfg.tiempo_espera_ms, 45_000))
        if respuesta.ok and not es_challenge_cloudflare(respuesta.text()):
            return respuesta.text()
    except Exception as exc:
        log.debug("Playwright request falló para %s: %s", url, exc)

    log.info("Respaldo TLS (curl_cffi): %s", url)
    return obtener_html_tls(url)


def obtener_bytes(url: str, contexto: BrowserContext | None, cfg: ConfigExtraccion) -> bytes:
    if cfg.solo_tls or contexto is None:
        return obtener_bytes_tls(url)

    try:
        respuesta = contexto.request.get(url, timeout=cfg.tiempo_espera_ms)
        if respuesta.ok:
            cuerpo = respuesta.body()
            if len(cuerpo) > 500:
                return cuerpo
    except Exception as exc:
        log.debug("Playwright bytes falló para %s: %s", url, exc)

    log.debug("Respaldo TLS para binario: %s", url)
    return obtener_bytes_tls(url)


def inicializar_cookies_cloudflare(contexto: BrowserContext) -> None:
    # Obtiene cookies válidas vía TLS fingerprint (curl_cffi) y las inyecta
    # en el contexto Playwright antes de la primera navegación
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        log.warning("curl_cffi no instalado; omitiendo bootstrap de cookies.")
        return

    try:
        respuesta = cffi_requests.get(BASE_URL + "/popular", impersonate="chrome", timeout=60)
        cookies = [
            {
                "name": name,
                "value": value,
                "domain": ".camelcamelcamel.com",
                "path": "/",
                "secure": True,
                "httpOnly": name.startswith("cf_") or name == "cf_clearance",
            }
            for name, value in respuesta.cookies.items()
        ]
        if cookies:
            contexto.add_cookies(cookies)
            log.info("Cookies de sesión inyectadas (%s).", len(cookies))
    except Exception as exc:
        log.warning("No se pudieron obtener cookies de bootstrap: %s", exc)


def esperar_pagina_real(pagina: Page, cfg: ConfigExtraccion) -> bool:
    limite_tiempo = time.time() + cfg.tiempo_espera_ms / 1000
    while time.time() < limite_tiempo:
        titulo = pagina.title()
        html = pagina.content()
        if not es_challenge_cloudflare(html, titulo):
            if "camelcamelcamel" in pagina.url and (
                "/popular" in pagina.url
                or "/top_drops" in pagina.url
                or "/product/" in pagina.url
                or "Popular Products" in html
                or "Top Amazon Price Drops" in html
            ):
                return True
        pagina.wait_for_timeout(2_000)
    return False


# ---------------------------------------------------------------------------
# Paso 1 — Descubrimiento de productos
# ---------------------------------------------------------------------------


def parsear_productos_listado(html: str, fuente: str) -> list[ProductoBase]:
    soup = BeautifulSoup(html, "lxml")
    encontrados: dict[str, ProductoBase] = {}

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
                precio = parsear_precio_us(pm.group(0))

        if asin not in encontrados or len(nombre) > len(encontrados[asin].nombre):
            encontrados[asin] = ProductoBase(
                asin=asin,
                nombre=nombre,
                precio_actual=precio,
                fuente=fuente,
            )

    return list(encontrados.values())


def descubrir_productos(
    pagina: Page | None, contexto: BrowserContext | None, cfg: ConfigExtraccion
) -> list[ProductoBase]:
    colectados: dict[str, ProductoBase] = {}
    num_pagina = 1

    while len(colectados) < cfg.limite and num_pagina <= 30:
        for path_tpl, fuente in LISTING_PATHS:
            if len(colectados) >= cfg.limite:
                break
            url = urljoin(BASE_URL, path_tpl.format(page=num_pagina))
            log.info("Listado %s (página %s)", fuente, num_pagina)
            html = obtener_html(contexto, pagina, url, cfg)
            pausa_humana(cfg)
            for producto_base in parsear_productos_listado(html, fuente):
                if producto_base.asin not in colectados:
                    colectados[producto_base.asin] = producto_base
                if len(colectados) >= cfg.limite:
                    break
        num_pagina += 1

    productos = list(colectados.values())[: cfg.limite]
    log.info("Productos únicos descubiertos: %s", len(productos))
    return productos


# ---------------------------------------------------------------------------
# Paso 2 — Historial de precios
# ---------------------------------------------------------------------------


def parsear_metadata_producto(html: str, asin: str) -> tuple[str, str, float | None, date | None, float | None, float | None]:
    # nombre, categoría, precio actual, fecha inicio tracking, min amazon, max amazon
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
            precio_actual = parsear_precio_us(cells[3])
        min_amazon = parsear_precio_us(cells[1])
        max_amazon = parsear_precio_us(cells[2])
        break

    inicio_seguimiento = None
    for p in soup.select("p, div"):
        text = p.get_text(" ", strip=True)
        m = MONITORING_SINCE_RE.search(text)
        if m:
            inicio_seguimiento = parsear_fecha_mes(m.group(1), m.group(2), m.group(3))
            break

    return nombre, categoria, precio_actual, inicio_seguimiento, min_amazon, max_amazon


def extraer_puntos_tabla_resumen(html: str) -> list[PuntoPrecio]:
    # Puntos discretos de la tabla resumen (lowest/highest/current)
    soup = BeautifulSoup(html, "lxml")
    puntos: list[PuntoPrecio] = []

    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or cells[0] != "Amazon":
            continue
        for cell in cells[1:]:
            price_m = re.search(r"\$\s*([\d,]+\.?\d*)", cell)
            if not price_m:
                continue
            precio = parsear_precio_us(price_m.group(0))
            dm = MONTH_DATE_RE.search(cell)
            if precio is not None and dm:
                d = parsear_fecha_mes(dm.group(1), dm.group(2), dm.group(3))
                puntos.append(PuntoPrecio(d, precio))
    return puntos


def extraer_puntos_tabla_bruta(html: str) -> list[PuntoPrecio]:
    # Tabla en bruto bajo la gráfica (si existe): columnas fecha + precio
    soup = BeautifulSoup(html, "lxml")
    puntos: list[PuntoPrecio] = []

    for table in soup.find_all("table"):
        filas = table.find_all("tr")
        if len(filas) < 5:
            continue
        encabezado = [c.get_text(" ", strip=True).lower() for c in filas[0].find_all(["th", "td"])]
        if not encabezado:
            continue
        indice_fecha = indice_precio = None
        for i, h in enumerate(encabezado):
            if any(k in h for k in ("date", "fecha", "time", "day")):
                indice_fecha = i
            if any(k in h for k in ("price", "precio", "amazon")):
                indice_precio = i
        if indice_fecha is None or indice_precio is None:
            continue

        for tr in filas[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) <= max(indice_fecha, indice_precio):
                continue
            dm = MONTH_DATE_RE.search(cells[indice_fecha]) or re.search(
                r"(\d{4}-\d{2}-\d{2})", cells[indice_fecha]
            )
            precio = parsear_precio_us(cells[indice_precio])
            if not precio:
                continue
            if dm:
                if dm.lastindex == 3:
                    d = parsear_fecha_mes(dm.group(1), dm.group(2), dm.group(3))
                else:
                    d = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
                puntos.append(PuntoPrecio(d, precio))

    return puntos


def intentar_parsear_payload_red(cuerpo: bytes, tipo_contenido: str) -> list[PuntoPrecio]:
    puntos: list[PuntoPrecio] = []
    text = cuerpo.decode("utf-8", errors="ignore").strip()
    if not text:
        return puntos

    carga_util: Any = None
    if "json" in tipo_contenido or text.startswith("{") or text.startswith("["):
        try:
            carga_util = json.loads(text)
        except json.JSONDecodeError:
            carga_util = None
    elif "csv" in tipo_contenido or text.count(",") > 3:
        return parsear_puntos_csv(text)

    if carga_util is None:
        # series Flot: [[ts_ms, precio], ...]
        flot = re.findall(r"\[\s*(\d{9,13})\s*,\s*([\d.]+)\s*\]", text)
        for ts, precio in flot:
            d = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).date()
            puntos.append(PuntoPrecio(d, float(precio)))
        return puntos

    def walk(nodo: Any) -> None:
        if isinstance(nodo, list):
            if len(nodo) >= 2 and isinstance(nodo[0], (int, float)) and isinstance(nodo[1], (int, float)):
                ts, valor = nodo[0], nodo[1]
                if ts > 1_000_000_000_000:
                    ts /= 1000
                if 10 < valor < 1_000_000:
                    puntos.append(
                        PuntoPrecio(
                            datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                            float(valor),
                        )
                    )
                return
            for item in nodo:
                walk(item)
        elif isinstance(nodo, dict):
            for v in nodo.values():
                walk(v)

    walk(carga_util)
    return puntos


def parsear_puntos_csv(text: str) -> list[PuntoPrecio]:
    puntos: list[PuntoPrecio] = []
    for linea in text.splitlines():
        if not linea.strip() or linea.lower().startswith("date"):
            continue
        partes = [p.strip() for p in re.split(r"[,;\t]", linea) if p.strip()]
        if len(partes) < 2:
            continue
        precio = parsear_precio_us(partes[-1])
        dm = MONTH_DATE_RE.search(linea) or re.search(r"(\d{4}-\d{2}-\d{2})", linea)
        if precio and dm:
            if dm.lastindex == 3:
                d = parsear_fecha_mes(dm.group(1), dm.group(2), dm.group(3))
            else:
                d = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
            puntos.append(PuntoPrecio(d, precio))
    return puntos


def construir_url_grafico_png(
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


def _mascara_linea_grafico(arr: np.ndarray) -> np.ndarray | None:
    # Máscara de píxeles de la línea de precio Amazon en el PNG del chart
    for rgb in CHART_AMAZON_COLORS:
        mask = (
            (np.abs(arr[:, :, 0].astype(int) - rgb[0]) <= CHART_COLOR_TOLERANCE)
            & (np.abs(arr[:, :, 1].astype(int) - rgb[1]) <= CHART_COLOR_TOLERANCE)
            & (np.abs(arr[:, :, 2].astype(int) - rgb[2]) <= CHART_COLOR_TOLERANCE)
        )
        if mask.sum() > 500:
            return mask
    return None


def _y_a_precio(y: float, y_min: float, y_max: float, min_precio: float, max_precio: float) -> float:
    rango_precio = max(max_precio - min_precio, 0.01)
    return max_precio - (y - y_min) / max(y_max - y_min, 1) * rango_precio


def sanear_serie_precios(
    puntos: list[PuntoPrecio],
    min_precio: float | None,
    max_precio: float | None,
    *,
    margin: float = 0.12,
) -> list[PuntoPrecio]:
    # Elimina valores fuera del rango Amazon declarado en la ficha del producto
    if not puntos or min_precio is None or max_precio is None:
        return puntos
    lo = min_precio * (1 - margin)
    hi = max_precio * (1 + margin)
    limpios = [p for p in puntos if lo <= p.precio <= hi]
    return limpios if len(limpios) >= 10 else puntos


def extraer_puntos_grafico_png(
    png_bytes: bytes,
    *,
    inicio: date,
    fin: date,
    min_precio: float,
    max_precio: float,
) -> list[PuntoPrecio]:
    # Traza la línea Amazon del PNG (charts.camelcamelcamel.com).
    # Por columna X elige el tramo coherente con el precio del día anterior (evita saltos
    # por leyenda/rejilla). Un punto por día calendario en el eje temporal del gráfico
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape

    mask = _mascara_linea_grafico(arr)
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
    total_days = max((fin - inicio).days, 1)

    por_fecha: dict[date, float] = {}
    prev_precio: float | None = None

    for x in sorted(columns):
        day_offset = (x - x_min) / max(x_max - x_min, 1) * total_days
        d = inicio + timedelta(days=int(day_offset))
        candidatos = [
            _y_a_precio(float(y), y_min, y_max, min_precio, max_precio) for y in columns[x]
        ]
        if prev_precio is None:
            precio = float(np.median(candidatos))
        else:
            precio = min(candidatos, key=lambda p: abs(p - prev_precio))
        prev_precio = precio
        por_fecha[d] = round(precio, 2)

    return [PuntoPrecio(d, p) for d, p in sorted(por_fecha.items())]


def unir_puntos(*series: list[PuntoPrecio]) -> list[PuntoPrecio]:
    combinados: dict[date, float] = {}
    for seq in series:
        for pt in seq:
            combinados[pt.fecha] = pt.precio
    return [PuntoPrecio(d, p) for d, p in sorted(combinados.items())]


def filtrar_ventana_historial(puntos: list[PuntoPrecio], fecha_inicio: date) -> list[PuntoPrecio]:
    if not puntos:
        return []
    filtrados = [p for p in puntos if p.fecha >= fecha_inicio]
    return filtrados if filtrados else sorted(puntos, key=lambda p: p.fecha)


def formatear_historial_diario(
    puntos: list[PuntoPrecio],
    fecha_inicio: date,
    *,
    llenar_vacios: bool = True,
) -> list[dict[str, Any]]:
    # Serie diaria. Camelcamelcamel registra cambios de precio (escalones);
    # con llenar_vacios=True propaga el último precio conocido a cada día calendario
    filtrados = filtrar_ventana_historial(puntos, fecha_inicio)
    if not filtrados:
        return []

    por_fecha: dict[date, float] = {}
    for pt in filtrados:
        por_fecha[pt.fecha] = pt.precio

    if not llenar_vacios:
        return [
            {"fecha": d.isoformat(), "precio_registrado": round(p, 2)}
            for d, p in sorted(por_fecha.items())
        ]

    inicio = min(por_fecha)
    fin = min(max(por_fecha), date.today())
    salida: list[dict[str, Any]] = []
    ultimo: float | None = None
    d = inicio
    while d <= fin:
        if d in por_fecha:
            ultimo = por_fecha[d]
        if ultimo is not None:
            salida.append({"fecha": d.isoformat(), "precio_registrado": round(ultimo, 2)})
        d += timedelta(days=1)
    return salida


def remuestrear_semanal(puntos: list[PuntoPrecio], fecha_inicio: date) -> list[dict[str, Any]]:
    filtrados = filtrar_ventana_historial(puntos, fecha_inicio)
    if not filtrados:
        return []

    grupos: dict[tuple[int, int], list[PuntoPrecio]] = defaultdict(list)
    for pt in filtrados:
        iso = pt.fecha.isocalendar()
        grupos[(iso.year, iso.week)].append(pt)

    semanal: list[dict[str, Any]] = []
    for key in sorted(grupos):
        bucket = grupos[key]
        elegido = max(bucket, key=lambda p: p.fecha)
        semanal.append(
            {
                "fecha": elegido.fecha.isoformat(),
                "precio_registrado": round(elegido.precio, 2),
            }
        )
    return semanal


def formatear_historial(puntos: list[PuntoPrecio], cfg: ConfigExtraccion) -> list[dict[str, Any]]:
    if cfg.granularidad == "weekly":
        return remuestrear_semanal(puntos, cfg.fecha_inicio_historial)
    return formatear_historial_diario(
        puntos,
        cfg.fecha_inicio_historial,
        llenar_vacios=cfg.llenar_vacios_diarios,
    )


def obtener_historial_precios(
    pagina: Page | None,
    contexto: BrowserContext | None,
    producto: ProductoBase,
    cfg: ConfigExtraccion,
) -> tuple[list[dict[str, Any]], date | None]:
    capturados: list[tuple[bytes, str]] = []
    capture_active = {"on": True}

    url_producto = (
        f"{BASE_URL}/product/{producto.asin}"
        "?active=price_amazon&context=price_history&tp=all"
    )
    log.info("Producto %s — historial", producto.asin)

    if pagina is not None and not cfg.solo_tls:

        def al_recibir_respuesta(response: Response) -> None:
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
                cuerpo = response.body()
                if len(cuerpo) < 30 or len(cuerpo) > 8_000_000:
                    return
                ct = (response.headers.get("content-type") or "").lower()
                if any(t in ct for t in ("json", "csv", "javascript", "text")) or url.endswith(
                    (".json", ".csv", ".js")
                ):
                    capturados.append((cuerpo, ct))
            except Exception:
                pass

        pagina.on("response", al_recibir_respuesta)
        try:
            pagina.goto(url_producto, wait_until="domcontentloaded", timeout=cfg.tiempo_espera_ms)
            pagina.wait_for_timeout(2_000)
        except Exception as exc:
            log.debug("goto producto %s: %s", producto.asin, exc)

    pausa_humana(cfg)
    html = obtener_html(contexto, pagina, url_producto, cfg)

    nombre, categoria, precio_tabla, inicio_seguimiento, min_p, max_p = parsear_metadata_producto(
        html, producto.asin
    )
    producto.nombre = nombre or producto.nombre
    producto.categoria = categoria
    if precio_tabla is not None:
        producto.precio_actual = precio_tabla

    puntos_red: list[PuntoPrecio] = []
    for cuerpo, ct in capturados:
        puntos_red.extend(intentar_parsear_payload_red(cuerpo, ct))

    puntos_tabla = extraer_puntos_tabla_bruta(html)
    puntos_resumen = extraer_puntos_tabla_resumen(html)
    todos_puntos = unir_puntos(puntos_red, puntos_tabla, puntos_resumen)

    # Serie densa desde PNG Amazon (única fuente con granularidad diaria en camelcamelcamel)
    if cfg.usar_respaldo_grafico:
        limite_min, limite_max = min_p, max_p
        if limite_min is None or limite_max is None:
            precios = [p.precio for p in todos_puntos]
            if precios:
                limite_min, limite_max = min(precios), max(precios)
            else:
                limite_min, limite_max = 1.0, 100.0
        inicio = inicio_seguimiento or (
            todos_puntos[0].fecha if todos_puntos else date.today() - timedelta(days=365 * 3)
        )
        fin = date.today()
        url_grafico = construir_url_grafico_png(producto.asin)
        try:
            png_bytes = obtener_bytes(url_grafico, contexto, cfg)
            puntos_grafico = extraer_puntos_grafico_png(
                png_bytes,
                inicio=inicio,
                fin=fin,
                min_precio=limite_min,
                max_precio=limite_max,
            )
            puntos_grafico = sanear_serie_precios(puntos_grafico, min_p, max_p)
            if puntos_grafico:
                log.info(
                    "%s: %s puntos desde chart Amazon (tracking desde %s).",
                    producto.asin,
                    len(puntos_grafico),
                    inicio.isoformat(),
                )
                if len(puntos_grafico) >= len(todos_puntos):
                    todos_puntos = puntos_grafico
                else:
                    todos_puntos = unir_puntos(todos_puntos, puntos_grafico)
        except Exception as exc:
            log.warning("%s: fallo al descargar chart PNG: %s", producto.asin, exc)

    todos_puntos = sanear_serie_precios(todos_puntos, min_p, max_p)
    capture_active["on"] = False

    mas_temprano = min((p.fecha for p in todos_puntos), default=None)
    historial = formatear_historial(todos_puntos, cfg)
    log.info(
        "%s: historial %s → %s registros.",
        producto.asin,
        cfg.granularidad,
        len(historial),
    )
    return historial, mas_temprano


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


def guardar_incremental(productos: list[dict[str, Any]], salida: Path) -> None:
    # Guardado incremental para no perder progreso si el scraper falla
    partial_path = salida.with_suffix(".partial.json")
    with partial_path.open("w", encoding="utf-8") as fh:
        json.dump({"productos": productos}, fh, ensure_ascii=False, indent=2)
    log.info("Guardado incremental: %s productos en %s", len(productos), partial_path)


def ejecutar_scraper_solo_tls(cfg: ConfigExtraccion) -> dict[str, Any]:
    # Modo sin Chromium: útil en WSL si falta libnspr4/libnss3
    if cfg.iniciar_sesion:
        raise RuntimeError("--init-session requiere navegador; omita --tls-only.")

    log.info("Modo --tls-only (sin Chromium / Playwright browser)")
    cfg.solo_tls = True
    productos: list[dict[str, Any]] = []
    saltados: list[str] = []

    productos_base = descubrir_productos(None, None, cfg)
    for indice, producto_base in enumerate(productos_base, start=1):
        log.info("[%s/%s] Procesando %s", indice, len(productos_base), producto_base.asin)
        try:
            historial, mas_temprano = obtener_historial_precios(None, None, producto_base, cfg)
        except Exception as exc:
            log.error(
                "[%s/%s] SALTANDO producto %s por error irrecuperable: %s",
                indice, len(productos_base), producto_base.asin, exc,
            )
            saltados.append(producto_base.asin)
            # Pausa larga tras un bloqueo para enfriar el rate-limit
            enfriamiento = random.uniform(30, 60)
            log.info("Cooldown de %.0fs antes del siguiente producto...", enfriamiento)
            time.sleep(enfriamiento)
            continue

        if mas_temprano and mas_temprano > cfg.fecha_inicio_historial:
            print(
                f"ALERTA: El producto {producto_base.asin} ({producto_base.nombre[:50]}...) "
                f"solo tiene historial desde {mas_temprano.isoformat()} "
                f"(deseado desde {cfg.fecha_inicio_historial.isoformat()}). "
                f"Se exportan {len(historial)} registros {cfg.granularidad} disponibles.",
                file=sys.stderr,
            )
        elif not historial:
            print(f"ALERTA: Sin historial de precios para {producto_base.asin}.", file=sys.stderr)

        precio_actual = producto_base.precio_actual
        if precio_actual is None and historial:
            precio_actual = historial[-1]["precio_registrado"]

        productos.append(
            {
                "id_producto": producto_base.asin,
                "nombre": producto_base.nombre,
                "categoria": producto_base.categoria,
                "precio_actual": round(float(precio_actual), 2)
                if precio_actual is not None
                else 0.0,
                "historial_precios": historial,
            }
        )

        # Guardado incremental cada 10 productos
        if len(productos) % 10 == 0:
            guardar_incremental(productos, cfg.salida)

        pausa_humana(cfg)

    if saltados:
        log.warning(
            "Productos saltados por errores (%s): %s", len(saltados), ", ".join(saltados)
        )

    return {"productos": productos}


def ejecutar_scraper(cfg: ConfigExtraccion) -> dict[str, Any]:
    if cfg.solo_tls:
        return ejecutar_scraper_solo_tls(cfg)
    cfg.directorio_perfil.mkdir(parents=True, exist_ok=True)

    productos: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        contexto = playwright.chromium.launch_persistent_context(
            user_data_dir=str(cfg.directorio_perfil.resolve()),
            headless=not (cfg.con_navegador_visible or cfg.iniciar_sesion),
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1366, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
        )
        contexto.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        inicializar_cookies_cloudflare(contexto)

        if cfg.iniciar_sesion:
            log.info("Modo init-session: abra la ventana y complete Cloudflare si aparece.")
            pagina.goto(f"{BASE_URL}/popular", wait_until="domcontentloaded", timeout=cfg.tiempo_espera_ms)
            esperar_pagina_real(pagina, cfg)
            log.info("Sesión inicializada. Vuelva a ejecutar sin --init-session.")
            if cfg.con_navegador_visible or cfg.iniciar_sesion:
                contexto.close()
                return {"productos": []}

        productos_base = descubrir_productos(pagina, contexto, cfg)

        for indice, producto_base in enumerate(productos_base, start=1):
            log.info("[%s/%s] Procesando %s", indice, len(productos_base), producto_base.asin)
            historial, mas_temprano = obtener_historial_precios(pagina, contexto, producto_base, cfg)

            if mas_temprano and mas_temprano > cfg.fecha_inicio_historial:
                print(
                    f"ALERTA: El producto {producto_base.asin} ({producto_base.nombre[:50]}...) "
                    f"solo tiene historial desde {mas_temprano.isoformat()} "
                    f"(deseado desde {cfg.fecha_inicio_historial.isoformat()}). "
                    f"Se exportan {len(historial)} registros {cfg.granularidad} disponibles.",
                    file=sys.stderr,
                )
            elif not historial:
                print(
                    f"ALERTA: Sin historial de precios para {producto_base.asin}.",
                    file=sys.stderr,
                )

            precio_actual = producto_base.precio_actual
            if precio_actual is None and historial:
                precio_actual = historial[-1]["precio_registrado"]

            productos.append(
                {
                    "id_producto": producto_base.asin,
                    "nombre": producto_base.nombre,
                    "categoria": producto_base.categoria,
                    "precio_actual": round(float(precio_actual), 2)
                    if precio_actual is not None
                    else 0.0,
                    "historial_precios": historial,
                }
            )
            pausa_humana(cfg)

        contexto.close()

    return {"productos": productos}


def construir_parser() -> argparse.ArgumentParser:
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
    parser = construir_parser()
    argumentos = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = ConfigExtraccion(
        salida=argumentos.output,
        limite=argumentos.limit,
        directorio_perfil=argumentos.profile_dir,
        con_navegador_visible=argumentos.headed,
        iniciar_sesion=argumentos.init_session,
        espera_min=argumentos.delay_min,
        espera_max=argumentos.delay_max,
        usar_respaldo_grafico=not argumentos.no_chart_fallback,
        solo_tls=argumentos.tls_only,
        granularidad=argumentos.granularity,
        llenar_vacios_diarios=not argumentos.no_fill_daily_gaps,
        fecha_inicio_historial=argumentos.start_date if argumentos.start_date is not None else date(2024, 1, 1),
    )

    if cfg.espera_max < cfg.espera_min:
        parser.error("--delay-max debe ser >= --delay-min")

    try:
        resultado = ejecutar_scraper(cfg)
    except Exception as exc:
        err = f"{type(exc).__name__} {exc}".lower()
        if any(
            needle in err
            for needle in ("libnspr", "shared libraries", "targetclosed", "exitcode=127")
        ):
            print(LINUX_BROWSER_DEPS_HINT, file=sys.stderr)
        raise

    if cfg.iniciar_sesion and not resultado["productos"]:
        return 0

    cfg.salida.parent.mkdir(parents=True, exist_ok=True)
    with cfg.salida.open("w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)

    log.info("JSON guardado en %s (%s productos)", cfg.salida.resolve(), len(resultado["productos"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
