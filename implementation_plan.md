# Plan de Implementación: Diagnóstico y Solución de 'FAILED TO FETCH' en NexusMarket

Este plan describe los hallazgos de la auditoría y la causa raíz del error "FAILED TO FETCH" en el login de NexusMarket, junto con los cambios propuestos para solucionar el problema de manera definitiva.

## Causa Raíz del Problema

El error **"FAILED TO FETCH"** ocurre porque el frontend intenta realizar una petición de red a un host o puerto donde el backend no está escuchando de forma compatible en Windows.

Específicamente:
1. **Configuración del Backend:** En `run.py`, el backend (Uvicorn) se inicia explícitamente en el host `127.0.0.1` (IPv4 loopback):
   ```python
   comando_backend = [
       str(python), "-m", "uvicorn", "Backend.app:app",
       "--reload", "--host", "127.0.0.1", "--port", "8000",
   ]
   ```
2. **Configuración del Frontend:** En `Frontend/js/api.js`, la URL base del backend por defecto es `http://localhost:8000`:
   ```javascript
   const BACKEND_URL = localStorage.getItem("urlApi") || "http://localhost:8000";
   ```
3. **Discrepancia en Windows (IPv6 vs IPv4):** En sistemas Windows modernos, el nombre de host `localhost` se resuelve prioritariamente a la dirección de loopback de IPv6 (`::1`). Al intentar conectar a `http://localhost:8000`, el navegador del usuario intenta conectarse a `[::1]:8000`. Dado que Uvicorn está escuchando únicamente en la interfaz IPv4 `127.0.0.1:8000`, la conexión es rechazada (`net::ERR_CONNECTION_REFUSED`).
4. **Manejo de Errores:** La API de Fetch de JavaScript lanza un error de tipo `TypeError: Failed to fetch`, que es capturado por el manejador de envío del formulario en `iniciar-sesion.html` y mostrado directamente en pantalla mediante la función `mostrarNotificacion()`.

---

## FASE 1 - AUDITORÍA DEL PROYECTO

### Inventario Tecnológico

- **Frontend:**
  - HTML5, CSS3, JavaScript (Vanilla).
  - Páginas estáticas: `index.html`, `iniciar-sesion.html`, `registrarse.html`.
  - Paneles: cliente (`cliente/marketplace.html`, `cliente/producto.html`, `cliente/historial.html`), vendedor (`vendedor/inventario.html`, `vendedor/reporte.html`).
  - JS Módulos: `js/api.js` (cliente API), `js/carrito.js` (carrito), `js/graficos.js` (Chart.js), `js/utilerias.js` (helpers y perfil).
- **Backend:**
  - FastAPI (Python 3.11+).
  - Servidor: Uvicorn con recarga automática.
  - ORM / Persistencia: `oracledb` para base de datos Oracle Autonomous Database en la nube (con Wallet).
  - Autenticación: `passlib` (`pbkdf2_sha256`) para hashing de contraseñas.
  - Lógica de Machine Learning: `scikit-learn` y `numpy` para recomendación de precios usando TF-IDF y similitud coseno.
- **Variables de Entorno (.env):**
  - `DB_USER`, `DB_PASSWORD`, `DB_DSN`
  - `WALLET_PATH`, `WALLET_PASSWORD`
  - `FRONTEND_URL` (para configuración de CORS)
- **Configuración de Red:**
  - Frontend: Puerto `5180` (servido con `http.server` de Python).
  - Backend: Puerto `8000` (servido con `uvicorn`).

---

## FASE 2 - TRAZAR EL FLUJO DE LOGIN

Ruta completa del flujo de autenticación:

1. **Botón:** El usuario hace clic en el botón "Iniciar sesión" (`#btnEnviar`) en `iniciar-sesion.html`.
2. **Handler (Evento submit):**
   - El evento `submit` del formulario `#formularioLogin` ejecuta una función asíncrona anónima.
   - Recupera el correo y la contraseña, y llama a `Api.iniciarSesion(correo, contrasena, portalSeleccionado)`.
3. **Servicio:** `Api.iniciarSesion` en `Frontend/js/api.js` construye la petición POST a `${BACKEND_URL}/api/auth/login`.
4. **Fetch / Axios:** Llama al método `eventoFetch` definido en `Frontend/js/utilerias.js`, que ejecuta la función global `fetch(url, opciones)` con cabeceras JSON.
5. **Endpoint Backend:** La petición llega al endpoint `POST /api/auth/login` definido en `Backend/app.py`.
6. **Backend:**
   - La función `iniciar_sesion_usuario` normaliza el correo y el rol.
   - Consulta a la base de datos Oracle (`usuarios`) los roles y detalles del usuario.
   - Verifica la contraseña utilizando `contexto_contrasenas.verify(solicitud.contrasena, password_hash)`.
7. **Respuesta:** Si las credenciales son válidas, retorna un objeto JSON con los datos del usuario. El frontend guarda el estado de la sesión en `localStorage` y redirige al panel según el rol (`Vendedor` o `Cliente`).

