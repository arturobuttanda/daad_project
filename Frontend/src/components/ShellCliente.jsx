import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import { notificar_cambio_autenticacion } from "../utils/authEvents.js";
import { actualizar_perfil_usuario } from "../utils/profileApi.js";
import {
  EVENTO_CAMBIO_NOTIFICACION,
  agregar_notificacion,
  limpiar_notificaciones,
  leer_notificaciones,
} from "../utils/notificationEvents.js";

const elementosNavegacion = [
  { a: "/cliente", etiqueta: "Marketplace", corto: "MP", icono: IconoMercado },
  { a: "/cliente/historial", etiqueta: "Pedidos", corto: "PE", icono: IconoPedidos },
];

function IconoMercado({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 7h16l-1.5 12h-13z" />
      <path d="M8 7a4 4 0 0 1 8 0" />
    </svg>
  );
}

function IconoPedidos({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M7 4h10l2 4v12H5V8z" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </svg>
  );
}

function IconoPerfil({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 21a8 8 0 0 0-16 0" />
      <circle cx="12" cy="8" r="4" />
    </svg>
  );
}

function IconoCampana({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M15 17H5l1.4-1.4A2 2 0 0 0 7 14.2V10a5 5 0 1 1 10 0v4.2a2 2 0 0 0 .6 1.4L19 17h-4" />
      <path d="M10 17a2 2 0 0 0 4 0" />
    </svg>
  );
}

function IconoCerrarSesion({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10 17l5-5-5-5" />
      <path d="M15 12H4" />
      <path d="M20 4v16" />
    </svg>
  );
}

