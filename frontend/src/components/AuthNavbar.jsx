import { Link } from "react-router-dom";

export default function BarraAutenticacion({ title = "Sistema de analisis de ventas e inventario" }) {
  return (
    <header className="mx-auto flex w-full max-w-3xl items-center justify-between">
      <div>
        <p className="text-sm font-semibold text-ocean">NexusMarket</p>
        <h1 className="mt-1 text-base text-slate-600 sm:text-lg">{title}</h1>
      </div>
      <Link to="/" className="secondary-button">
        Inicio
      </Link>
    </header>
  );
}