---

## FASE 3 - INVESTIGAR EL FAILED TO FETCH

- **CORS:** La API del backend en `app.py` tiene configurada la política de CORS mediante `CORSMiddleware`, permitiendo orígenes derivados de la variable `FRONTEND_URL`. Si `FRONTEND_URL` es `http://localhost:5180`, el backend permite dinámicamente `http://localhost:5180` y `http://127.0.0.1:5180`. El problema de CORS no es la causa raíz, sino la resolución del Host.
- **HTTP/HTTPS:** La aplicación corre enteramente sobre HTTP sin certificados SSL locales, por lo que no hay mezcla de protocolos que cause el bloqueo del navegador.
- **Host / IP:** La causa raíz reside enteramente en que el frontend apunta a `localhost:8000` (resuelto como `::1:8000` en Windows) mientras que el backend escucha estrictamente en `127.0.0.1:8000`.

---

## FASE 4 - REPRODUCIR EL ERROR

Ejecutamos la aplicación con `python run.py`.
Al abrir Chrome/Edge e ingresar a `http://localhost:5180/iniciar-sesion.html` e intentar iniciar sesión:
- **URL exacta llamada:** `POST http://localhost:8000/api/auth/login`
- **Método HTTP:** `POST` (con preflight `OPTIONS`)
- **Código de respuesta:** Ninguno (el navegador no logra establecer la conexión).
- **Consola:**
  `POST http://localhost:8000/api/auth/login net::ERR_CONNECTION_REFUSED`
  `Uncaught (in promise) TypeError: Failed to fetch`
- **UI:** Muestra la notificación roja con el mensaje `"Failed to fetch"`.

---

## FASE 5 - DIAGNÓSTICO

| Problema | Evidencia | Severidad | Impacto |
| :--- | :--- | :--- | :--- |
| Mapeo/Resolución de loopback de localhost en Windows (`::1` vs `127.0.0.1`) | La consola reporta `ERR_CONNECTION_REFUSED` en `localhost:8000` mientras que el log del servidor muestra que Uvicorn está escuchando estrictamente en `127.0.0.1`. | **Alta** | Bloquea totalmente el inicio de sesión del usuario en sistemas Windows con soporte de IPv6 activo. |

---

## FASE 6 - PROPUESTA DE REPARACIÓN

Se proponen cambios para alinear la dirección local a `127.0.0.1` en todo el flujo local (evitando la resolución ambigua de `localhost` a `::1`).

### Frontend

#### [MODIFY] [api.js](file:///c:/Users/arturobuttanda/Desktop/richie_daad/daad_project/Frontend/js/api.js)

Cambiar la URL por defecto a `127.0.0.1` para que las peticiones se realicen directamente por IPv4.

* **Línea:** 8
* **Antes:**
  ```javascript
  const BACKEND_URL = localStorage.getItem("urlApi") || "http://localhost:8000";
  ```
* **Después:**
  ```javascript
  const BACKEND_URL = localStorage.getItem("urlApi") || "http://127.0.0.1:8000";
  ```
* **Motivo:** Evitar que el navegador intente resolver `localhost` a `::1` (IPv6), dirigiendo las llamadas API directamente a la dirección IPv4 `127.0.0.1` en la que escucha el backend.

---

### Scripts

#### [MODIFY] [run.py](file:///c:/Users/arturobuttanda/Desktop/richie_daad/daad_project/run.py)

Alinear la salida del script y la apertura del navegador a `127.0.0.1` para consistencia.

* **Líneas:** 111 y 118
* **Antes:**
  ```python
  # Línea 111
  print("  Frontend: http://localhost:5180/iniciar-sesion.html")
  # Línea 118
  webbrowser.open("http://localhost:5180/iniciar-sesion.html")
  ```
* **After:**
  ```python
  # Línea 111
  print("  Frontend: http://127.0.0.1:5180/iniciar-sesion.html")
  # Línea 118
  webbrowser.open("http://127.0.0.1:5180/iniciar-sesion.html")
  ```
* **Motivo:** Consistencia de origen para el navegador, garantizando que el origen del frontend sea `http://127.0.0.1:5180`, lo que evita discrepancias de CORS y resolución de nombres.

---

## FASE 7 - VALIDACIÓN PLAN

1. Reiniciar los servidores ejecutando `python run.py`.
2. El script debe abrir el navegador automáticamente en `http://127.0.0.1:5180/iniciar-sesion.html`.
3. Probar inicio de sesión válido (ej: `cliente_demo_01@demo.local` / `Demo1234`). Confirmar redirección exitosa.
4. Probar inicio de sesión inválido (ej: contraseña incorrecta). Confirmar respuesta `401 Unauthorized` controlada con mensaje descriptivo de credenciales en pantalla.
5. Inspeccionar consola del navegador y pestaña Network en DevTools para verificar la ausencia de errores `ERR_CONNECTION_REFUSED` o "Failed to fetch".
