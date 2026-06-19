# Auditoría Completa — NexusMarket

> Proyecto de marketplace e-commerce con FastAPI, Oracle Autonomous Database y motor de recomendación de precios con TF-IDF.

---

## 1. ¿Qué es NexusMarket?

Es una aplicación web **full-stack** de marketplace donde:

- **Vendedores** pueden registrar productos, consultar reportes financieros, exportar CSV, y recibir sugerencias de precio basadas en inteligencia artificial (TF-IDF + similitud coseno).
- **Clientes** pueden navegar el catálogo, buscar productos por nombre/marca/categoría, ver el historial de precios, obtener una señal de "comprar ahora o esperar", y realizar compras.
- **Administradores** (no hay panel dedicado aún) pueden ver indicadores globales a través de la API.

Está construido completamente en **Python (FastAPI)** para el backend, **HTML + CSS + JavaScript vanilla** para el frontend, y **Oracle Autonomous Database** en la nube como base de datos.

---

## 2. Arquitectura General (3 Capas)

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND                           │
│  HTML5 + CSS3 + JavaScript (Vanilla)                 │
│  ├── index.html (landing)                           │
│  ├── iniciar-sesion.html / registrarse.html         │
│  ├── vendedor/inventario.html / reporte.html        │
│  ├── cliente/marketplace.html / producto.html       │
│  │           / historial.html                       │
│  └── js/ (api.js, carrito.js, graficos.js, ...)     │
└──────────────┬──────────────────────────────────────┘
               │ HTTP (fetch) — JSON
               ▼
┌─────────────────────────────────────────────────────┐
│                   BACKEND                            │
│  FastAPI (Python) + Uvicorn                          │
│  ├── app.py            ← Rutas y lógica de API      │
│  ├── modelo_poo.py     ← Clases del dominio         │
│  ├── conexion_base.py  ← Persistencia Oracle        │
│  └── recomendación_precio/ ← ML engine (TF-IDF)     │
└──────────────┬──────────────────────────────────────┘
               │ Oracle DB (oracledb + Wallet)
               ▼
┌─────────────────────────────────────────────────────┐
│               BASE DE DATOS                          │
│  Oracle Autonomous Database (ATP) — Cloud            │
│  8 tablas: productos, usuarios, vendedores,          │
│  ventas, venta_detalle, historial_precios,           │
│  producto_vendedor, competencia_mercado              │
└─────────────────────────────────────────────────────┘
```

### Diagrama de Flujo de una Compra

```
Cliente → marketplace.html → GET /api/cliente/productos → Oracle
       → Click en producto → producto.html → GET /api/cliente/productos/{id}
         (devuelve: producto + historial precios + recomendación + vendedor)
       → Agrega al carrito → carrito.js (localStorage)
       → Finalizar compra → POST /api/cliente/compras
         (transacción atómica: crea venta, descuenta stock, calcula márgenes)
       → GET /api/cliente/compras → historial.html
```

---

## 3. Backend en Profundidad

### 3.1 `app.py` — API REST (~600 líneas, 25+ endpoints)

El servidor FastAPI se inicia con `uvicorn Backend.app:app`. Usa `CORSMiddleware` configurable desde la variable `FRONTEND_URL` del `.env`. Todos los endpoints devuelven JSON.

**Seguridad:**
- Contraseñas hasheadas con `passlib` (pbkdf2_sha256).
- Validación de contraseñas: mínimo 8 caracteres, 1 mayúscula, 1 número.
- Normalización de correos (minúsculas, sin espacios).
- Los roles se normalizan desde inglés/español ("vendedor"/"seller" → "Vendedor").
- Soporte multi-rol: un mismo correo puede estar registrado como cliente y vendedor; al hacer login sin especificar rol, se detecta automáticamente si hay ambigüedad.

**Funciones de normalización clave:**
- `normalizar_texto_busqueda()` — quita acentos para búsqueda SQL
- `normalizar_id_producto()` — mayúsculas + trim
- `_validar_no_negativo()` — protege precios, stock, costos

**Paginación consistente:** todos los endpoints de listado usan `_paginar_respuesta()` que devuelve `{items, page, page_size, total_items, total_pages}`.

### 3.2 `conexion_base.py` — Capa de Persistencia (940 líneas)

**Clase `BaseOracle`** — conexión a Oracle Autonomous Database mediante Wallet.

**Cómo se conecta:**
1. Lee credenciales del `.env`: `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `WALLET_PATH`
2. Busca automáticamente el wallet en `Backend/ConexionDB/Wallet/` si no está configurado
3. Analiza el archivo `tnsnames.ora` para extraer la cadena de conexión correcta
4. Usa `oracledb.connect()` con el wallet

