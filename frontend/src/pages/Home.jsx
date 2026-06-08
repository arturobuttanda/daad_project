import { Link } from "react-router-dom";
import BarraUsuario from "../components/UserNavbar.jsx";
import { notificar_cambio_autenticacion } from "../utils/authEvents.js";

const sidebarItems = [
  {
    title: "Registro",
    detail: "Cuentas para vendedor o cliente.",
  },
  {
    title: "Productos",
    detail: "Ver y registrar productos clave.",
  },
  {
    title: "Finanzas",
    detail: "Resultados financieros resumidos.",
  },
];

const actionCards = [
  {
    title: "Ver productos",
    detail: "Consulta stock, marca y estado de productos.",
    clientTo: "/cliente",
    vendorTo: "/vendedor",
  },
  {
    title: "Registrar productos",
    detail: "Agrega nuevos items con datos esenciales.",
    vendorTo: "/vendedor",
    fallbackTo: "/login",
  },
  {
    title: "Resultados financieros",
    detail: "Visualiza ingresos, costos y margen.",
    vendorTo: "/vendedor/reporte",
    fallbackTo: "/login",
  },
];

export default function Home() {
  const userName = localStorage.getItem("userName");
  const userType = localStorage.getItem("userType");
  const isVendor = userType === "Vendedor";
  const isClient = userType === "Cliente";
  const homeLabel =
    userType === "Vendedor"
      ? "Pagina principal de vendedor"
      : "Pagina principal de cliente";

  const handleLogout = () => {
    localStorage.removeItem("isRegistered");
    localStorage.removeItem("userType");
    localStorage.removeItem("userName");
    localStorage.removeItem("userId");
    notificar_cambio_autenticacion();
  };

  return (
    <div className="min-h-screen">
      <div className="page-wrap py-8">
        {userName ? (
            <div className="mb-6">
            <BarraUsuario
              userName={userName}
              onLogout={handleLogout}
              homeLabel={homeLabel}
            />
          </div>
        ) : (
          <header className="glass-panel flex flex-wrap items-center justify-between gap-4 px-6 py-4">
            <div>
              <h1 className="mt-3 font-display text-2xl font-semibold text-ink">
                Sistema de analisis de ventas e inventario
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <Link to="/login" className="secondary-button">
                Iniciar sesión
              </Link>
              <Link to="/registro" className="primary-button">
                Registro
              </Link>
            </div>
          </header>
        )}

        <main className="mt-8 space-y-6">
          <section className="glass-panel relative overflow-hidden p-6 sm:p-8">
            <div className="orb orb-amber" />
            <div className="orb orb-coral" />
            <div className="orb orb-teal" />
            <div className="relative z-10 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <div>
                <h2 className="mt-3 break-words font-display text-3xl font-semibold text-ink sm:text-4xl">
                  Un entorno claro para ventas, inventario y resultados
                </h2>
                <p className="mt-3 max-w-2xl text-sm text-slate-600 sm:text-base">
                  Este sistema centraliza productos y ventas en una vista
                  ordenada. Desde aqui puedes registrarte como vendedor o
                  cliente y acceder a funciones clave del proyecto.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="rounded-full bg-[rgba(26,127,143,0.15)] px-4 py-1 text-xs font-semibold text-ocean">
                    Registro vendedor
                  </span>
                  <span className="rounded-full bg-[rgba(242,107,91,0.15)] px-4 py-1 text-xs font-semibold text-copper">
                    Registro cliente
                  </span>
                </div>
              </div>
              <div className="grid gap-3">
                <div className="glass-panel shine-card lift-card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Vista rapida
                  </p>
                  <h3 className="mt-2 font-display text-lg font-semibold text-ink">
                    Productos en un vistazo
                  </h3>
                  <p className="mt-2 text-sm text-slate-600">
                    Consulta el inventario y registra nuevos productos en
                    minutos.
                  </p>
                </div>
                <div className="glass-panel lift-card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Resultados
                  </p>
                  <h3 className="mt-2 font-display text-lg font-semibold text-ink">
                    Finanzas visibles
                  </h3>
                  <p className="mt-2 text-sm text-slate-600">
                    Accede a resultados financieros de forma clara y directa.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            {actionCards.map((card) => {
              const target = isVendor
                ? card.vendorTo
                : isClient
                  ? card.clientTo || "/cliente"
                  : card.fallbackTo || "/login";

              return (
                <Link
                  key={card.title}
                  to={target}
                  className="glass-panel lift-card block p-5 transition hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="h-2 w-2 rounded-full bg-copper" />
                    <h3 className="font-display text-lg font-semibold text-ink">
                      {card.title}
                    </h3>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{card.detail}</p>
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-ocean">
                    Abrir pagina
                  </p>
                </Link>
              );
            })}
          </section>
        </main>
      </div>
    </div>
  );
}
