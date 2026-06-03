import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import ClientShell from "../components/ClientShell.jsx";
import { addNotification } from "../utils/notificationEvents.js";

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

function truncateText(value, maxLength = 48) {
  const cleanValue = String(value || "").trim();
  if (!cleanValue) {
    return "Producto";
  }
  if (cleanValue.length <= maxLength) {
    return cleanValue;
  }
  return `${cleanValue.slice(0, maxLength - 3)}...`;
}

function buildProductPreview(products = [], maxVisible = 3) {
  const visibleProducts = Array.isArray(products) ? products.slice(0, maxVisible) : [];
  return visibleProducts.map((item) => `${truncateText(item.nombre, 42)} x${item.cantidad}`).join(" · ");
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
      addNotification({
        kind: "history",
        title: "Ticket abierto",
        detail: `Se abrió el detalle del pedido ${saleId}.`,
        source: "Historial",
      });
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
                  className="w-full rounded-3xl border border-sand bg-white p-5 text-left transition hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_12px_30px_rgba(11,27,43,0.06)]"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                            Pedido n.º {purchase.numero_pedido || purchase.id_venta}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">{purchase.fecha_venta}</p>
                        </div>
                        <span className="rounded-full bg-[#EAF2FF] px-3 py-1 text-xs font-semibold text-ocean">
                          Compra registrada
                        </span>
                      </div>

                      <div className="mt-4 space-y-3">
                        {Array.isArray(purchase.productos) && purchase.productos.length > 0 ? (
                          purchase.productos.slice(0, 3).map((item) => (
                            <div key={`${purchase.id_venta}-${item.id_producto}`} className="flex items-start gap-3">
                              <span className="mt-2 h-2 w-2 flex-none rounded-full bg-ocean" />
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-ink">{truncateText(item.nombre, 72)}</p>
                                <p className="text-xs text-slate-500">{item.cantidad} unidades</p>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-slate-500">{truncateText(purchase.resumen || purchase.id_venta, 72)}</p>
                        )}
                        {Array.isArray(purchase.productos) && purchase.productos.length > 3 ? (
                          <p className="text-xs text-slate-500">
                            +{purchase.productos.length - 3} productos más
                          </p>
                        ) : null}
                        {purchase.resumen ? (
                          <p className="text-xs text-slate-500">{truncateText(purchase.resumen, 96)}</p>
                        ) : null}
                        <p className="text-xs text-slate-500">{buildProductPreview(purchase.productos)}</p>
                      </div>
                    </div>

                    <div className="flex flex-col items-start gap-3 lg:items-end">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Total</p>
                      <p className="text-2xl font-semibold text-ink">{formatMoney(purchase.monto_total)}</p>
                      <p className="text-xs text-slate-500">{purchase.total_unidades} unidades</p>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={(event) => {
                          event.stopPropagation();
                          openTicket(purchase.id_venta);
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
                  <p className="text-xs uppercase tracking-wide text-slate-500">Pedido n.º</p>
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
                      <p className="truncate font-semibold text-ink">{truncateText(item.nombre, 64)}</p>
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
