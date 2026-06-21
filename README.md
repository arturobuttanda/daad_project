# NexusMarket — Sistema de Marketplace Inteligente

Plataforma de comercio electrónico con análisis de precios, recomendación basada en similitud semántica y reportes financieros. Backend en Python/FastAPI + Oracle Autonomous Database, frontend HTML/JS vanilla.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (HTML estático — http.server :5180)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │Login/Reg │  │Marketplace│  │Producto  │  │Panel       │ │
│  │          │  │(Catálogo) │  │(Detalle+ │  │Vendedor    │ │
│  │          │  │           │  │Gráficas) │  │(Reportes)  │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
│                    ↕ fetch (JSON)                           │
│              js/api.js + js/utilerias.js                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP :8000
┌──────────────────────▼──────────────────────────────────────┐
│  Backend (FastAPI — uvicorn :8000)                          │
│  app.py                   → Rutas y lógica de endpoints      │
│  conexion_base.py         → Capa de persistencia Oracle      │
│  modelo_poo.py            → Clases del dominio (POO)         │
│  recomendacion_precio/    → Recomendador TF-IDF semántico    │
│  scripts/                 → DDL, seed, importación CSV       │
└──────────────────────┬──────────────────────────────────────┘
                       │ Oracle Wallet (mTLS)
┌──────────────────────▼──────────────────────────────────────┐
│  Oracle Autonomous Database                                  │
│  USUARIOS | PRODUCTOS | VENTAS | VENTA_DETALLE              │
│  VENDEDORES | CLIENTES | HISTORIAL_PRECIOS                  │
│  PRODUCTO_VENDEDOR                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Requisitos

- Python 3.10 o superior
- Oracle Autonomous Database (ADB) con wallet de conexión
- Navegador web moderno
- Conexión a internet (para carga inicial de modelos ML)

## Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio> nexusmarket
cd nexusmarket
```

### 2. Configurar variables de entorno

Copia el archivo de ejemplo y completa los valores de tu base de datos Oracle:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
DB_USER=ADMIN
DB_PASSWORD=tu_contraseña
DB_DSN=nombre_de_tu_db_high
WALLET_LOCATION=wallet/Wallet_TU_WALLET
WALLET_PASSWORD=tu_password_wallet
FRONTEND_URL=http://localhost:5180
```

### 3. Colocar el wallet de Oracle

Descarga y descomprime el wallet ZIP de tu ADB dentro de `wallet/`. La estructura debe ser:

```
wallet/
  Wallet_TU_WALLET/
    tnsnames.ora
    ewallet.p12
    keystore.jks
    ...
```

### 4. Inicializar la base de datos

Ejecuta el script SQL para crear las tablas:

```bash
# Opción A: Desde SQL*Net / SQL Developer, ejecuta:
Backend/scripts/schema.sql

# Opción B: Usando el script seed (crea tablas + datos demo):
python Backend/scripts/seed_demo_data.py
```

El script `seed_demo_data.py` crea las tablas, inserts datos de ejemplo (productos, vendedores, clientes, historial de precios) y es la opción recomendada para desarrollo/pruebas.

### 5. Iniciar la aplicación

Ejecuta el lanzador desde la raíz del proyecto:

```bash
python run.py
```

Esto:
1. Crea/activa un entorno virtual (`.venv`)
2. Instala dependencias de `requirements.txt`
3. Inicia el backend (uvicorn en `:8000`)
4. Espera a que el backend responda (vía `GET /api/ping`)
5. Inicia un servidor de archivos estáticos para el frontend en `:5180`
6. Abre el navegador en la página de inicio de sesión

### 6. Acceder

| Componente | URL |
|---|---|
| Frontend | http://127.0.0.1:5180/iniciar-sesion.html |
| Backend API | http://127.0.0.1:8000 |
| Documentación interactiva | http://127.0.0.1:8000/docs |

### Inicio manual (sin run.py)

```bash
# Backend
uvicorn Backend.app:app --reload --host 0.0.0.0 --port 8000

# Frontend (otra terminal)
python -m http.server 5180 --directory Frontend
```

---

## Estructura del proyecto

