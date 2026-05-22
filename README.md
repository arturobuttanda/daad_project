# DAAD — Data Acquisition & Delivery

Pipeline de extracción de productos y precios desde **camelcamelcamel.com** (scraper con bypass de Cloudflare vía Playwright + curl_cffi) y carga eficiente en **Oracle Autonomous Database** mediante upserts por lotes y forward-fill de series temporales.

## Arquitectura

```
camelcamelcamel.com          scripts/                    Oracle Autonomous DB
       │                   ┌──────────────┐                    │
       │  Playwright /     │  scrape_     │   productos_       │
       │  curl_cffi        │  camelcamel  │ ──► .json ────┐   │
       ├──────────────────►│  camel.py    │               │   │
       │                   │              │               │   │
       │                   │  insert_     │◄──────────────┘   │
       │                   │  oracle.py   │ ──────────────────►│
       │                   └──────────────┘   oracledb thin    │
                                                         productos
                                                         historial_precios
```

## Tabla de contenido

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso](#uso)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Seguridad](#seguridad)

## Requisitos

- **Python 3.10+**
- **Oracle Autonomous Database** (ATP/ADW) con Wallet de conexión
- **Playwright** (solo para el scraper; modo `--tls-only` no necesita navegador)
- `pip` y `venv`

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/daad.git
cd daad
```

### 2. Crear y activar entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate       # Linux / macOS / WSL
# .venv\Scripts\activate        # Windows (cmd)
# .venv\Scripts\Activate.ps1    # Windows (PowerShell)
```

### 3. Instalar dependencias del scraper

```bash
pip install -r scripts/requirements-camelcamelcamel.txt
```

### 4. Instalar navegador Playwright (opcional — necesario solo para `--init-session`)

```bash
python -m playwright install chromium
```

**En WSL/Linux**, si Chromium falla por librerías faltantes:

```bash
sudo playwright install-deps chromium
# o alternativamente ejecutar el scraper con --tls-only
```

### 5. Instalar dependencias para inserción en Oracle

```bash
pip install oracledb python-dotenv
```

### 6. Configurar la base de datos

Ejecutar `scripts/schema.sql` en tu instancia de Oracle Autonomous Database para crear las tablas `productos` e `historial_precios`.

## Configuración

### Variables de entorno

Copia el archivo de plantilla y completa tus credenciales:

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

| Variable           | Descripción                                           | Ejemplo                             |
|--------------------|-------------------------------------------------------|-------------------------------------|
| `DB_USER`          | Usuario de la base de datos Oracle                    | `ADMIN`                             |
| `DB_PASSWORD`      | Contraseña del usuario                                | `TuPasswordSegura123`               |
| `DB_DSN`           | TNS name (definido en `tnsnames.ora` dentro del wallet) | `r9mhb9kr53smcwqp_high`         |
| `WALLET_LOCATION`  | Ruta a la carpeta del Wallet descomprimido            | `wallet/Wallet_R9MHB9KR53SMCWQP`   |
| `WALLET_PASSWORD`  | Contraseña del Wallet (opcional, por defecto `DB_PASSWORD`) |                              |

### Wallet de Oracle

Coloca los archivos del Wallet (descomprimido del `.zip` descargado desde OCI) en la carpeta `wallet/`. La estructura debe ser similar a:

```
wallet/
├── Wallet_R9MHB9KR53SMCWQP/
│   ├── tnsnames.ora
│   ├── ewallet.p12
│   ├── keystore.jks
│   ├── ojdbc.properties
│   └── ...
```

**Esta carpeta está excluida de Git** (`.gitignore`).

## Uso

### Extraer datos de camelcamelcamel

```bash
# Primera ejecución: validar Cloudflare manualmente (solo una vez)
python scripts/scrape_camelcamelcamel.py --init-session

# Extraer 100 productos populares
python scripts/scrape_camelcamelcamel.py --output productos_camel.json

# Prueba rápida (3 productos, sin navegador)
python scripts/scrape_camelcamelcamel.py --tls-only --limit 3 --output prueba.json
```

### Cargar datos en Oracle

```bash
# Probar conexión
python scripts/insert_oracle.py --test

# Cargar datos desde el JSON generado por el scraper
python scripts/insert_oracle.py --json productos_camel.json
```

## Estructura del proyecto

```
daad/
├── .env.example           # Plantilla de variables de entorno
├── .gitignore             # Exclusiones de Git
├── README.md              # Este archivo
├── wallet/                # Wallet de Oracle (excluido de Git)
├── scripts/
│   ├── scrape_camelcamelcamel.py   # Scraper con Playwright + curl_cffi
│   ├── insert_oracle.py            # Pipeline ETL hacia Oracle
│   ├── schema.sql                  # DDL de tablas Oracle
│   └── requirements-camelcamelcamel.txt  # Dependencias del scraper
└── .venv/                 # Entorno virtual (excluido de Git)
```

## Seguridad

### Credenciales

El script `insert_oracle.py` lee todas las credenciales desde variables de entorno usando `os.environ.get()`. **Nunca edites los valores por defecto con credenciales reales**. Usa siempre el archivo `.env`:

```python
# ✅ Correcto (lee desde variable de entorno)
DB_USER = os.environ.get("DB_USER")
# Requiere que la variable esté definida

# ❌ Incorrecto (hardcodea credenciales)
DB_USER = "ADMIN"
DB_PASSWORD = "Password123*"   # ¡Esto filtra la contraseña en Git!
```

Para eliminar los valores hardcodeados del script, cambia las líneas ~31-34 de `insert_oracle.py` para que no tengan valores por defecto sensibles:

```python
DB_USER = os.environ["DB_USER"]            # Error si no está definida
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_LOCATION = os.environ["WALLET_LOCATION"]
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")  # Opcional
```

Si ya estás usando `python-dotenv`, añade al inicio del script:

```python
from dotenv import load_dotenv
load_dotenv()  # Carga variables desde .env
```

### Archivos excluidos

| Archivo/Carpeta       | Motivo                                    |
|-----------------------|-------------------------------------------|
| `.env`                | Contiene credenciales de base de datos    |
| `wallet/`             | Certificados, llaves privadas, contraseñas |
| `.venv/`              | Entorno virtual (pesado, no portable)     |
| `*.json` de datos     | Datos extraídos localmente                |

---

**Autor:** Arturo Buttanda