**Operaciones principales:**
- `conectar()` — establece conexión (usado como context manager)
- `consultar_producto_por_id()` / `listar_productos()` / `listar_productos_vendedor()`
- `crear_producto()` / `actualizar_producto()` / `eliminar_producto()`
- `registrar_usuario()` / `actualizar_perfil_usuario()`
- `crear_compra()` — **la más compleja**: transacción atómica que:
  - Valida cliente, vendedor, productos
  - Bloquea filas con `FOR UPDATE` para evitar condiciones de carrera
  - Inserta cabecera de venta + detalle por cada ítem
  - Actualiza stock
  - Calcula márgenes unitarios
  - Si no se especifica vendedor, lo detecta automáticamente del producto
- `obtener_indicadores_financieros()` — KPIs globales o por vendedor
- `obtener_ventas_mensuales()` — agregación por año/mes con `EXTRACT` + `TO_CHAR`

### 3.3 `modelo_poo.py` — Modelo de Dominio (823 líneas)

Jerarquía de clases con herencia y composición:

```
Persona (ABC)
├── Cliente  → historial_compras: list[Venta]
└── Vendedor → codigo_vendedor, especialidad, objetivo_ventas
               + vender_producto() (descuenta stock)

Producto    → id_producto, nombre, marca, categoria, precio_actual, stock, ...
Venta       → id_venta, producto, cantidad, fecha_venta, total_pagado
Informe     → agregados para reportes financieros
```

**Métodos importantes:**
- `Persona.a_diccionario_publico()` — serialización segura (sin hash)
- `Producto.desde_dict()` / `desde_fila()` — factory methods desde API y SQL
- `Vendedor.vender_producto()` — valida stock, descuenta, genera ID de venta
- `crear_venta_por_item()` — función pública que orquesta la creación de una venta
- `calcular_recomendacion_precio()` — integración completa del recomendador + análisis de tendencia

**Lógica de `calcular_recomendacion_precio()`:**
1. Obtiene productos similares vía TF-IDF
2. Calcula media, mínimo y máximo del historial de precios
3. Determina señal de precio (oportunidad/arriba del promedio/etc.)
4. Sugiere precio basado en: referencia de mercado, margen mínimo (12%), días estancado, stock alto
5. Analiza tendencia con regresión lineal (`np.polyfit`)
6. Decide "comprar ahora o esperar" según percentiles vs mercado
7. Calcula puntuación vectorial con pesos: {margen: 0.50, brecha mercado: 0.25, días estancado: 0.15, stock: -0.10}

### 3.4 `recomendacion_precio/recomendador_precio.py` — Motor ML (315 líneas)

**Clase `RecomendadorPrecio`:**
- Singleton thread-safe con candado doble (`_candado`, `_candado_singleton`)
- Construye documentos de texto concatenando: `nombre x3 + marca x2 + categoría`
- Vectoriza con `TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))`
- `char_wb` analiza caracteres dentro de palabras, ideal para texto corto con errores ortográficos
- `ngram_range=(3,5)` captura subcadenas de 3 a 5 caracteres
- Similaridad coseno entre vector objetivo y matriz del catálogo
- Filtro adicional: solo productos de la **misma categoría**
- Precio recomendado = promedio ponderado por similitud
- Caché inteligente: recarga solo cuando cambia la firma del catálogo (conteo + última actualización)

**Parámetros clave:**
- `_SIMILITUD_MINIMA = 0.10` — umbral mínimo
- `_LIMITE_SIMILARES = 10` — máximo de similares
- `_MINIMO_ROBUSTO = 3` — mínimo para recomendación robusta

---

## 4. Base de Datos Oracle (8 tablas)

### Esquema Completo