```
NexusMarket/
├── Backend/
│   ├── app.py                     # API REST (FastAPI)
│   ├── conexion_base.py           # Capa de datos (Oracle)
│   ├── modelo_poo.py              # Modelos del dominio (POO)
│   ├── ConexionDB/                # (residual)
│   ├── RecoleccionDatos/          # (residual)
│   ├── recomendacion_precio/
│   │   ├── __init__.py
│   │   └── recomendador_precio.py # TF-IDF + SentenceTransformer
│   └── scripts/
│       ├── schema.sql             # DDL completo
│       ├── seed_demo_data.py      # Poblado de datos demo
│       └── importar_csv_oracle.py # Importación desde CSV
├── Frontend/
│   ├── iniciar-sesion.html        # Login
│   ├── registrarse.html           # Registro
│   ├── index.html                 # Inicio
│   ├── cliente/
│   │   ├── marketplace.html       # Catálogo de productos
│   │   ├── producto.html          # Detalle + gráficas + historial
│   │   └── historial.html         # Historial de compras
│   ├── vendedor/
│   │   ├── inventario.html        # CRUD de productos
│   │   └── reporte.html           # Reportes financieros
│   ├── js/
│   │   ├── api.js                 # Cliente HTTP (fetch)
│   │   ├── carrito.js             # Carrito (localStorage)
│   │   └── utilerias.js           # Utilidades compartidas
│   └── css/
│       └── estilo.css             # Estilos globales
├── EDA/
│   ├── analisis.ipynb             # Notebook de análisis exploratorio
│   └── *.csv                       # Datos de respaldo
├── Recursos de prueba/             # Capturas y assets de respaldo
├── run.py                         # Lanzador unificado
├── requirements.txt               # Dependencias Python
├── .env.example                   # Template de configuración
└── README.md
```

---

## API Endpoints

### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/register` | Registrar usuario (cliente o vendedor) |
| POST | `/api/auth/login` | Iniciar sesión |
| PUT | `/api/auth/profile` | Actualizar nombre/contraseña |

### Productos (Cliente)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/cliente/productos` | Listar productos (paginado, búsqueda, filtro categoría) |
| GET | `/api/cliente/productos/{id}` | Detalle del producto + historial de precios |
| GET | `/api/productos/categorias` | Listar categorías disponibles |

### Compras (Cliente)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/cliente/compras` | Realizar compra (carrito multi-item) |
| GET | `/api/cliente/compras` | Historial de compras del cliente (paginado, por período) |
| GET | `/api/cliente/compras/{id}` | Ticket de una compra específica |

### Productos (Vendedor)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/vendedor/productos` | Listar productos del vendedor |
| POST | `/api/productos` | Crear producto |
| PUT | `/api/productos/{id}` | Actualizar producto |
| DELETE | `/api/productos/{id}` | Eliminar producto |
| POST | `/api/productos/recomendacion-precio` | Recomendar precio por similitud semántica |

### Reportes (Vendedor)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/vendedor/reportes/indicadores` | Indicadores financieros (ingresos, costos, margen) |
| GET | `/api/vendedor/reportes/ventas-mensuales` | Ventas agregadas por mes |
| GET | `/api/vendedor/reportes/productos-estancados` | Productos sin ventas recientes |
| GET | `/api/vendedor/reportes/top-productos` | Productos más vendidos |
| GET | `/api/vendedor/reportes/ventas/csv` | Exportar ventas a CSV |

### Salud

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/ping` | Health check (retorna estado del servidor y BD) |

---

## Esquema de base de datos

```
USUARIOS (id_usuario PK, nombre, telefono, correo, tipo_usuario, password_hash)
  ├── CLIENTES (id_cliente PK FK→USUARIOS, ...)
  ├── VENDEDORES (id_vendedor PK FK→USUARIOS, codigo_vendedor, ...)
  └── VENTAS (id_venta PK, id_cliente FK→USUARIOS, monto_total, total_unidades, fecha_venta)
        └── VENTA_DETALLE (id_venta FK, id_producto FK, id_vendedor FK→VENDEDORES,
                           cantidad, precio_unitario, subtotal, ...)

PRODUCTOS (id_producto PK, nombre, marca, categoria, precio_actual, stock, ...)
  └── PRODUCTO_VENDEDOR (id_producto FK, id_vendedor FK) — relación N:M
  └── HISTORIAL_PRECIOS (id_producto FK, precio, fecha)