function IconoReloj({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function IconoChevronIzquierda({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M14 18l-6-6 6-6" />
    </svg>
  );
}

function IconoChevronDerecha({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10 6l6 6-6 6" />
    </svg>
  );
}

export default function ShellCliente({ title, subtitle, children }) {
  const refContenedor = useRef(null);
  const ubicacion = useLocation();
  const [barraColapsada, setBarraColapsada] = useState(() => localStorage.getItem("clientSidebarCollapsed") === "true");
  const [menuActivo, setMenuActivo] = useState(null);
  const [seccionPerfil, setSeccionPerfil] = useState("menu");
  const [notificaciones, setNotificaciones] = useState(() => leer_notificaciones());
  const [formularioPerfil, setFormularioPerfil] = useState(() => ({
    nombreUsuario: localStorage.getItem("userName") || "",
    contrasena: "",
    confirmarContrasena: "",
  }));
  const nombreUsuario = formularioPerfil.nombreUsuario;

  useEffect(() => {
    localStorage.setItem("clientSidebarCollapsed", String(barraColapsada));
  }, [barraColapsada]);

  useEffect(() => {
    const sincronizarNotificaciones = () => {
      setNotificaciones(leer_notificaciones());
    };

    const manejarClicFuera = (evento) => {
      if (refContenedor.current && !refContenedor.current.contains(evento.target)) {
        setMenuActivo(null);
        setSeccionPerfil("menu");
      }
    };

    const manejarEscape = (evento) => {
      if (evento.key === "Escape") {
        setMenuActivo(null);
        setSeccionPerfil("menu");
      }
    };

    window.addEventListener(EVENTO_CAMBIO_NOTIFICACION, sincronizarNotificaciones);
    document.addEventListener("mousedown", manejarClicFuera);
    document.addEventListener("keydown", manejarEscape);

    return () => {
      window.removeEventListener(EVENTO_CAMBIO_NOTIFICACION, sincronizarNotificaciones);
      document.removeEventListener("mousedown", manejarClicFuera);
      document.removeEventListener("keydown", manejarEscape);
    };
  }, []);

  const manejarCerrarSesion = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    localStorage.removeItem("vendorSidebarCollapsed");
    localStorage.removeItem("clientSidebarCollapsed");
    notificar_cambio_autenticacion();
  };

  const manejarEnvioPerfil = async (evento) => {
    evento.preventDefault();

    const nombreRecortado = formularioPerfil.nombreUsuario.trim();
    const idUsuario = localStorage.getItem("userId");

    if (seccionPerfil === "user" && !nombreRecortado) {
      toast.error("El nombre de usuario no puede quedar vacio.");
      return;
    }

    if (seccionPerfil === "password") {
      if (!formularioPerfil.contrasena || !formularioPerfil.confirmarContrasena) {
        toast.error("Completa ambos campos de contrasena.");
        return;
      }
      if (formularioPerfil.contrasena.length < 8) {
        toast.error("La nueva contrasena debe tener al menos 8 caracteres.");
        return;
      }
      if (formularioPerfil.contrasena !== formularioPerfil.confirmarContrasena) {
        toast.error("Las contrasenas no coinciden.");
        return;
      }
    }

    try {
      const perfilActualizado = await actualizar_perfil_usuario({
        userId: idUsuario,
        userName: seccionPerfil === "user" ? nombreRecortado : undefined,
        password: seccionPerfil === "password" ? formularioPerfil.contrasena : undefined,
      });

      if (perfilActualizado?.nombre) {
        localStorage.setItem("userName", perfilActualizado.nombre);
      }

      setFormularioPerfil((actual) => ({
        ...actual,
        nombreUsuario: perfilActualizado?.nombre || actual.nombreUsuario,
        contrasena: "",
        confirmarContrasena: "",
      }));
      setMenuActivo(null);
      setSeccionPerfil("menu");
      agregar_notificacion({
        kind: "settings",
        title: "Perfil actualizado",
        detail: seccionPerfil === "user"
          ? `Se actualizo el nombre de usuario a ${perfilActualizado?.nombre || nombreRecortado}.`
          : "Se actualizo la contrasena del usuario.",
        source: "Configuracion",
      });
      toast.success("Perfil actualizado correctamente.");
    } catch (error) {
      toast.error(error.message || "No se pudo actualizar el perfil.");
    }
  };

  const manejarLimpiarNotificaciones = () => {
    limpiar_notificaciones();
    setMenuActivo(null);
    toast.success("Alertas limpiadas.");
  };

  return (
    <div ref={refContenedor} className="min-h-screen bg-[#F9F9FF]">
      <header className="border-b border-[#D6DEEE] bg-white/90 backdrop-blur">
        <div className="flex w-full flex-col gap-4 px-3 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between lg:px-6 xl:px-8">
          <Link to="/cliente" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ocean text-white shadow-glow">
              <span className="text-xs font-bold tracking-[0.18em]">NM</span>
            </div>
            <div className="min-w-0">
              <p className="font-display text-2xl font-semibold text-ocean">NexusMarket</p>
              <p className="text-xs text-slate-500">Inicio del cliente</p>
            </div>
          </Link>

          <div className="flex items-center gap-2 lg:ml-auto lg:justify-end">
            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuActivo((actual) => (actual === "notificaciones" ? null : "notificaciones"))}
                className="group relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[#CFD8EA] bg-white/80 text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
                aria-label="Abrir alertas"
                aria-expanded={menuActivo === "notificaciones"}
              >
                <IconoCampana className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
                {notificaciones.length > 0 ? (
                  <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-copper px-1 text-[10px] font-bold text-white">
                    {notificaciones.length > 9 ? "9+" : notificaciones.length}
                  </span>
                ) : null}
              </button>

              {menuActivo === "notificaciones" ? (
                <div className="absolute right-0 top-full z-40 mt-3 w-[min(92vw,24rem)] rounded-3xl border border-[#D6DEEE] bg-white p-4 shadow-[0_20px_60px_rgba(11,27,43,0.18)]">
                  <div className="flex items-start justify-between gap-3 border-b border-[#E6ECF6] pb-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Alertas</p>
                      <h3 className="mt-1 text-lg font-semibold text-ink">Actividad reciente</h3>
                    </div>
                    <button
                      type="button"
                      onClick={manejarLimpiarNotificaciones}
                      className="rounded-full border border-[#CFD8EA] px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean"
                    >
                      Limpiar
                    </button>
                  </div>

                  <div className="mt-4 max-h-80 space-y-3 overflow-y-auto pr-1">
                    {notificaciones.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-[#D6DEEE] bg-[#F8FAFF] p-4 text-sm text-slate-600">
                        No hay actividades registradas todavía.
                      </div>
                    ) : (
                      notificaciones.map((notificacion) => (
                        <div key={notificacion.id} className="rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3 transition hover:border-[#9FB3E8] hover:bg-white">
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5 rounded-xl bg-white p-2 text-ocean shadow-[0_6px_16px_rgba(11,27,43,0.08)]">
                              <IconoReloj className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-ink">{notificacion.title}</p>
                                <span className="rounded-full bg-[rgba(18,50,155,0.08)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ocean">{notificacion.kind}</span>
                              </div>
                              <p className="mt-1 text-xs text-slate-600">{notificacion.detail}</p>
                              <p className="mt-2 text-[11px] text-slate-500">{notificacion.source}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuActivo((actual) => (actual === "perfil" ? null : "perfil"))}
                className="group inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[#CFD8EA] bg-white/80 text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
                aria-label="Abrir configuracion de perfil"
                aria-expanded={menuActivo === "perfil"}
              >
                <IconoPerfil className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
              </button>

              {menuActivo === "perfil" ? (
                <div className="absolute right-0 top-full z-40 mt-3 w-[min(92vw,28rem)] rounded-3xl border border-[#D6DEEE] bg-white p-5 shadow-[0_20px_60px_rgba(11,27,43,0.18)]">
                  <div className="flex items-start justify-between gap-3 border-b border-[#E6ECF6] pb-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Perfil</p>
                      <h3 className="mt-1 text-lg font-semibold text-ink">
                        {seccionPerfil === "menu" ? "Configuracion de cuenta" : seccionPerfil === "user" ? "Cambiar nombre de usuario" : "Cambiar contraseña"}
                      </h3>
                    </div>
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[rgba(18,50,155,0.08)] text-ocean">
                      <IconoPerfil className="h-5 w-5" />
                    </div>
                  </div>

                  {seccionPerfil === "menu" ? (
                    <div className="mt-4 space-y-3">
                      <p className="text-sm text-slate-600">Elige qué quieres cambiar dentro de esta misma ventana.</p>
                      <button type="button" onClick={() => setSeccionPerfil("user")} className="flex w-full items-center justify-between rounded-2xl border border-[#E6ECF6] px-4 py-3 text-left transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean">
                        <span>
                          <span className="block text-sm font-semibold text-ink">Cambiar nombre de usuario</span>
                          <span className="block text-xs text-slate-500">Nombre visible de la cuenta</span>
                        </span>
                        <IconoChevronDerecha className="h-4 w-4" />
                      </button>
                      <button type="button" onClick={() => setSeccionPerfil("password")} className="flex w-full items-center justify-between rounded-2xl border border-[#E6ECF6] px-4 py-3 text-left transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean">
                        <span>
                          <span className="block text-sm font-semibold text-ink">Cambiar contraseña</span>
                          <span className="block text-xs text-slate-500">Clave de acceso de la cuenta</span>
                        </span>
                        <IconoChevronDerecha className="h-4 w-4" />
                      </button>
                    </div>
                  ) : null}

                  {seccionPerfil === "user" ? (
                    <form className="mt-4 space-y-4" onSubmit={manejarEnvioPerfil}>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Nuevo nombre de usuario</span>
                        <input className="input-field mt-2" value={formularioPerfil.nombreUsuario} onChange={(evento) => setFormularioPerfil((actual) => ({ ...actual, nombreUsuario: evento.target.value }))} placeholder="Nombre de cuenta" />
                      </label>
                      <div className="flex gap-3">
                        <button type="button" onClick={() => setSeccionPerfil("menu")} className="secondary-button w-full justify-center">Volver</button>
                        <button type="submit" className="primary-button w-full justify-center">Guardar cambios</button>
                      </div>
                    </form>
                  ) : null}

                  {seccionPerfil === "password" ? (
                    <form className="mt-4 space-y-4" onSubmit={manejarEnvioPerfil}>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Nueva contraseña</span>
                        <input className="input-field mt-2" type="password" value={formularioPerfil.contrasena} onChange={(evento) => setFormularioPerfil((actual) => ({ ...actual, contrasena: evento.target.value }))} placeholder="Minimo 8 caracteres" />
                      </label>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Confirmar contraseña</span>
                        <input className="input-field mt-2" type="password" value={formularioPerfil.confirmarContrasena} onChange={(evento) => setFormularioPerfil((actual) => ({ ...actual, confirmarContrasena: evento.target.value }))} placeholder="Repite la nueva clave" />
                      </label>
                      <div className="flex gap-3">
                        <button type="button" onClick={() => setSeccionPerfil("menu")} className="secondary-button w-full justify-center">Volver</button>
                        <button type="submit" className="primary-button w-full justify-center">Guardar cambios</button>
                      </div>
                    </form>
                  ) : null}
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={manejarCerrarSesion}
              className="group inline-flex h-11 w-11 items-center overflow-hidden rounded-2xl border border-[#CFD8EA] bg-white/80 px-3 text-slate-700 transition-all duration-200 hover:w-32 hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:w-32 focus:border-[#9FB3E8] focus:bg-[#EFF4FF] focus:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
              aria-label="Salir"
            >
              <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center text-copper transition-colors duration-200 group-hover:text-ocean group-focus:text-ocean">
                <IconoCerrarSesion className="h-5 w-5" />
              </span>
              <span className="ml-2 max-w-0 overflow-hidden whitespace-nowrap text-sm font-semibold opacity-0 transition-all duration-200 group-hover:max-w-20 group-hover:opacity-100 group-focus:max-w-20 group-focus:opacity-100">
                Salir
              </span>
            </button>
          </div>
        </div>
      </header>

      <div className={[
        "grid transition-[grid-template-columns] duration-300 ease-in-out",
        barraColapsada ? "lg:grid-cols-[90px_minmax(0,1fr)]" : "lg:grid-cols-[240px_minmax(0,1fr)]",
      ].join(" ")}>
        <aside className="group relative border-r border-[#D6DEEE] bg-[#EEF2FF] px-3 py-5 transition-all duration-300">
          <button
            type="button"
            onClick={() => setBarraColapsada((actual) => !actual)}
            className={[
              "absolute -right-3 top-8 z-20 flex h-7 w-7 items-center justify-center rounded-full border border-[#C7D2FE] bg-white text-ocean shadow-[0_8px_20px_rgba(11,27,43,0.12)] transition-opacity duration-200",
              barraColapsada ? "opacity-0 group-hover:opacity-100 focus:opacity-100" : "opacity-100",
            ].join(" ")}
            aria-label={barraColapsada ? "Expandir barra lateral" : "Colapsar barra lateral"}
          >
            {barraColapsada ? <IconoChevronDerecha className="h-4 w-4" /> : <IconoChevronIzquierda className="h-4 w-4" />}
          </button>

          <div className={barraColapsada ? "flex flex-col items-center px-1" : "px-2"}>
            <div className={[
              "flex items-center gap-3 transition-all duration-300",
              barraColapsada ? "justify-center" : "justify-start",
            ].join(" ")}>
              <Link to="/cliente" className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ocean text-white shadow-glow" aria-label="Ir al inicio">
                <span className="text-xs font-bold tracking-[0.18em]">NM</span>
              </Link>
              {!barraColapsada ? (
                <div>
                  <h1 className="font-display text-2xl font-semibold text-ocean">Hola, {nombreUsuario || "Cliente"}</h1>
                  <p className="mt-1 text-xs text-slate-500">Portal del cliente</p>
                </div>
              ) : null}
            </div>

            <button type="button" onClick={() => setBarraColapsada((actual) => !actual)} className="secondary-button mt-4 w-full justify-center lg:hidden">
              {barraColapsada ? "Expandir" : "Colapsar"}
            </button>
          </div>

          <nav className="mt-5 space-y-2">
            {elementosNavegacion.map((elemento) => (
              <Link
                key={elemento.a}
                to={elemento.a}
                className={[
                  "flex items-center rounded-xl py-2.5 text-sm font-semibold transition",
                  barraColapsada ? "justify-center px-2" : "gap-3 px-3",
                  ubicacion.pathname === elemento.a ? "bg-[#6EE7B7] text-[#0F172A]" : "text-slate-700 hover:bg-white",
                ].join(" ")}
                title={barraColapsada ? elemento.etiqueta : undefined}
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-white text-ocean shadow-[0_6px_16px_rgba(11,27,43,0.08)]">
                  <elemento.icono className="h-5 w-5" />
                </span>
                {barraColapsada ? null : <span>{elemento.etiqueta}</span>}
              </Link>
            ))}
          </nav>

          <button
            type="button"
            onClick={manejarCerrarSesion}
            className={[
              "secondary-button mt-4 w-full transition-all",
              barraColapsada ? "justify-center px-3" : "",
            ].join(" ")}
            title={barraColapsada ? "Salir" : undefined}
          >
            <span className="inline-flex h-5 w-5 items-center justify-center text-copper">
              <IconoCerrarSesion className="h-5 w-5" />
            </span>
            {barraColapsada ? null : <span className="ml-2">Salir</span>}
          </button>
        </aside>

        <div className="page-wrap py-6">
          <section className="mb-6">
            <p className="tag">Cliente</p>
            <h2 className="mt-2 font-display text-4xl font-semibold text-ink">{title}</h2>
            {subtitle ? <p className="mt-2 text-sm text-slate-600">{subtitle}</p> : null}
          </section>

          <main className="space-y-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
