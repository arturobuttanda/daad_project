import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import { notifyAuthChange } from "../utils/authEvents.js";
import { updateUserProfile } from "../utils/profileApi.js";
import {
  NOTIFICATION_CHANGE_EVENT,
  addNotification,
  clearNotifications,
  readNotifications,
} from "../utils/notificationEvents.js";

const navItems = [
  { to: "/vendedor", label: "Inventario", short: "IV", icon: InventoryIcon },
  { to: "/vendedor/reporte", label: "Finanzas", short: "FI", icon: ReportIcon },
];

function InventoryIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v9A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z" />
      <path d="M8 5v14" />
      <path d="M4 10h16" />
      <path d="M8 14h4" />
    </svg>
  );
}

function ReportIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <path d="M8 16v-4" />
      <path d="M12 16V8" />
      <path d="M16 16v-6" />
    </svg>
  );
}

function PlusIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function LogoutIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10 17l5-5-5-5" />
      <path d="M15 12H4" />
      <path d="M20 4v16" />
    </svg>
  );
}

function ProfileIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 21a8 8 0 0 0-16 0" />
      <circle cx="12" cy="8" r="4" />
    </svg>
  );
}

function BellIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M15 17H5l1.4-1.4A2 2 0 0 0 7 14.2V10a5 5 0 1 1 10 0v4.2a2 2 0 0 0 .6 1.4L19 17h-4" />
      <path d="M10 17a2 2 0 0 0 4 0" />
    </svg>
  );
}

function ClockIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function SettingsIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
      <path d="M19.4 15a7.8 7.8 0 0 0 .1-1l2-1.2-2-3.5-2.3.6a7.4 7.4 0 0 0-1.7-1L15 6h-4l-.5 2.9a7.4 7.4 0 0 0-1.7 1L6.5 9.3l-2 3.5 2 1.2a7.8 7.8 0 0 0 .1 1 7.8 7.8 0 0 0-.1 1l-2 1.2 2 3.5 2.3-.6a7.4 7.4 0 0 0 1.7 1L11 22h4l.5-2.9a7.4 7.4 0 0 0 1.7-1l2.3.6 2-3.5-2-1.2a7.8 7.8 0 0 0-.1-1Z" />
    </svg>
  );
}

function ChevronDownIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function ChevronLeftIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M14 18l-6-6 6-6" />
    </svg>
  );
}

function ChevronRightIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10 6l6 6-6 6" />
    </svg>
  );
}