```sql
-- 1. PRODUCTOS — Maestro de productos
--    PK: id_producto VARCHAR2(20)
--    CHECK: precio_actual >= 0, stock >= 0
--    Índice: categoria

-- 2. HISTORIAL_PRECIOS — Evolución de precios
--    PK compuesta: (id_producto, fecha)
--    FK → productos ON DELETE CASCADE

-- 3. USUARIOS — Autenticación y roles
--    PK: id_usuario UUID (VARCHAR2(36))
--    UNIQUE: correo
--    CHECK: tipo_usuario IN ('Vendedor', 'Cliente')

-- 4. VENDEDORES — Perfil extendido de vendedor
--    PK: id_vendedor → usuarios
--    UNIQUE: codigo_vendedor
--    Campos: especialidad, objetivo_ventas

-- 5. PRODUCTO_VENDEDOR — Asignación producto ↔ vendedor
--    PK: id_producto (1 producto = 1 vendedor)

-- 6. COMPETENCIA_MERCADO — Precios de competencia externa
--    PK: id_competencia (identity)
--    FK → productos

-- 7. VENTAS — Cabecera de compra
--    FK: id_cliente → usuarios, id_vendedor → vendedores
--    CHECK: monto_total >= 0

-- 8. VENTA_DETALLE — Líneas de la compra
--    PK compuesta: (id_venta, id_producto)
--    CHECK: cantidad > 0
--    Campos: precio_unitario, costo_unitario, margen_unitario
```

**Particularidades:**
- Usa `ON DELETE CASCADE` en la mayoría de FKs para limpieza en cascada
- `VENTAS.id_vendedor` usa `ON DELETE SET NULL` (la venta sobrevive si se elimina el vendedor)
- Transacciones atómicas con `FOR UPDATE` para bloqueo pesimista en compras
- Paginación con `OFFSET :offset ROWS FETCH NEXT :n ROWS ONLY` (SQL:2008)

---

## 5. Frontend en Profundidad

### 5.1 Estructura de Páginas

| Archivo | Ruta de acceso | Función |
|---------|---------------|---------|
| `index.html` | `/` | Landing page con login/registro |
| `iniciar-sesion.html` | `/iniciar-sesion.html` | Login con detección multi-rol |
| `registrarse.html` | `/registrarse.html` | Registro (cliente o vendedor) |
| `vendedor/inventario.html` | `/vendedor/inventario.html` | CRUD de productos + recomendación IA |
| `vendedor/reporte.html` | `/vendedor/reporte.html` | Dashboard: indicadores, gráficos, CSV |
| `cliente/marketplace.html` | `/cliente/marketplace.html` | Catálogo con búsqueda y categorías |
| `cliente/producto.html` | `/cliente/producto.html` | Detalle + historial + señal de compra |
| `cliente/historial.html` | `/cliente/historial.html` | Historial de compras con tickets |

### 5.2 Módulos JavaScript

**`api.js`** — Cliente HTTP centralizado:
- Función genérica `api(method, endpoint, body?)` con manejo de errores
- Endpoints específicos: `login()`, `register()`, `getProducts()`, `getCategories()`, `createProduct()`, `buy()`, etc.
- Todas las llamadas son asíncronas con `fetch()` + manejo de JSON

**`carrito.js`** — Carrito de compras:
- Persistencia en `localStorage`
- Funciones: `agregarAlCarrito()`, `eliminarDelCarrito()`, `vaciarCarrito()`, `obtenerCarrito()`
- Cálculo de totales en tiempo real
- Modal de confirmación antes de comprar

**`graficos.js`** — Visualización con Chart.js:
- `graficarVentasMensuales(data)` — gráfico de barras: ingresos vs costos vs ganancia
- `graficarTopProductos(data)` — gráfico de barras horizontal: productos más vendidos

**`notificaciones.js`** — Sistema de notificaciones toast:
- `mostrarNotificacion(mensaje, tipo)` — éxito/error/info con auto-dismiss
- Estilo flotante con animaciones CSS

**`utilerias.js`** — Funciones auxiliares:
- `formatearMoneda(valor)` — formato $X,XXX.XX
- `formatearFecha(isoString)` — formato legible
- `validarCorreo()`, `validarContrasena()`
- `obtenerUsuarioSesion()`, `guardarUsuarioSesion()`, `cerrarSesion()` — sessionStorage

### 5.3 CSS (`estilo.css` ~1000 líneas)

