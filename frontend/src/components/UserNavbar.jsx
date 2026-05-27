import { Link, useNavigate } from "react-router-dom";

export default function UserNavbar({ userName, onLogout, homeLabel = "Inicio" }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    if (typeof onLogout === "function") {
      onLogout();
    }
    navigate("/login");
  };

  return (
    <header className="glass-panel flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Bienvenido {userName || "usuario"}
        </p>
        <h1 className="mt-1 break-words font-display text-xl font-semibold text-ink sm:text-2xl">
          {homeLabel}
        </h1>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className="w-full rounded-2xl border border-copper px-4 py-2 text-sm font-semibold text-copper transition hover:bg-[rgba(242,107,91,0.08)] sm:w-auto"
      >
        Cerrar sesion
      </button>
    </header>
  );
}