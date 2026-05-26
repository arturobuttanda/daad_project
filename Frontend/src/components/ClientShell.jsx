import { Link, useLocation } from "react-router-dom";
import UserNavbar from "./UserNavbar.jsx";

const navItems = [
  { to: "/cliente", label: "Productos" },
  { to: "/cliente/historial", label: "Historial" },
];

export default function ClientShell({ title, subtitle, children }) {
  const location = useLocation();
  const userName = localStorage.getItem("userName");

  const handleLogout = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    localStorage.removeItem("vendorSidebarCollapsed");
  };

  return (
    <div className="min-h-screen">
      <div className="page-wrap py-8">
        <UserNavbar userName={userName} onLogout={handleLogout} homeLabel="Panel de cliente" />

        <div className="mt-6 flex flex-wrap gap-3">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={[
                "rounded-full border px-4 py-2 text-sm font-semibold transition",
                location.pathname === item.to
                  ? "border-ocean bg-ocean text-white"
                  : "border-sand bg-white/80 text-slate-700 hover:bg-white",
              ].join(" ")}
            >
              {item.label}
            </Link>
          ))}
        </div>

        <section className="mt-6 glass-panel px-6 py-5">
          <p className="tag">Cliente</p>
          <h2 className="mt-3 break-words font-display text-2xl font-semibold text-ink sm:text-3xl">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-2 max-w-3xl text-sm text-slate-600">{subtitle}</p>
          ) : null}
        </section>

        <main className="mt-6 space-y-6">{children}</main>
      </div>
    </div>
  );
}
