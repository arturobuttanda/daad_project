import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import ShellCliente from "../components/ShellCliente.jsx";
import { agregar_item_carrito_cliente } from "../utils/clientCart.js";

const URL_API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatearDinero(valor) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(valor || 0));
}

export default function DetalleProductoCliente() {
  const { productId } = useParams();
  const navegar = useNavigate();
  const idUsuario = localStorage.getItem("userId");
  const [detalle, setDetalle] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [pestanaActiva, setPestanaActiva] = useState("recommendation");
  const [cantidad, setCantidad] = useState(1);
  const [comprando, setComprando] = useState(false);
  const [ticket, setTicket] = useState(null);

  const cargarDetalle = async () => {
    setCargando(true);
    try {
      const respuesta = await fetch(`${URL_API}/api/cliente/productos/${encodeURIComponent(productId)}`);
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo obtener el producto.");
      }
      setDetalle(datos);
    } catch (error) {
      toast.error(error.message || "No se pudo obtener el producto.");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarDetalle();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const producto = detalle?.product;
  const recomendacion = detalle?.recommendation;
  const historialPrecios = detalle?.price_history || [];
  const productosSimilares = recomendacion?.similar_products || [];

  const mensajeHistorial = useMemo(() => recomendacion?.signal || "", [recomendacion]);

  const manejar_agregar_carrito = () => {
    if (!producto) {
      return;
    }
    agregar_item_carrito_cliente(idUsuario, producto, cantidad);
    toast.success("Producto agregado al carrito.");
  };

  const manejar_compra = async () => {
    if (!idUsuario || !producto) {
      return;
    }
    setComprando(true);
    try {
      const respuesta = await fetch(`${URL_API}/api/cliente/compras`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id_cliente: idUsuario,
          items: [
            {
              id_producto: producto.id_producto,
              cantidad: cantidad,
            },
          ],
        }),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo completar la compra.");
      }
      setTicket(datos);
      toast.success("Compra registrada correctamente.");
    } catch (error) {
      toast.error(error.message || "No se pudo completar la compra.");
    } finally {
      setComprando(false);
    }
  };

  return (
    <ShellCliente
      title={producto?.nombre || "Detalle del producto"}
      subtitle="Revisa el comportamiento de precio, la recomendación de compra y la estimación de cuándo conviene comprar."
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <section className="glass-panel p-6">
          {cargando ? (
            <p className="text-sm text-slate-500">Cargando producto...</p>
          ) : producto ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="tag">Producto disponible</p>
                  <h3 className="mt-3 font-display text-3xl font-semibold text-ink">
                    {producto.nombre}
                  </h3>
                  <p className="mt-2 text-sm text-slate-600">
                    {producto.marca || "Marca no indicada"} · {producto.categoria || "Sin categoria"}
                  </p>
                </div>
                <div className="rounded-3xl border border-sand bg-white/70 px-5 py-4 text-right">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Precio actual</p>
                  <p className="mt-2 font-display text-3xl font-semibold text-ink">
                    {formatearDinero(producto.precio_actual)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Stock disponible: {producto.stock ?? 0}</p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                <button
                  type="button"
                  className={pestanaActiva === "history" ? "primary-button" : "secondary-button"}
                  onClick={() => setPestanaActiva("history")}
                >
                  Ver historial de precio
                </button>
                <button
                  type="button"
                  className={pestanaActiva === "recommendation" ? "primary-button" : "secondary-button"}
                  onClick={() => setPestanaActiva("recommendation")}
                >
                  Recomendación de compra
                </button>
                <button
                  type="button"
                  className={pestanaActiva === "prediction" ? "primary-button" : "secondary-button"}
                  onClick={() => setPestanaActiva("prediction")}
                >
                  Calcular fecha tentativa de compra
                </button>
              </div>

              <div className="mt-6 rounded-3xl border border-sand bg-white/70 p-5">
                {pestanaActiva === "history" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Historial del producto</h4>
                    <div className="mt-4 space-y-3">
                      {historialPrecios.length === 0 ? (
                        <p className="text-sm text-slate-500">No hay historial de precio disponible.</p>
                      ) : (
                        historialPrecios.map((entrada) => (
                          <div key={`${entrada.fecha}-${entrada.precio}`} className="flex items-center justify-between rounded-2xl border border-sand bg-white px-4 py-3 text-sm">
                            <span className="text-slate-600">{entrada.fecha}</span>
                            <span className="font-semibold text-ink">{formatearDinero(entrada.precio)}</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                ) : null}

                {pestanaActiva === "recommendation" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Recomendación de compra</h4>
                    <p className="mt-3 text-sm text-slate-600">{mensajeHistorial}</p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Señal</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recomendacion?.signal || "Sin señal"}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Precio sugerido</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{formatearDinero(recomendacion?.suggested_price)}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Margen</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recomendacion?.margin_percent ?? 0}%</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Competencia</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{formatearDinero(recomendacion?.competition_average)}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Mercado similar</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{formatearDinero(recomendacion?.market_reference_price)}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Comprar ahora</p>
                        <p className="mt-2 text-sm font-semibold text-ink">
                          {recomendacion?.buy_now ? "Sí, conviene" : "No, mejor esperar"}
                        </p>
                      </div>
                    </div>
                    <p className="mt-4 text-sm text-slate-600">{recomendacion?.reason}</p>
                    <p className="mt-2 text-sm text-slate-600">{recomendacion?.buy_reason}</p>
                    {productosSimilares.length > 0 ? (
                      <div className="mt-5 rounded-3xl border border-sand bg-white/70 p-5">
                        <h5 className="font-display text-lg font-semibold text-ink">Productos similares detectados</h5>
                        <div className="mt-4 space-y-3">
                          {productosSimilares.slice(0, 4).map((elemento) => (
                            <div key={elemento.id_producto} className="rounded-2xl border border-sand bg-white px-4 py-3 text-sm">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="font-semibold text-ink">{elemento.nombre || elemento.id_producto}</p>
                                  <p className="text-xs text-slate-500">{elemento.marca || "Sin marca"} · {elemento.categoria || "Sin categoria"}</p>
                                </div>
                                <div className="text-right">
                                  <p className="font-semibold text-ink">{formatearDinero(elemento.precio_actual)}</p>
                                  <p className="text-xs text-slate-500">{(Number(elemento.similarity_score || 0) * 100).toFixed(1)}% similitud</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {pestanaActiva === "prediction" ? (
                  <div>
                    <h4 className="font-display text-xl font-semibold text-ink">Fecha tentativa de compra</h4>
                    <p className="mt-3 text-sm text-slate-600">
                      {recomendacion?.estimated_buy_date
                        ? `Se estima que el mejor momento de compra sea alrededor del ${recomendacion.estimated_buy_date}.`
                        : "No hay suficiente tendencia para estimar una fecha confiable."}
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Tendencia</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recomendacion?.trend_label || "Sin tendencia"}</p>
                      </div>
                      <div className="rounded-2xl border border-sand bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Puntaje vectorial</p>
                        <p className="mt-2 text-sm font-semibold text-ink">{recomendacion?.vector_score ?? 0}</p>
                      </div>
                    </div>
                    <button type="button" className="secondary-button mt-4" onClick={cargarDetalle}>
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
                value={cantidad}
                onChange={(evento) => setCantidad(Math.max(1, Number(evento.target.value || 1)))}
                className="input-field mt-2"
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" className="primary-button" onClick={manejar_compra} disabled={comprando}>
                {comprando ? "Comprando..." : "Comprar ahora"}
              </button>
              <button type="button" className="secondary-button" onClick={manejar_agregar_carrito}>
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
              <p className="mt-1 text-sm text-slate-600">Monto pagado: {formatearDinero(ticket.monto_total)}</p>
              <Link to="/cliente/historial" className="mt-4 inline-flex text-sm font-semibold text-ocean">
                Ver historial de compras
              </Link>
            </section>
          ) : null}
        </aside>
      </div>
    </ShellCliente>
  );
}
