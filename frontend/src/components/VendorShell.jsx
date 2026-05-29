import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import { notifyAuthChange } from "../utils/authEvents.js";

const navItems = [
  { to: "/vendedor", label: "Inventario", short: "IV" },
  { to: "/vendedor/reporte", label: "Finanzas", short: "FI" },
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
    notifyAuthChange();
    toast.success("Sesion cerrada correctamente.");
  };

  return (
    <div className="min-h-screen bg-[#F9F9FF]">
      <div className="grid min-h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="border-r border-[#D6DEEE] bg-[#EEF2FF] px-3 py-5">
          <div className="px-2">
            <h1 className="font-display text-3xl font-semibold text-ocean">Merchant Portal</h1>
            {!isCollapsed ? <p className="mt-1 text-xs text-slate-500">Premium Seller</p> : null}
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed((current) => !current)}
            className="secondary-button mt-4 w-full"
          >
            {isCollapsed ? "Expandir" : "Colapsar"}
          </button>

          <nav className="mt-5 space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={[
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition",
                  location.pathname === item.to
                    ? "bg-[#6EE7B7] text-[#0F172A]"
                    : "text-slate-700 hover:bg-white",
                ].join(" ")}
              >
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-white text-xs text-ocean">
                  {item.short}
                </span>
                {isCollapsed ? null : <span>{item.label}</span>}
              </Link>
            ))}
          </nav>

          <Link to="/vendedor#add-product" className="primary-button mt-6 w-full">
            + Add Product
          </Link>

          <button type="button" onClick={handleLogout} className="secondary-button mt-3 w-full">
            Cerrar sesion
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
