import { Link } from "react-router-dom";

export default function AuthNavbar({ title = "Sistema de analisis de ventas e inventario" }) {
  return (
    <header className="glass-panel flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Acceso
        </p>
        <h1 className="mt-1 break-words font-display text-xl font-semibold text-ink sm:text-2xl">
          {title}
        </h1>
      </div>
      <Link to="/" className="secondary-button w-full sm:w-auto">
        Home
      </Link>
    </header>
  );
}