export default function VendorShell({ title, subtitle, children }) {
  const shellRef = useRef(null);
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem("vendorSidebarCollapsed") === "true";
  });
  const [activeMenu, setActiveMenu] = useState(null);
  const [profileSection, setProfileSection] = useState("menu");
  const [notifications, setNotifications] = useState(() => readNotifications());
  const [profileForm, setProfileForm] = useState(() => ({
    userName: localStorage.getItem("userName") || "",
    password: "",
    confirmPassword: "",
    activityAlerts: localStorage.getItem("activityAlertsEnabled") !== "false",
  }));
  const location = useLocation();
  const userName = profileForm.userName;

  useEffect(() => {
    localStorage.setItem("vendorSidebarCollapsed", String(isCollapsed));
  }, [isCollapsed]);

  useEffect(() => {
    const syncNotifications = () => {
      setNotifications(readNotifications());
    };

    const handlePointerDown = (event) => {
      if (shellRef.current && !shellRef.current.contains(event.target)) {
        setActiveMenu(null);
        setProfileSection("menu");
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setActiveMenu(null);
        setProfileSection("menu");
      }
    };

    window.addEventListener(NOTIFICATION_CHANGE_EVENT, syncNotifications);
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener(NOTIFICATION_CHANGE_EVENT, syncNotifications);
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    localStorage.removeItem("vendorSidebarCollapsed");
    notifyAuthChange();
    toast.success("Sesion cerrada correctamente.");
  };

  const handleProfileSubmit = async (event) => {
    event.preventDefault();

    const trimmedUserName = profileForm.userName.trim();
    const userId = localStorage.getItem("userId");

    if (profileSection === "user" && !trimmedUserName) {
      toast.error("El nombre de usuario no puede quedar vacio.");
      return;
    }

    if (profileSection === "password") {
      if (!profileForm.password || !profileForm.confirmPassword) {
        toast.error("Completa ambos campos de contrasena.");
        return;
      }

      if (profileForm.password.length < 8) {
        toast.error("La nueva contrasena debe tener al menos 8 caracteres.");
        return;
      }

      if (profileForm.password !== profileForm.confirmPassword) {
        toast.error("Las contrasenas no coinciden.");
        return;
      }
    }

    localStorage.setItem("activityAlertsEnabled", String(profileForm.activityAlerts));

    try {
      const updatedProfile = await updateUserProfile({
        userId,
        userName: profileSection === "user" ? trimmedUserName : undefined,
        password: profileSection === "password" ? profileForm.password : undefined,
      });

      if (updatedProfile?.nombre) {
        localStorage.setItem("userName", updatedProfile.nombre);
      }

      setProfileForm((current) => ({
        ...current,
        userName: updatedProfile?.nombre || current.userName,
        password: "",
        confirmPassword: "",
      }));
      setActiveMenu(null);
      setProfileSection("menu");
      addNotification({
        kind: "settings",
        title: "Perfil actualizado",
        detail: profileSection === "user"
          ? `Se actualizo el nombre de usuario a ${updatedProfile?.nombre || trimmedUserName}.`
          : "Se actualizo la contrasena del usuario.",
        source: "Configuracion",
      });
      toast.success("Perfil actualizado correctamente.");
    } catch (error) {
      toast.error(error.message || "No se pudo actualizar el perfil.");
    }
  };

  const handleClearNotifications = () => {
    clearNotifications();
    setActiveMenu(null);
    toast.success("Alertas limpiadas.");
  };

  const openProfileSection = (section) => {
    setProfileSection(section);
  };

  const closeProfilePanel = () => {
    setActiveMenu(null);
    setProfileSection("menu");
  };

  return (
    <div ref={shellRef} className="min-h-screen bg-[#F9F9FF]">
      <header className="border-b border-[#D6DEEE] bg-white/90 backdrop-blur">
        <div className="flex w-full flex-col gap-4 px-3 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between lg:px-6 xl:px-8">
          <Link to="/vendedor" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ocean text-white shadow-glow">
              <span className="text-xs font-bold tracking-[0.18em]">NM</span>
            </div>
            <div className="min-w-0">
              <p className="font-display text-2xl font-semibold text-ocean">NexusMarket</p>
              <p className="text-xs text-slate-500">Inicio del vendedor</p>
            </div>
          </Link>

          <div className="flex items-center gap-2 lg:ml-auto lg:justify-end">
            <div className="relative">
              <button
                type="button"
                onClick={() => setActiveMenu((current) => (current === "notifications" ? null : "notifications"))}
                className="group relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[#CFD8EA] bg-white/80 text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
                aria-label="Abrir alertas"
                aria-expanded={activeMenu === "notifications"}
              >
                <BellIcon className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
                {notifications.length > 0 ? (
                  <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-copper px-1 text-[10px] font-bold text-white">
                    {notifications.length > 9 ? "9+" : notifications.length}
                  </span>
                ) : null}
              </button>

              {activeMenu === "notifications" ? (
                <div className="absolute right-0 top-full z-40 mt-3 w-[min(92vw,24rem)] rounded-3xl border border-[#D6DEEE] bg-white p-4 shadow-[0_20px_60px_rgba(11,27,43,0.18)]">
                  <div className="flex items-start justify-between gap-3 border-b border-[#E6ECF6] pb-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Alertas</p>
                      <h3 className="mt-1 text-lg font-semibold text-ink">Actividad reciente</h3>
                    </div>
                    <button
                      type="button"
                      onClick={handleClearNotifications}
                      className="rounded-full border border-[#CFD8EA] px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean"
                    >
                      Limpiar
                    </button>
                  </div>

                  <div className="mt-4 max-h-80 space-y-3 overflow-y-auto pr-1">
                    {notifications.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-[#D6DEEE] bg-[#F8FAFF] p-4 text-sm text-slate-600">
                        No hay actividades registradas todavía.
                      </div>
                    ) : (
                      notifications.map((notification) => (
                        <div
                          key={notification.id}
                          className="rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3 transition hover:border-[#9FB3E8] hover:bg-white"
                        >
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5 rounded-xl bg-white p-2 text-ocean shadow-[0_6px_16px_rgba(11,27,43,0.08)]">
                              <ClockIcon className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-ink">{notification.title}</p>
                                <span className="rounded-full bg-[rgba(18,50,155,0.08)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ocean">
                                  {notification.kind}
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-slate-600">{notification.detail}</p>
                              <p className="mt-2 text-[11px] text-slate-500">{notification.source}</p>
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
                onClick={() => setActiveMenu((current) => (current === "profile" ? null : "profile"))}
                className="group inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[#CFD8EA] bg-white/80 text-slate-600 transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
                aria-label="Abrir configuracion de perfil"
                aria-expanded={activeMenu === "profile"}
              >
                <ProfileIcon className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
              </button>

              {activeMenu === "profile" ? (
                <div className="absolute right-0 top-full z-40 mt-3 w-[min(92vw,28rem)] rounded-3xl border border-[#D6DEEE] bg-white p-5 shadow-[0_20px_60px_rgba(11,27,43,0.18)]">
                  <div className="flex items-start justify-between gap-3 border-b border-[#E6ECF6] pb-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Perfil</p>
                      <h3 className="mt-1 text-lg font-semibold text-ink">
                        {profileSection === "menu"
                          ? "Configuracion de cuenta"
                          : profileSection === "user"
                            ? "Cambiar usuario"
                            : "Cambiar contrasena"}
                      </h3>
                    </div>
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[rgba(18,50,155,0.08)] text-ocean">
                      <ProfileIcon className="h-5 w-5" />
                    </div>
                  </div>

                  {profileSection === "menu" ? (
                    <div className="mt-4 space-y-3">
                      <p className="text-sm text-slate-600">Elige qué quieres cambiar dentro de esta misma ventana.</p>
                      <button
                        type="button"
                        onClick={() => openProfileSection("user")}
                        className="flex w-full items-center justify-between rounded-2xl border border-[#E6ECF6] px-4 py-3 text-left transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean"
                      >
                        <span>
                          <span className="block text-sm font-semibold text-ink">Cambiar nombre de usuario</span>
                          <span className="block text-xs text-slate-500">Nombre visible de la cuenta</span>
                        </span>
                        <ChevronRightIcon className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => openProfileSection("password")}
                        className="flex w-full items-center justify-between rounded-2xl border border-[#E6ECF6] px-4 py-3 text-left transition hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean"
                      >
                        <span>
                          <span className="block text-sm font-semibold text-ink">Cambiar contraseña</span>
                          <span className="block text-xs text-slate-500">Clave de acceso del vendedor</span>
                        </span>
                        <ChevronRightIcon className="h-4 w-4" />
                      </button>
                      <div className="flex items-center justify-between rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3">
                        <div>
                          <p className="text-sm font-semibold text-ink">Alertas de actividad</p>
                          <p className="text-xs text-slate-500">Recibe avisos de CSV, productos y cambios importantes.</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setProfileForm((current) => ({ ...current, activityAlerts: !current.activityAlerts }))}
                          className={[
                            "relative inline-flex h-7 w-12 items-center rounded-full transition",
                            profileForm.activityAlerts ? "bg-ocean" : "bg-slate-300",
                          ].join(" ")}
                          aria-pressed={profileForm.activityAlerts}
                        >
                          <span
                            className={[
                              "inline-block h-5 w-5 transform rounded-full bg-white shadow transition",
                              profileForm.activityAlerts ? "translate-x-6" : "translate-x-1",
                            ].join(" ")}
                          />
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {profileSection === "user" ? (
                    <form className="mt-4 space-y-4" onSubmit={handleProfileSubmit}>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Nuevo nombre de usuario</span>
                        <input
                          className="input-field mt-2"
                          value={profileForm.userName}
                          onChange={(event) => setProfileForm((current) => ({ ...current, userName: event.target.value }))}
                          placeholder="Nombre de cuenta"
                        />
                      </label>

                      <div className="flex gap-3">
                        <button type="button" onClick={() => setProfileSection("menu")} className="secondary-button w-full justify-center">
                          Volver
                        </button>
                        <button type="submit" className="primary-button w-full justify-center">
                          Guardar cambios
                        </button>
                      </div>
                    </form>
                  ) : null}

                  {profileSection === "password" ? (
                    <form className="mt-4 space-y-4" onSubmit={handleProfileSubmit}>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Nueva contraseña</span>
                        <input
                          className="input-field mt-2"
                          type="password"
                          value={profileForm.password}
                          onChange={(event) => setProfileForm((current) => ({ ...current, password: event.target.value }))}
                          placeholder="Minimo 8 caracteres"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">Confirmar contraseña</span>
                        <input
                          className="input-field mt-2"
                          type="password"
                          value={profileForm.confirmPassword}
                          onChange={(event) => setProfileForm((current) => ({ ...current, confirmPassword: event.target.value }))}
                          placeholder="Repite la nueva clave"
                        />
                      </label>

                      <div className="rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3 text-sm text-slate-600">
                        <p className="font-semibold text-ink">Sugerencia</p>
                        <p className="mt-1">Usa una contraseña única y de al menos 8 caracteres.</p>
                      </div>

                      <div className="flex gap-3">
                        <button type="button" onClick={() => setProfileSection("menu")} className="secondary-button w-full justify-center">
                          Volver
                        </button>
                        <button type="submit" className="primary-button w-full justify-center">
                          Guardar cambios
                        </button>
                      </div>
                    </form>
                  ) : null}
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="group inline-flex h-11 w-11 items-center overflow-hidden rounded-2xl border border-[#CFD8EA] bg-white/80 px-3 text-slate-700 transition-all duration-200 hover:w-44 hover:border-[#9FB3E8] hover:bg-[#EFF4FF] hover:text-ocean focus:w-44 focus:border-[#9FB3E8] focus:bg-[#EFF4FF] focus:text-ocean focus:outline-none focus:ring-2 focus:ring-[#9FB3E8]"
              aria-label="Cerrar sesion"
            >
              <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center text-copper transition-colors duration-200 group-hover:text-ocean group-focus:text-ocean">
                <LogoutIcon className="h-5 w-5" />
              </span>
              <span className="ml-2 max-w-0 overflow-hidden whitespace-nowrap text-sm font-semibold opacity-0 transition-all duration-200 group-hover:max-w-32 group-hover:opacity-100 group-focus:max-w-32 group-focus:opacity-100">
                Cerrar sesion
              </span>
            </button>
          </div>
        </div>
      </header>

      <div
        className={[
          "grid transition-[grid-template-columns] duration-300 ease-in-out",
          isCollapsed ? "lg:grid-cols-[88px_minmax(0,1fr)]" : "lg:grid-cols-[220px_minmax(0,1fr)]",
        ].join(" ")}
      >
        <aside className="group relative border-r border-[#D6DEEE] bg-[#EEF2FF] px-3 py-5 transition-all duration-300">
          <button
            type="button"
            onClick={() => setIsCollapsed((current) => !current)}
            className={[
              "absolute -right-3 top-8 z-20 flex h-7 w-7 items-center justify-center rounded-full border border-[#C7D2FE] bg-white text-ocean shadow-[0_8px_20px_rgba(11,27,43,0.12)] transition-opacity duration-200",
              isCollapsed ? "opacity-0 group-hover:opacity-100 focus:opacity-100" : "opacity-100",
            ].join(" ")}
            aria-label={isCollapsed ? "Expandir barra lateral" : "Colapsar barra lateral"}
          >
            {isCollapsed ? <ChevronRightIcon className="h-4 w-4" /> : <ChevronLeftIcon className="h-4 w-4" />}
          </button>

          <div className={isCollapsed ? "flex flex-col items-center px-1" : "px-2"}>
            <div
              className={[
                "flex items-center gap-3 transition-all duration-300",
                isCollapsed ? "justify-center" : "justify-start",
              ].join(" ")}
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ocean text-white shadow-glow">
                <span className="text-xs font-bold tracking-[0.18em]">V</span>
              </div>
              {!isCollapsed ? (
                <div>
                  <h1 className="font-display text-2xl font-semibold text-ocean">Hola, {userName || "Seller"}</h1>
                  <p className="mt-1 text-xs text-slate-500">Portal del vendedor</p>
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={() => setIsCollapsed((current) => !current)}
              className="secondary-button mt-4 w-full justify-center lg:hidden"
            >
              {isCollapsed ? "Expandir" : "Colapsar"}
            </button>
          </div>

          <nav className="mt-5 space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={[
                  "flex items-center rounded-xl py-2.5 text-sm font-semibold transition",
                  isCollapsed ? "justify-center px-2" : "gap-3 px-3",
                  location.pathname === item.to ? "bg-[#6EE7B7] text-[#0F172A]" : "text-slate-700 hover:bg-white",
                ].join(" ")}
                title={isCollapsed ? item.label : undefined}
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-white text-ocean shadow-[0_6px_16px_rgba(11,27,43,0.08)]">
                  <item.icon className="h-5 w-5" />
                </span>
                {isCollapsed ? null : <span>{item.label}</span>}
              </Link>
            ))}
          </nav>

          <Link
            to="/vendedor#add-product"
            className={[
              "primary-button mt-6 w-full transition-all",
              isCollapsed ? "justify-center px-3" : "",
            ].join(" ")}
            title={isCollapsed ? "Add Product" : undefined}
          >
            <span className="inline-flex h-5 w-5 items-center justify-center">
              <PlusIcon className="h-5 w-5" />
            </span>
            {isCollapsed ? null : <span className="ml-2">Add Product</span>}
          </Link>

          <button
            type="button"
            onClick={handleLogout}
            className={[
              "secondary-button mt-3 w-full transition-all",
              isCollapsed ? "justify-center px-3" : "",
            ].join(" ")}
            title={isCollapsed ? "Cerrar sesion" : undefined}
          >
            <span className="inline-flex h-5 w-5 items-center justify-center text-copper">
              <LogoutIcon className="h-5 w-5" />
            </span>
            {isCollapsed ? null : <span className="ml-2">Cerrar sesion</span>}
          </button>
        </aside>

        <main className="p-4 sm:p-6 lg:p-8">
          <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-[#D6DEEE] pb-4">
            <div>
              <h2 className="font-display text-3xl font-semibold text-ink">{title}</h2>
              {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
            </div>
            <div className="text-right text-sm text-slate-600">
              <p>{userName || "Seller"}</p>
              <p className="text-xs">Nexus Partner</p>
            </div>
          </header>
          <div className="space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
