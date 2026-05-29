import { Link, useLocation } from "react-router-dom";
import { notifyAuthChange } from "../utils/authEvents.js";

const navItems = [
  { to: "/cliente", label: "Marketplace" },
  { to: "/cliente/historial", label: "Orders" },
];

export default function ClientShell({ title, subtitle, children }) {
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    localStorage.removeItem("vendorSidebarCollapsed");
    notifyAuthChange();
  };

  return (
    <div className="min-h-screen bg-[#F9F9FF]">
      <div className="border-b border-[#D6DEEE] bg-white">
        <div className="page-wrap flex flex-wrap items-center gap-3 py-3">
          <Link to="/cliente" className="font-display text-3xl font-semibold text-ocean">
            NexusMarket
          </Link>
          <input
            type="search"
            className="input-field max-w-sm"
            placeholder="Search marketplace..."
          />
          <div className="ml-auto flex items-center gap-2">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={[
                  "rounded-lg px-3 py-2 text-sm font-semibold transition",
                  location.pathname === item.to
                    ? "border-b-2 border-ocean text-ocean"
                    : "text-slate-600 hover:text-ocean",
                ].join(" ")}
              >
                {item.label}
              </Link>
            ))}
            <button type="button" onClick={handleLogout} className="secondary-button">
              Salir
            </button>
          </div>
        </div>
      </div>

      <div className="page-wrap py-6">
        <section className="mb-6">
          <p className="tag">Cliente</p>
          <h2 className="mt-2 font-display text-4xl font-semibold text-ink">{title}</h2>
          {subtitle ? <p className="mt-2 text-sm text-slate-600">{subtitle}</p> : null}
        </section>

        <main className="space-y-6">{children}</main>
      </div>
    </div>
  );
}
