import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import ClientShell from "../components/ClientShell.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PERIODS = [
  { value: "30d", label: "30 días" },
  { value: "3m", label: "3 meses" },
  { value: "6m", label: "6 meses" },
  { value: "1y", label: "1 año" },
  { value: "all", label: "Histórico" },
];

function formatMoney(value) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function ClientHistory() {
  const userId = localStorage.getItem("userId");
  const [period, setPeriod] = useState("30d");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(8);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [purchases, setPurchases] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadHistory = async (nextPage = page, nextPeriod = period) => {
    if (!userId) {
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_URL}/api/cliente/compras?id_cliente=${encodeURIComponent(userId)}&period=${nextPeriod}&page=${nextPage}&page_size=${pageSize}`
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo cargar el historial.");
      }
      setPurchases(Array.isArray(data.items) ? data.items : []);
      setTotalPages(Number(data.total_pages || 1));
      setTotalItems(Number(data.total_items || 0));
      setPage(Number(data.page || nextPage));
    } catch (error) {
      toast.error(error.message || "No se pudo cargar el historial.");
      setPurchases([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory(1, period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const openTicket = async (saleId) => {
    try {
      const response = await fetch(`${API_URL}/api/cliente/compras/${encodeURIComponent(saleId)}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo cargar el ticket.");
      }
      setSelectedTicket(data);
    } catch (error) {
      toast.error(error.message || "No se pudo cargar el ticket.");
    }
  };

  return (
    <ClientShell
      title="Historial de compras"
      subtitle="Consulta compras por rango de tiempo y abre cada registro para ver su ticket de venta completo."
    >
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <div className="glass-panel p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="tag">Historial</p>
              <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                Compras registradas
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                {totalItems} registros en el rango seleccionado.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {PERIODS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={period === option.value ? "primary-button" : "secondary-button"}
                  onClick={() => setPeriod(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {isLoading ? (
              <p className="text-sm text-slate-500">Cargando historial...</p>
            ) : purchases.length === 0 ? (
              <p className="text-sm text-slate-500">No hay compras para este rango de fechas.</p>
            ) : (
              purchases.map((purchase) => (
                <button
                  key={purchase.id_venta}
                  type="button"
                  onClick={() => openTicket(purchase.id_venta)}
                  className="w-full rounded-3xl border border-sand bg-white/70 p-4 text-left transition hover:bg-white"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-ink">{purchase.resumen || purchase.id_venta}</p>
                      <p className="mt-1 text-xs text-slate-500">{purchase.fecha_venta}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-ink">{formatMoney(purchase.monto_total)}</p>
                      <p className="text-xs text-slate-500">{purchase.total_unidades} unidades</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-sand pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Página {page} de {totalPages} · {pageSize} compras por vista
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={isLoading || page <= 1}
                onClick={() => loadHistory(page - 1, period)}
              >
                Anterior
              </button>
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={isLoading || page >= totalPages}
                onClick={() => loadHistory(page + 1, period)}
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>

        <aside className="space-y-6">
          <section className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">Ticket de venta</h4>
            {selectedTicket ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">ID venta</p>
                  <p className="mt-1 font-semibold text-ink">{selectedTicket.id_venta}</p>
                </div>
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Fecha</p>
                  <p className="mt-1 text-sm text-ink">{selectedTicket.fecha_venta}</p>
                </div>
                <div className="rounded-2xl border border-sand bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Monto pagado</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{formatMoney(selectedTicket.monto_total)}</p>
                </div>
                <div className="space-y-2">
                  {selectedTicket.items.map((item) => (
                    <div key={`${item.id_producto}-${item.nombre}`} className="rounded-2xl border border-sand bg-white/70 p-4 text-sm">
                      <p className="font-semibold text-ink">{item.nombre}</p>
                      <p className="mt-1 text-slate-600">{item.marca || "Sin marca"}</p>
                      <p className="mt-1 text-slate-600">
                        {item.cantidad} unidades · {formatMoney(item.precio_unitario)} c/u
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
    </ClientShell>
  );
}
