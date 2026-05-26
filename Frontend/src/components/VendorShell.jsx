import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import UserNavbar from "./UserNavbar.jsx";

const navItems = [
  { to: "/vendedor", label: "Gestión de productos", short: "GP" },
  { to: "/vendedor/reporte", label: "Reporte financiero", short: "RF" },
];

export default function VendorShell({ title, subtitle, children }) {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem("vendorSidebarCollapsed") === "true";
  });
  const location = useLocation();
  const userName = localStorage.getItem("userName");

  useEffect(() => {
    localStorage.setItem("vendorSidebarCollapsed", String(isCollapsed));
  }, [isCollapsed]);

  const handleLogout = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    localStorage.removeItem("vendorSidebarCollapsed");
    toast.success("Sesion cerrada correctamente.");
  };

  return (
    <div className="min-h-screen">
      <div className="page-wrap relative py-8">
        <div className="mb-6">
          <UserNavbar userName={userName} onLogout={handleLogout} homeLabel="Panel de vendedor" />
        </div>
        <div className="absolute inset-0 -z-10">
          <div className="absolute left-[-10%] top-[-20%] h-72 w-72 rounded-full bg-[rgba(212,163,115,0.25)] blur-3xl" />
          <div className="absolute right-[-5%] top-10 h-80 w-80 rounded-full bg-[rgba(31,78,95,0.2)] blur-3xl" />
        </div>
        <div
          className="flex flex-col gap-8 lg:grid lg:items-start"
          style={{
            gridTemplateColumns: isCollapsed
              ? "84px minmax(0, 1fr)"
              : "240px minmax(0, 1fr)",
          }}
        >
          <aside className="w-full shrink-0 lg:min-h-[calc(100vh-4rem)] lg:self-stretch">
            <div
              className={`glass-panel h-full overflow-hidden transition-all ${
                isCollapsed
                  ? "w-[84px] p-3"
                  : "w-[240px] p-4 sm:p-5"
              }`}
            >
              <div className={`flex items-center justify-between gap-3 ${isCollapsed ? "lg:justify-center" : ""}`}>
                <div className={isCollapsed ? "sr-only" : "min-w-0"}>
                  <div className="min-w-0">
                    <p className="tag">Vendedor</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsCollapsed((current) => !current)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-sand bg-white/80 text-ocean transition hover:bg-white"
                  aria-label={
                    isCollapsed ? "Expandir sidebar" : "Ocultar sidebar"
                  }
                >
                  <span className="text-lg leading-none" aria-hidden="true">
                    {isCollapsed ? "›" : "‹"}
                  </span>
                </button>
              </div>
              <nav className={`mt-8 space-y-2 ${isCollapsed ? "lg:space-y-3" : ""}`}>
                {navItems.map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    title={item.label}
                    aria-label={item.label}
                    className={[
                      "flex items-center rounded-2xl transition hover:bg-white/70",
                      location.pathname === item.to ? "bg-white/80 shadow-soft" : "",
                      isCollapsed
                        ? "justify-center px-2 py-3"
                        : "justify-between px-3 py-3 sm:px-4",
                    ].join(" ")}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className={`flex h-9 w-9 items-center justify-center rounded-2xl text-sm font-semibold ${
                          isCollapsed
                            ? "bg-ocean text-white"
                            : "bg-white/70 text-ocean"
                        }`}
                      >
                        {item.short}
                      </span>
                      <span
                        className={isCollapsed ? "sr-only" : "break-words text-left text-sm font-semibold leading-tight text-slate-700"}
                      >
                        {item.label}
                      </span>
                    </div>
                    {isCollapsed ? null : (
                      <span className="text-xs opacity-70">Ir</span>
                    )}
                  </Link>
                ))}
              </nav>

            </div>
          </aside>
          <main className="min-w-0 space-y-6">
            <header className="glass-panel px-6 py-5">
              <p className="tag">Panel operativo</p>
              <h2 className="mt-3 break-words font-display text-2xl font-semibold text-ink sm:text-3xl">
                {title}
              </h2>
              {subtitle ? (
                <p className="mt-2 max-w-2xl text-sm text-slate-600">
                  {subtitle}
                </p>
              ) : null}
            </header>
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