- Sistema de variables CSS para colores, fuentes, sombras (`--primary-color`, `--secondary-color`, etc.)
- Diseño responsivo con media queries
- Animaciones: `@keyframes fadeIn`, `fadeInUp`, `slideIn`, `pulse`
- Componentes: cards, tablas, formularios, modales, toasts, sidebar, navbar
- Grid y flexbox para layouts

---

## 6. Scripts de Base de Datos (Backend/scripts/)

| Script | Propósito |
|--------|-----------|
| `schema.sql` | DDL completo: crea las 8 tablas con constraints, índices, comentarios |
| `seed_demo_data.py` | Pobla 16 vendedores, 16 clientes, productos, y ventas demo |
| `poblar_ventas_demo.py` | Genera ventas aleatorias desde el CSV de demostración |
| `redistribuir_productos_vendedores.py` | Reasigna productos entre vendedores |
| `scrape_camelcamelcamel.py` | Scraping de precios históricos de Amazon (vía camelcamelcamel) |
| `importar_csv_oracle.py` | Importa catálogo desde CSV a Oracle |
| `insert_oracle.py` | Inserción masiva de productos desde JSON |
| `requirements-camelcamelcamel.txt` | Dependencias para el scraper (Playwright) |

---

## 7. Sistema de Recomendación de Precios — Explicación Técnica

### 7.1 TF-IDF (Term Frequency — Inverse Document Frequency)

Se usa para convertir texto de productos en vectores numéricos:

- **Term Frequency (TF):** qué tan frecuente es un término en el documento del producto
- **Inverse Document Frequency (IDF):** qué tan raro es ese término en todo el catálogo
- Producto: TF × IDF = peso del término

En este proyecto se usa `char_wb` (character n-grams dentro de palabras) porque:
- Los nombres de productos suelen ser cortos
- Captura subcadenas significativas ("tele", "visi", "sión")
- Es tolerante a variaciones ortográficas

### 7.2 Similitud Coseno

```
similarity(A, B) = cos(θ) = (A · B) / (||A|| × ||B||)
```

Rango: 0 (ortogonal, nada similar) a 1 (idéntico). Mide el ángulo entre vectores, no la magnitud.

### 7.3 Precio Ponderado

```
precio_recomendado = Σ(precio_i × similitud_i) / Σ(similitud_i)
```

Los productos más similares tienen más peso en el precio final.

### 7.4 Componentes de la Señal de Compra

La función `calcular_recomendacion_precio()` en `modelo_poo.py` integra:
1. **Referencia de mercado** del TF-IDF
2. **Historial de precios**: media, mínimo, días desde último cambio
3. **Margen**: (precio - costo) / costo
4. **Tendencia**: regresión lineal con `np.polyfit` para detectar alza/baja
5. **Stock**: si hay mucho inventario, sugiere bajar precio
6. **Días estancado**: si > 21 días sin cambios, sugiere reducción
7. **Puntuación vectorial**: combinación lineal ponderada de 4 factores

---

## 8. Flujo de Autenticación Detallado

```
Registro:
  Frontend → POST /api/auth/register {nombre, telefono, correo, tipo_usuario, contrasena}
  Backend:
    1. Normaliza correo (lowercase + trim)
    2. Normaliza rol (español/inglés → "Vendedor" o "Cliente")
    3. Valida correo (debe contener @)
    4. Valida contraseña (≥8 chars, 1 mayúscula, 1 número)
    5. Genera UUID como id_usuario
    6. Hashea contraseña con pbkdf2_sha256
    7. Inserta en usuarios + vendedores (si aplica, con especialidad aleatoria)
    8. Retorna {id, nombre, correo, tipo_usuario}

Login:
  Frontend → POST /api/auth/login {correo, contrasena, tipo_usuario?}
  Backend:
    1. Busca todos los roles asociados al correo
    2. Si hay múltiples roles y no se especificó tipo: HTTP 409 (debe elegir)
    3. Si hay 1 rol: lo usa automáticamente
    4. Verifica contraseña (passlib.verify + fallback a comparación directa)
    5. Retorna datos públicos del usuario
```

---

## 9. Lo que Debes Aprender (Guía de Estudio)

### Prioridad Alta (Imprescindible)

