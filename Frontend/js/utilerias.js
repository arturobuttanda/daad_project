/**
 * Utilidades compartidas para todo el frontend.
 * Formateo de dinero, truncado de texto, fechas, etc.
 */



function formatearDinero(valor) {
  if (valor === null || valor === undefined) return "---";
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
  }).format(valor);
}

function truncarTexto(texto, maximo = 30) {
  if (!texto) return "";
  if (texto.length <= maximo) return texto;
  return texto.substring(0, maximo) + "...";
}

function formatearFecha(isoString) {
  if (!isoString) return "---";
  try {
    const fecha = new Date(isoString);
    return fecha.toLocaleDateString("es-MX", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function formatearFechaHora(isoString) {
  if (!isoString) return "---";
  try {
    const fecha = new Date(isoString);
    return fecha.toLocaleDateString("es-MX", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function mostrarNotificacion(mensaje, tipo = "exito") {
  const existente = document.querySelector(".notificacion");
  if (existente) existente.remove();

  const div = document.createElement("div");
  div.className = `notificacion ${tipo}`;
  div.textContent = mensaje;
  document.body.appendChild(div);

  setTimeout(() => {
    div.style.opacity = "0";
    div.style.transition = "opacity 0.3s";
    setTimeout(() => div.remove(), 300);
  }, 3500);
}

function obtenerUsuario() {
  return {
    id: localStorage.getItem("userId"),
    nombre: localStorage.getItem("userName"),
    tipo: localStorage.getItem("userType"),
    registrado: localStorage.getItem("isRegistered") === "true",
  };
}

function cerrarSesion() {
  localStorage.removeItem("isRegistered");
  localStorage.removeItem("userType");
  localStorage.removeItem("userName");
  localStorage.removeItem("userId");
  
  const path = window.location.pathname;
  if (path.includes("/cliente/") || path.includes("/vendedor/")) {
    window.location.href = "../iniciar-sesion.html";
  } else {
    window.location.href = "iniciar-sesion.html";
  }
}

const TIEMPO_ESPERA_API = 30000;

function eventoFetch(url, opciones = {}) {
  const controlador = new AbortController();
  const temporizador = setTimeout(() => controlador.abort(), TIEMPO_ESPERA_API);

  const opcionesFinales = {
    headers: { "Content-Type": "application/json", ...opciones.headers },
    ...opciones,
    signal: controlador.signal,
  };

  return fetch(url, opcionesFinales)
    .then((res) => {
      clearTimeout(temporizador);
      if (!res.ok) {
        if (res.status === 0) {
          throw new Error("Error de conexion con el servidor.");
        }
        return res.json().then((err) => {
          const errMsg = err.detail || "Error en la peticion";
          if (res.status >= 500) {
            throw new Error("Error en el servidor. Intenta de nuevo.");
          }
          throw new Error(errMsg);
        });
      }
      return res.json();
    })
    .catch((err) => {
      clearTimeout(temporizador);
      if (err.name === "AbortError") {
        throw new Error(
          "El servidor tardo demasiado en responder. Verifica que el backend este corriendo."
        );
      }
      if (err.message === "Failed to fetch" || err.message === "NetworkError when attempting to fetch resource." || err.message === "Load failed") {
        throw new Error("No se pudo conectar con el servidor.");
      }
      throw err;
    });
}

// --- AUTO INJECT PROFILE BUTTON & MODAL ---
document.addEventListener("DOMContentLoaded", () => {
  const user = obtenerUsuario();
  if (!user.registrado) return;

  const path = window.location.pathname;
  if (!path.includes("/cliente/") && !path.includes("/vendedor/")) return;

  // 1. Inject Styles
  const style = document.createElement("style");
  style.textContent = `
    .btn-perfil-header {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.5rem 0.75rem;
      border: 1px solid var(--borde, #d6d3d1);
      background: var(--tarjeta-bg, #ffffff);
      color: var(--texto, #1c1917);
      border-radius: 0.5rem;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .btn-perfil-header:hover {
      background: var(--borde-suave, #f5f5f4);
      border-color: var(--texto-suave, #78716c);
    }
    .btn-perfil-header svg {
      width: 16px;
      height: 16px;
      stroke: currentColor;
    }
    .perfil-modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 3000;
      backdrop-filter: blur(2px);
    }
    .perfil-modal {
      background: var(--tarjeta-bg, #ffffff);
      border: 1px solid var(--borde, #d6d3d1);
      border-radius: 1rem;
      width: 100%;
      max-width: 400px;
      padding: 1.5rem;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
      animation: perfilModalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes perfilModalIn {
      from { transform: scale(0.95); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .perfil-modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--borde-suave, #f5f5f4);
      padding-bottom: 0.75rem;
    }
    .perfil-modal-header h3 {
      font-size: 1.125rem;
      font-weight: 700;
      margin: 0;
      color: var(--texto, #1c1917);
    }
    .perfil-seccion {
      border: 1px solid var(--borde-suave, #f5f5f4);
      border-radius: 0.75rem;
      padding: 1rem;
      margin-bottom: 1rem;
      background: var(--borde-suave, #fafaf9);
    }
    .perfil-seccion h4 {
      font-size: 0.875rem;
      font-weight: 600;
      margin: 0 0 0.5rem 0;
      color: var(--texto, #1c1917);
    }
  `;
  document.head.appendChild(style);

  // 2. Find header to inject the profile button
  const mainEl = document.querySelector("main.contenido-principal");
  if (!mainEl) return;
  const headerDiv = mainEl.querySelector("div");
  if (!headerDiv) return;

  const lastHeaderChild = headerDiv.lastElementChild;

  const btnPerfil = document.createElement("button");
  btnPerfil.className = "btn-perfil-header";
  btnPerfil.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
      <circle cx="12" cy="7" r="4"></circle>
    </svg>
    <span>Mi Perfil</span>
  `;

  // Inject the button
  if (headerDiv.children.length === 1) {
    const wrapper = document.createElement("div");
    wrapper.style.display = "flex";
    wrapper.style.gap = "0.5rem";
    wrapper.style.alignItems = "center";
    wrapper.appendChild(btnPerfil);
    headerDiv.appendChild(wrapper);
  } else {
    if (lastHeaderChild && (lastHeaderChild.tagName === "BUTTON" || lastHeaderChild.style.display === "flex" || lastHeaderChild.classList.contains("btn") || lastHeaderChild.tagName === "DIV")) {
      if (lastHeaderChild.tagName === "BUTTON") {
        const wrapper = document.createElement("div");
        wrapper.style.display = "flex";
        wrapper.style.gap = "0.5rem";
        wrapper.style.alignItems = "center";
        headerDiv.replaceChild(wrapper, lastHeaderChild);
        wrapper.appendChild(btnPerfil);
        wrapper.appendChild(lastHeaderChild);
      } else {
        lastHeaderChild.style.display = "flex";
        lastHeaderChild.style.gap = "0.5rem";
        lastHeaderChild.style.alignItems = "center";
        lastHeaderChild.insertBefore(btnPerfil, lastHeaderChild.firstChild);
      }
    } else {
      headerDiv.appendChild(btnPerfil);
    }
  }

  // 3. Define Perfil Modal Open Action
  btnPerfil.onclick = () => {
    if (document.getElementById("perfilModalOverlay")) return;

    const overlay = document.createElement("div");
    overlay.id = "perfilModalOverlay";
    overlay.className = "perfil-modal-overlay";
    overlay.innerHTML = `
      <div class="perfil-modal">
        <div class="perfil-modal-header">
          <h3>Mi Perfil (${user.tipo})</h3>
          <button class="btn btn-sm" id="btnCerrarPerfil" style="background:none; border:1px solid var(--borde, #d6d3d1); width:28px; height:28px; padding:0; display:flex; align-items:center; justify-content:center; border-radius:4px; cursor:pointer;">✕</button>
        </div>
        <div class="perfil-modal-body">
          <div style="margin-bottom:1.25rem; font-size:0.875rem; color:var(--texto-suave);">
            Usuario actual: <strong id="lblUserName" style="color:var(--texto); font-size:0.95rem;">${user.nombre}</strong>
          </div>
          
          <!-- SECCION CAMBIAR NOMBRE -->
          <div class="perfil-seccion">
            <h4>Cambiar nombre</h4>
            <div style="display:flex; gap:0.5rem;">
              <input type="text" id="txtNuevoNombre" class="campo" placeholder="Nuevo nombre" style="margin:0; font-size:0.875rem; padding:0.375rem 0.75rem; flex:1;" />
              <button class="btn btn-primario btn-sm" id="btnGuardarNombre" style="padding:0.375rem 0.75rem;">Guardar</button>
            </div>
          </div>
          
          <!-- SECCION CAMBIAR CONTRASEÑA -->
          <div class="perfil-seccion">
            <h4>Cambiar contraseña</h4>
            <div style="display:flex; flex-direction:column; gap:0.5rem;">
              <input type="password" id="txtNuevaContrasena" class="campo" placeholder="Nueva contraseña" style="margin:0; font-size:0.875rem; padding:0.375rem 0.75rem;" />
              <button class="btn btn-primario btn-sm" id="btnGuardarContrasena" style="align-self:flex-end; padding:0.375rem 0.75rem;">Actualizar contraseña</button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    const closeBtn = overlay.querySelector("#btnCerrarPerfil");
    closeBtn.onclick = () => overlay.remove();
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    // Change Name Action
    const btnGuardarNombre = overlay.querySelector("#btnGuardarNombre");
    btnGuardarNombre.onclick = async () => {
      const nuevoNombre = overlay.querySelector("#txtNuevoNombre").value.trim();
      if (!nuevoNombre) {
        mostrarNotificacion("El nombre no puede estar vacío.", "error");
        return;
      }
      try {
        btnGuardarNombre.disabled = true;
        btnGuardarNombre.textContent = "Guardan...";
        await window.Api.actualizarPerfil(user.id, nuevoNombre, null);
        localStorage.setItem("userName", nuevoNombre);
        overlay.querySelector("#lblUserName").textContent = nuevoNombre;
        
        // Update welcome message if present
        const tituloBienvenida = document.getElementById("tituloBienvenida");
        if (tituloBienvenida) {
          tituloBienvenida.textContent = "Panel de " + nuevoNombre;
        }
        
        mostrarNotificacion("Nombre actualizado correctamente.", "exito");
        overlay.querySelector("#txtNuevoNombre").value = "";
      } catch (err) {
        mostrarNotificacion("Error al actualizar nombre: " + err.message, "error");
      } finally {
        btnGuardarNombre.disabled = false;
        btnGuardarNombre.textContent = "Guardar";
      }
    };

    // Change Password Action
    const btnGuardarContrasena = overlay.querySelector("#btnGuardarContrasena");
    btnGuardarContrasena.onclick = async () => {
      const nuevaContrasena = overlay.querySelector("#txtNuevaContrasena").value.trim();
      if (!nuevaContrasena) {
        mostrarNotificacion("La contraseña no puede estar vacía.", "error");
        return;
      }
      if (nuevaContrasena.length < 4) {
        mostrarNotificacion("La contraseña debe tener al menos 4 caracteres.", "error");
        return;
      }
      try {
        btnGuardarContrasena.disabled = true;
        btnGuardarContrasena.textContent = "Actualizando...";
        await window.Api.actualizarPerfil(user.id, null, nuevaContrasena);
        mostrarNotificacion("Contraseña actualizada correctamente.", "exito");
        overlay.querySelector("#txtNuevaContrasena").value = "";
      } catch (err) {
        mostrarNotificacion("Error al actualizar contraseña: " + err.message, "error");
      } finally {
        btnGuardarContrasena.disabled = false;
        btnGuardarContrasena.textContent = "Actualizar contraseña";
      }
    };
  };
});
