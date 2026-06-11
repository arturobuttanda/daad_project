import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import ShellCliente from "../components/ShellCliente.jsx";

const URL_API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PERIODOS = [
  { valor: "30d", etiqueta: "30 días" },
  { valor: "3m", etiqueta: "3 meses" },
  { valor: "6m", etiqueta: "6 meses" },
  { valor: "1y", etiqueta: "1 año" },
  { valor: "all", etiqueta: "Histórico" },
];

function formatearDinero(valor) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(valor || 0));
}

function truncarTexto(valor, longitudMaxima = 48) {
  const valorLimpio = String(valor || "").trim();
  if (!valorLimpio) {
    return "Producto";
  }
  if (valorLimpio.length <= longitudMaxima) {
    return valorLimpio;
  }
  return `${valorLimpio.slice(0, longitudMaxima - 3)}...`;
}

export default function HistorialCliente() {
  const idUsuario = localStorage.getItem("userId");
  const [periodo, setPeriodo] = useState("30d");
  const [pagina, setPagina] = useState(1);
  const [tamanoPagina] = useState(8);
  const [totalPaginas, setTotalPaginas] = useState(1);
  const [totalElementos, setTotalElementos] = useState(0);
  const [compras, setCompras] = useState([]);
  const [ticketSeleccionado, setTicketSeleccionado] = useState(null);
  const [cargando, setCargando] = useState(false);

  const cargarHistorial = async (siguientePagina = pagina, siguientePeriodo = periodo) => {
    if (!idUsuario) {
      return;
    }
    setCargando(true);
    try {
      const respuesta = await fetch(
        `${URL_API}/api/cliente/compras?id_cliente=${encodeURIComponent(idUsuario)}&period=${siguientePeriodo}&page=${siguientePagina}&page_size=${tamanoPagina}`
      );
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo cargar el historial.");
      }
      setCompras(Array.isArray(datos.items) ? datos.items : []);
      setTotalPaginas(Number(datos.total_pages || 1));
      setTotalElementos(Number(datos.total_items || 0));
      setPagina(Number(datos.page || siguientePagina));
    } catch (error) {
      toast.error(error.message || "No se pudo cargar el historial.");
      setCompras([]);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarHistorial(1, periodo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo]);

  const abrirTicket = async (idVenta) => {
    try {
      const respuesta = await fetch(`${URL_API}/api/cliente/compras/${encodeURIComponent(idVenta)}`);
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo cargar el ticket.");
      }
      setTicketSeleccionado(datos);
    } catch (error) {
      toast.error(error.message || "No se pudo cargar el ticket.");
    }
  };

  return (
    <ShellCliente
      title="Historial de compras"
      subtitle="Consulta tus compras"
    >
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <div className="glass-panel p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="tag">Historial</p>
              <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                Compras registradas
              </h3>

            </div>
            <div className="flex flex-wrap gap-2">
              {PERIODOS.map((opcion) => (
                <button
                  key={opcion.valor}
                  type="button"
                  className={periodo === opcion.valor ? "primary-button" : "secondary-button"}
                  onClick={() => setPeriodo(opcion.valor)}
                >
                  {opcion.etiqueta}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {cargando ? (
              <p className="text-sm text-slate-500">Cargando historial...</p>
            ) : compras.length === 0 ? (
              <p className="text-sm text-slate-500">No hay compras para este rango de fechas.</p>
            ) : (
              compras.map((compra) => (
                <button
                  key={compra.id_venta}
                  type="button"
                  onClick={() => abrirTicket(compra.id_venta)}
                  className="w-full rounded-3xl border border-sand bg-white p-5 text-left transition hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_12px_30px_rgba(11,27,43,0.06)]"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                            Pedido n.º {compra.numero_pedido || compra.id_venta}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">{compra.fecha_venta}</p>
                        </div>
                        <span className="rounded-full bg-[#EAF2FF] px-3 py-1 text-xs font-semibold text-ocean">
                          Compra registrada
                        </span>
                      </div>

                      <div className="mt-4 space-y-3">
                        {Array.isArray(compra.productos) && compra.productos.length > 0 ? (
                          compra.productos.slice(0, 3).map((elemento) => (
                            <div key={`${compra.id_venta}-${elemento.id_producto}`} className="flex items-start gap-3">
                              <span className="mt-2 h-2 w-2 flex-none rounded-full bg-ocean" />
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-ink">{truncarTexto(elemento.nombre, 72)}</p>
                                <p className="text-xs text-slate-500">{elemento.cantidad} unidades</p>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-slate-500">No hay detalles disponibles.</p>
                        )}
                        {Array.isArray(compra.productos) && compra.productos.length > 3 ? (
                          <p className="text-xs text-slate-500">
                            +{compra.productos.length - 3} productos más
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-col items-start gap-3 lg:items-end">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Total</p>
                      <p className="text-2xl font-semibold text-ink">{formatearDinero(compra.monto_total)}</p>
                      <p className="text-xs text-slate-500">{compra.total_unidades} unidades</p>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={(evento) => {
                          evento.stopPropagation();
                          abrirTicket(compra.id_venta);
                        }}
                      >
                        Ver detalles del pedido
                      </button>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-sand pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Página {pagina} de {totalPaginas}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={cargando || pagina <= 1}
                onClick={() => cargarHistorial(pagina - 1, periodo)}
              >
                Anterior
              </button>
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={cargando || pagina >= totalPaginas}
                onClick={() => cargarHistorial(pagina + 1, periodo)}
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>

        <aside className="space-y-6">
          <section className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">Ticket de venta</h4>
            {ticketSeleccionado ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Pedido n.º</p>
                  <p className="mt-1 font-semibold text-ink">{ticketSeleccionado.id_venta}</p>
                </div>
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Fecha</p>
                  <p className="mt-1 text-sm text-ink">{ticketSeleccionado.fecha_venta}</p>
                </div>
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Monto pagado</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{formatearDinero(ticketSeleccionado.monto_total)}</p>
                </div>
                <div className="space-y-2">
                  {ticketSeleccionado.items.map((elemento) => (
                    <div key={`${elemento.id_producto}-${elemento.nombre}`} className="rounded-2xl border border-sand bg-white/70 p-4 text-sm">
                      <p className="truncate font-semibold text-ink">{truncarTexto(elemento.nombre, 64)}</p>
                      <p className="mt-1 text-slate-600">{elemento.marca || "Sin marca"}</p>
                      <p className="mt-1 text-slate-600">
                        {elemento.cantidad} unidades · {formatearDinero(elemento.precio_unitario)} c/u
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Selecciona una compra para ver el ticket.</p>
            )}
          </section>
        </aside>
      </section>
    </ShellCliente>
  );
}