| Tema | Dónde practicarlo | Por qué es clave |
|------|------------------|------------------|
| **Python** — Type hints, módulos, ABCs | `modelo_poo.py`, `app.py` | Todo el backend está en Python moderno |
| **FastAPI** — Routers, Pydantic, CORS | `app.py` | Framework del API REST |
| **SQL** — Joins, subconsultas, transacciones | `conexion_base.py`, `schema.sql` | Toda la lógica de datos |
| **Oracle DB** — Wallet, conexión cloud | `conexion_base.py` | Base de datos del proyecto |
| **JavaScript fetch + DOM** | `js/api.js`, todas las páginas HTML | Sin frameworks, puro JS nativo |
| **HTML + CSS** — Responsive, variables, animaciones | `estilo.css`, los .html | Diseño completo del frontend |

### Prioridad Media (Importante)

| Tema | Dónde practicarlo | Por qué |
|------|------------------|---------|
| **POO** — Herencia, composición, factory pattern | `modelo_poo.py` | Modelo de dominio completo |
| **Chart.js** | `graficos.js`, `reporte.html` | Dashboard de ventas |
| **numpy** — polyfit, mean, dot | `modelo_poo.py` | Cálculos de tendencia y puntuación |
| **scikit-learn** — TF-IDF, cosine_similarity | `recomendador_precio.py` | Motor de recomendación |
| **Transacciones atómicas** | `conexion_base.py` (crear_compra) | Integridad de datos crítica |

### Prioridad Baja (Complementario)

| Tema | Dónde practicarlo |
|------|------------------|
| **localStorage** | `carrito.js` |
| **Exportación CSV** | `app.py` (`/api/vendedor/reportes/ventas/csv`) |
| **Session storage** | `utilerias.js` |
| **Threading + Singleton** | `recomendador_precio.py` |
| **Scraping con Playwright** | `scrape_camelcamelcamel.py` |
| **python-dotenv** | `conexion_base.py` |
| **passlib** (hashing) | `app.py` |

---

## 10. Cómo Empezar a Explorar (Ruta de Aprendizaje)

```
Paso 1:        run.py                           → Entender cómo arranca todo
Paso 2:        app.py (endpoints básicos)       → Health, Auth
Paso 3:        modelo_poo.py (clases base)      → Persona, Producto
Paso 4:        conexion_base.py (operaciones)    → CRUD productos
Paso 5:        app.py (endpoints producto)      → Listar, crear, actualizar
Paso 6:        api.js + inventario.html         → Frontend CRUD productos
Paso 7:        schema.sql                       → Estructura completa BD
Paso 8:        recomendador_precio.py           → Motor TF-IDF
Paso 9:        carrito.js + marketplace.html    → Flujo de compra
Paso 10:       graficos.js + reporte.html       → Dashboard y reportes
```

---

## 11. Comandos Útiles

```bash
# Iniciar el proyecto completo
python run.py

# Iniciar solo el backend (desarrollo)
uvicorn Backend.app:app --reload --host 127.0.0.1 --port 8000

# Iniciar solo el frontend
python -m http.server 5180 --directory Frontend

# Ver usuarios registrados
python scratch_users.py

# Documentación interactiva de la API
# http://127.0.0.1:8000/docs  (Swagger UI)
# http://127.0.0.1:8000/redoc (ReDoc)

# Ejecutar schema SQL en Oracle
# Usar SQL Developer Cloud o la consola web de Oracle Cloud
```

---

## 12. Archivos Clave por Extensión

| Archivo | Líneas | Rol |
|---------|--------|-----|
| `Backend/app.py` | ~600 | API REST endpoints |
| `Backend/conexion_base.py` | 940 | Persistencia Oracle |
| `Backend/modelo_poo.py` | 823 | Modelo de dominio POO |
| `Backend/recomendacion_precio/recomendador_precio.py` | 315 | Motor TF-IDF |
| `Backend/scripts/schema.sql` | 244 | DDL Oracle |
| `Frontend/css/estilo.css` | ~1000 | Diseño responsivo |
| `Frontend/js/api.js` | ~200 | Cliente HTTP |
| `documentacion.html` | 1125 | Documentación técnica |
| `run.py` | 141 | Lanzador del proyecto |

---

> **Nota:** Este proyecto está construido en Python 3.11+ con tipado moderno (`from __future__ import annotations`). Todas las funciones tienen docstrings y type hints. La documentación en `documentacion.html` cubre cada endpoint y clase en detalle bilingüe (español/inglés).
