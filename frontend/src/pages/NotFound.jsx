import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="page-wrap min-h-screen py-12">
      <div className="flex w-full flex-col items-center justify-center gap-6 text-center">
        <p className="tag">404</p>
        <h1 className="font-display text-3xl font-semibold text-ink">
          Pagina no encontrada
        </h1>
        <p className="text-sm text-slate-600">
          La ruta no existe. Puedes volver al inicio y continuar con el flujo.
        </p>
        <Link to="/login" className="primary-button">
          Volver al login
        </Link>
      </div>
    </div>
  );
}
