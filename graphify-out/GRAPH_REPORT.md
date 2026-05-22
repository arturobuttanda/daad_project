# Graph Report - daad  (2026-05-21)

## Corpus Check
- 6 files · ~6,246 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 105 nodes · 163 edges · 10 communities (8 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]

## God Nodes (most connected - your core abstractions)
1. `fetch_price_history()` - 15 edges
2. `DAAD — Data Acquisition & Delivery` - 9 edges
3. `run_scraper()` - 8 edges
4. `PricePoint` - 7 edges
5. `run_scraper_tls_only()` - 7 edges
6. `Instalación` - 7 edges
7. `parse_us_price()` - 6 edges
8. `fetch_html()` - 6 edges
9. `discover_products()` - 6 edges
10. `extract_points_from_summary_table()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `extract_points_from_chart_png()` --calls--> `PricePoint`  [EXTRACTED]
  scripts/scrape_camelcamelcamel.py → scripts/scrape_camelcamelcamel.py  _Bridges community 2 → community 6_
- `fetch_price_history()` --calls--> `human_pause()`  [EXTRACTED]
  scripts/scrape_camelcamelcamel.py → scripts/scrape_camelcamelcamel.py  _Bridges community 0 → community 2_
- `fetch_price_history()` --calls--> `format_history()`  [EXTRACTED]
  scripts/scrape_camelcamelcamel.py → scripts/scrape_camelcamelcamel.py  _Bridges community 7 → community 2_

## Communities (10 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.15
Nodes (24): bootstrap_cloudflare_cookies(), build_parser(), _cffi_session(), discover_products(), fetch_bytes(), fetch_bytes_tls(), fetch_html(), fetch_html_tls() (+16 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (17): Arquitectura, Cargar datos en Oracle, code:block1 (camelcamelcamel.com          scripts/                    Ora), code:bash (# Primera ejecución: validar Cloudflare manualmente (solo un), code:bash (# Probar conexión), code:block12 (daad/), code:bash (cp .env.example .env), code:block9 (wallet/) (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.21
Nodes (16): build_chart_png_url(), extract_points_from_raw_table(), extract_points_from_summary_table(), fetch_price_history(), merge_points(), parse_csv_points(), parse_month_date(), parse_product_metadata() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.15
Nodes (13): 1. Clonar el repositorio, 2. Crear y activar entorno virtual, 3. Instalar dependencias del scraper, 4. Instalar navegador Playwright (opcional — necesario solo para `--init-session`), 5. Instalar dependencias para inserción en Oracle, 6. Configurar la base de datos, code:bash (git clone https://github.com/tu-usuario/daad.git), code:bash (python -m venv .venv) (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.22
Nodes (12): execute_batch(), forward_fill_daily(), get_connection_string_from_tnsnames(), load_and_clean_data(), Valida la conectividad a la base de datos., Dado un dict {date: precio} con observaciones esporádicas,     genera un registr, Lee el JSON, limpia los datos, y genera registros DIARIOS de precios     mediant, Ejecuta inserciones por lotes de forma eficiente. (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (6): Archivos excluidos, code:python (# ✅ Correcto (lee desde variable de entorno)), code:python (DB_USER = os.environ["DB_USER"]            # Error si no est), code:python (from dotenv import load_dotenv), Credenciales, Seguridad

### Community 6 - "Community 6"
Cohesion: 0.40
Nodes (5): _chart_line_mask(), extract_points_from_chart_png(), Máscara de píxeles de la línea de precio Amazon en el PNG del chart., Traza la línea Amazon del PNG (charts.camelcamelcamel.com).     Por columna X e, _y_to_price()

### Community 7 - "Community 7"
Cohesion: 0.50
Nodes (5): filter_history_window(), format_daily_history(), format_history(), Serie diaria. Camelcamelcamel registra cambios de precio (escalones);     con f, resample_weekly()

## Knowledge Gaps
- **21 isolated node(s):** `code:block1 (camelcamelcamel.com          scripts/                    Ora)`, `Tabla de contenido`, `Requisitos`, `code:bash (git clone https://github.com/tu-usuario/daad.git)`, `code:bash (python -m venv .venv)` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DAAD — Data Acquisition & Delivery` connect `Community 1` to `Community 3`, `Community 5`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `Instalación` connect `Community 3` to `Community 1`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Seguridad` connect `Community 5` to `Community 1`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **What connects `Parsea tnsnames.ora para extraer la descripción de conexión (connection string)`, `Valida la conectividad a la base de datos.`, `Dado un dict {date: precio} con observaciones esporádicas,     genera un registr` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._