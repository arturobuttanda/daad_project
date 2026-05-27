import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import ClientShell from "../components/ClientShell.jsx";
import { addClientCartItem } from "../utils/clientCart.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatMoney(value) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function ClientProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const userId = localStorage.getItem("userId");
  const [detail, setDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("recommendation");
  const [quantity, setQuantity] = useState(1);
  const [isPurchasing, setIsPurchasing] = useState(false);
  const [ticket, setTicket] = useState(null);

  const loadDetail = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/cliente/productos/${encodeURIComponent(productId)}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo obtener el producto.");
      }
      setDetail(data);
    } catch (error) {
      toast.error(error.message || "No se pudo obtener el producto.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const product = detail?.product;
  const recommendation = detail?.recommendation;
  const priceHistory = detail?.price_history || [];

  const historyMessage = useMemo(() => recommendation?.signal || "", [recommendation]);

  const handleAddToCart = () => {
    if (!product) {
      return;
    }
    addClientCartItem(userId, product, quantity);
    toast.success("Producto agregado al carrito.");
  };

  const handlePurchase = async () => {
    if (!userId || !product) {
      return;
    }
    setIsPurchasing(true);
    try {
      const response = await fetch(`${API_URL}/api/cliente/compras`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id_cliente: userId,
          items: [
            {
              id_producto: product.id_producto,
              cantidad: quantity,
            },
          ],
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo completar la compra.");
      }
      setTicket(data);
      toast.success("Compra registrada correctamente.");
    } catch (error) {
      toast.error(error.message || "No se pudo completar la compra.");
    } finally {
      setIsPurchasing(false);
    }
  };

  return (
    <ClientShell
      title={product?.nombre || "Detalle del producto"}
      subtitle="Revisa el comportamiento de precio, la recomendación de compra y la estimación de cuándo conviene comprar."
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <section className="glass-panel p-6">
          {isLoading ? (
            <p className="text-sm text-slate-500">Cargando producto...</p>
          ) : product ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="tag">Producto disponible</p>
                  <h3 className="mt-3 font-display text-3xl font-semibold text-ink">
                    {product.nombre}
                  </h3>
                  <p className="mt-2 text-sm text-slate-600">
                    {product.marca || "Marca no indicada"} · {product.categoria || "Sin categoria"}
                  </p>
                </div>
                <div className="rounded-3xl border border-sand bg-white/70 px-5 py-4 text-right">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Precio actual</p>
                  <p className="mt-2 font-display text-3xl font-semibold text-ink">
                    {formatMoney(product.precio_actual)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Stock disponible: {product.stock ?? 0}</p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                <button
                  type="button"
                  className={activeTab === "history" ? "primary-button" : "secondary-button"}
                  onClick={() => setActiveTab("history")}
                >
                  Ver historial de precio
                </button>
                <button
                  type="button"
                  className={activeTab === "recommendation" ? "primary-button" : "secondary-button"}
                  onClick={() => setActiveTab("recommendation")}
                >
                  Recomendación de compra
                </button>
                <button
                  type="button"
                  className={activeTab === "prediction" ? "primary-button" : "secondary-button"}
                  onClick={() => setActiveTab("prediction")}
                >
                  Calcular fecha tentativa de compra
                </button>
              </div>

              <div className="mt-6 rounded-3xl border border-sand bg-white/70 p-5">
                {activeTab === "history" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Historial del producto</h4>
                    <div className="mt-4 space-y-3">
                      {priceHistory.length === 0 ? (
                        <p className="text-sm text-slate-500">No hay historial de precio disponible.</p>
                      ) : (
                        priceHistory.map((entry) => (
                          <div key={`${entry.fecha}-${entry.precio}`} className="flex items-center justify-between rounded-2xl border border-sand bg-white px-4 py-3 text-sm">
                            <span className="text-slate-600">{entry.fecha}</span>
                            <span className="font-semibold text-ink">{formatMoney(entry.precio)}</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                ) : null}

                {activeTab === "recommendation" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Recomendación de compra</h4>
                    <p className="mt-3 text-sm text-slate-600">{historyMessage}</p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Señal</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recommendation?.signal || "Sin señal"}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Precio sugerido</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{formatMoney(recommendation?.suggested_price)}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Margen</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recommendation?.margin_percent ?? 0}%</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Competencia</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{formatMoney(recommendation?.competition_average)}</p>
                      </div>
                    </div>
                    <p className="mt-4 text-sm text-slate-600">{recommendation?.reason}</p>
                  </div>
                ) : null}

                {activeTab === "prediction" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Fecha tentativa de compra</h4>
                    <p className="mt-3 text-sm text-slate-600">
                      {recommendation?.estimated_buy_date
                        ? `Se estima que el mejor momento de compra sea alrededor del ${recommendation.estimated_buy_date}.`
                        : "No hay suficiente tendencia para estimar una fecha confiable."}
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Tendencia</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recommendation?.trend_label || "Sin tendencia"}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Puntaje vectorial</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recommendation?.vector_score ?? 0}</p>
                      </div>
                    </div>
                    <button type="button" className="secondary-button mt-4" onClick={loadDetail}>
                      Calcular otra vez
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No se pudo cargar el producto.</p>
          )}
        </section>

        <aside className="space-y-6">
          <section className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">Comprar producto</h4>
            <p className="mt-2 text-sm text-slate-600">
              Selecciona la cantidad y agrega este producto al carrito o cómpralo de inmediato.
            </p>
            <div className="mt-4">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">Cantidad</label>
              <input
                type="number"
                min="1"
                value={quantity}
                onChange={(event) => setQuantity(Math.max(1, Number(event.target.value || 1)))}
                className="input-field mt-2"
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" className="primary-button" onClick={handlePurchase} disabled={isPurchasing}>
                {isPurchasing ? "Comprando..." : "Comprar ahora"}
              </button>
              <button type="button" className="secondary-button" onClick={handleAddToCart}>
                Agregar al carrito
              </button>
            </div>
          </section>

          <section className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">Vendedor asignado</h4>
            <p className="mt-2 text-sm text-slate-600">
              {detail?.vendor?.nombre_vendedor || "Este producto aún no tiene vendedor asignado."}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {detail?.vendor?.codigo_vendedor || "Sin codigo"}
            </p>
          </section>

          {ticket ? (
            <section className="glass-panel p-5">
              <h4 className="font-display text-lg font-semibold text-ink">Ticket generado</h4>
              <p className="mt-2 text-sm text-slate-600">ID venta: {ticket.id_venta}</p>
              <p className="mt-1 text-sm text-slate-600">Monto pagado: {formatMoney(ticket.monto_total)}</p>
              <Link to="/cliente/historial" className="mt-4 inline-flex text-sm font-semibold text-ocean">
                Ver historial de compras
              </Link>
            </section>
          ) : null}
        </aside>
      </div>
    </ClientShell>
  );
}