HISTORIAL_PRECIOS_RAW — respaldo del historial original con outliers incluidos
```

### Detalles clave

- `VENTA_DETALLE.id_vendedor` (FK → `VENDEDORES` ON DELETE SET NULL): cada item de venta se asigna al vendedor que lo publicó, permitiendo reportes por vendedor incluso en compras multi-vendedor.
- `VENTAS` ya no tiene `id_vendedor` — el revenue por vendedor se calcula desde `VENTA_DETALLE`.
- `HISTORIAL_PRECIOS` contiene datos limpios (sin outliers). `HISTORIAL_PRECIOS_RAW` conserva los datos originales.
- El pool de conexión Oracle usa `timeout=30s`, `wait_timeout=5000ms`, `max_lifetime_session=600s`.

---

## Funcionamiento interno

### Flujo de compra

1. El cliente navega el marketplace (`GET /api/cliente/productos`).
2. Agrega productos al carrito (almacenado en `localStorage` via `carrito.js`).
3. Al pagar, el frontend envía `POST /api/cliente/compras` con `{id_cliente, items: [{id_producto, cantidad}]}`.
4. El backend valida el cliente, bloquea filas con `FOR UPDATE`, verifica stock, descuenta inventario e inserta en `VENTAS` + `VENTA_DETALLE` en una transacción.
5. Cada item se asigna al vendedor que lo publicó (desde `PRODUCTO_VENDEDOR`).

### Recomendación de precio

1. `RecomendadorPrecio` usa `SentenceTransformer` para generar embeddings del nombre/marca/categoría del producto.
2. Calcula similitud coseno contra el catálogo para encontrar productos similares.
3. Sugiere un precio basado en el promedio de productos semánticamente cercanos.

### Reportes financieros

- **Indicadores**: suma ingresos (`subtotal`), costos (`costo_unitario`) y calcula margen desde `VENTA_DETALLE`.
- **Ventas mensuales**: agrupa por mes usando `TRUNC(fecha_venta, 'MM')`.
- **Productos estancados**: productos del vendedor con `SUM(cantidad) = 0` en el período (con `HAVING COALESCE(SUM(d.cantidad), 0) > 0` para excluir los que nunca se vendieron).
- **Top productos**: ordena por cantidad vendida descendente.

### Gráficas del detalle de producto

- **Historial de precios**: dos modalidades:
  - *Histórico*: todos los registros (ordenados ASC).
  - *Mensual*: promedia los precios por mes calendario.
- Rango de fechas opcional via query params `fecha_inicio` y `fecha_fin`.

---

## Flujo de trabajo para exposición

### 1. Ciclo completo: Registro → Compra → Reporte

```
Registrar Vendedor ──→ Agregar Productos ──→ Ver Reportes
                                                    │
Registrar Cliente ───→ Marketplace ──→ Carrito ──→ Compra
                                                    │
                                              Historial (Ticket)
```

### 2. Demostración paso a paso

**A. Registrar un vendedor**
1. Ir a `/registrarse.html`, seleccionar "Vendedor", llenar datos.
2. Iniciar sesión como vendedor → redirige al panel de inventario.
3. Crear 2-3 productos con diferentes categorías y precios.

**B. Registrar un cliente**
1. Cerrar sesión, ir a `/registrarse.html`, seleccionar "Cliente".
2. Iniciar sesión como cliente → redirige al marketplace.

**C. Marketplace y compra**
1. Ver productos listados con stock > 0.
2. Usar búsqueda por nombre/marca y filtro por categoría.
3. Abrir detalle de producto → ver historial de precios (gráfica histórica y mensual).
4. Agregar productos al carrito, ajustar cantidades.
5. Pagar → muestra ticket con vendedor por item.

**D. Historial de compras**
1. Ir a "Pedidos" para ver el historial (paginado, filtro por período).
2. Abrir ticket de una compra → ver detalle con vendedor asignado.

**E. Reportes de vendedor**
1. Iniciar sesión como vendedor → ir a reportes.
2. Ver indicadores: ingresos totales, costos, margen, stock bajo.
3. Ver ventas mensuales (gráfica de barras).
4. Ver top productos y productos estancados.

### 3. Puntos clave para la exposición

- **Arquitectura**: Frontend HTML/JS vanilla ↔ FastAPI ↔ Oracle ADB con wallet mTLS.
- **Transaccionalidad**: `FOR UPDATE` + transacción Oracle para consistencia en compras.
- **ML**: Recomendación de precio vía `SentenceTransformer` + similitud coseno.
- **Reportes**: Cálculo de revenue por vendedor desde `VENTA_DETALLE` (soporta multi-vendedor por compra).
- **Gráficas**: Chart.js en frontend para historial de precios y ventas mensuales.
- **EDA previo**: Notebook `EDA/analisis.ipynb` para limpieza de datos y detección de outliers.

### 4. Comandos rápidos para demo

```bash
# 1. Iniciar todo
python run.py

# 2. Recargar datos demo (si es necesario)
python Backend/scripts/seed_demo_data.py

# 3. Ver logs del backend
tail -f server_out.log
tail -f server_err.log
```

### 5. Usuarios demo (si se ejecutó seed_demo_data.py)

Consulta `claves_usuarios.txt` después de ejecutar el seed para ver credenciales predefinidas. Los usuarios demo incluyen clientes y vendedores con productos y compras de ejemplo.
