import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import ClientShell from "../components/ClientShell.jsx";
import { addClientCartItem, clearClientCart, getClientCart, updateClientCartItem } from "../utils/clientCart.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PAGE_SIZE = 12;

function formatMoney(value) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function ClientDashboard() {
  const userId = localStorage.getItem("userId");
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [search, setSearch] = useState("");
  const [cartItems, setCartItems] = useState(() => getClientCart(userId));
  const [recentPurchases, setRecentPurchases] = useState([]);
  const [ticket, setTicket] = useState(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  const loadProducts = async (nextPage = page, nextSearch = search) => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(PAGE_SIZE),
      });
      if (nextSearch.trim()) {
        params.set("search", nextSearch.trim());
      }
      const response = await fetch(`${API_URL}/api/cliente/productos?${params.toString()}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudieron obtener los productos.");
      }
      setProducts(Array.isArray(data.items) ? data.items : []);
      setPage(Number(data.page || nextPage));
      setTotalPages(Number(data.total_pages || 1));
      setTotalItems(Number(data.total_items || 0));
    } catch (error) {
      toast.error(error.message || "No se pudieron obtener los productos.");
    } finally {
      setIsLoading(false);
    }
  };

  const loadRecentPurchases = async () => {
    if (!userId) {
      return;
    }
    try {
      const response = await fetch(
        `${API_URL}/api/cliente/compras?id_cliente=${encodeURIComponent(userId)}&period=30d&page=1&page_size=4`
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo cargar el historial.");
      }
      setRecentPurchases(Array.isArray(data.items) ? data.items : []);
    } catch {
      setRecentPurchases([]);
    }
  };

  useEffect(() => {
    loadProducts(1, search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadRecentPurchases();
  }, [userId]);

  useEffect(() => {
    setCartItems(getClientCart(userId));
  }, [userId, ticket]);

  const cartSummary = useMemo(() => {
    const items = cartItems.reduce((accumulator, item) => accumulator + item.quantity, 0);
    const total = cartItems.reduce(
      (accumulator, item) => accumulator + Number(item.precio_actual || 0) * item.quantity,
      0
    );
    return { items, total };
  }, [cartItems]);

  const handleAddToCart = (product) => {
    const nextCart = addClientCartItem(userId, product, 1);
    setCartItems(nextCart);
    toast.success(`${product.nombre} agregado al carrito.`);
  };

  const handleQuantityChange = (productId, nextQuantity) => {
    const nextCart = updateClientCartItem(userId, productId, nextQuantity);
    setCartItems(nextCart);
  };

  const handleCheckout = async () => {
    if (!cartItems.length || !userId) {
      return;
    }
    setIsCheckingOut(true);
    try {
      const response = await fetch(`${API_URL}/api/cliente/compras`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id_cliente: userId,
          items: cartItems.map((item) => ({
            id_producto: item.id_producto,
            cantidad: item.quantity,
          })),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo completar la compra.");
      }
      setTicket(data);
      clearClientCart(userId);
      setCartItems([]);
      await loadProducts(page, search);
      await loadRecentPurchases();
      toast.success("Compra registrada correctamente.");
    } catch (error) {
      toast.error(error.message || "No se pudo completar la compra.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <ClientShell
      title="Catálogo disponible"
      subtitle="Explora los productos, revisa stock y agrega artículos al carrito. Desde aquí también puedes consultar tu historial de compras."
    >
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className="space-y-6">
          <div className="glass-panel p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="tag">Productos disponibles</p>
                <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                  Lista general del inventario
                </h3>
                <p className="mt-2 text-sm text-slate-600">
                  {totalItems} productos listados con stock disponible.
                </p>
              </div>
              <div className="flex gap-3">
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar producto o marca"
                  className="input-field min-w-[240px]"
                />
                <button type="button" className="secondary-button" onClick={() => loadProducts(1, search)}>
                  Buscar
                </button>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {products.map((product) => (
              <article key={product.id_producto} className="glass-panel lift-card p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h4 className="break-words font-display text-lg font-semibold text-ink">
                      {product.nombre}
                    </h4>
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                      {product.marca || "Marca no indicada"}
                    </p>
                  </div>
                  <span className="rounded-full bg-[rgba(26,127,143,0.12)] px-3 py-1 text-xs font-semibold text-ocean">
                    Stock {product.stock ?? 0}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-600">
                  {product.categoria || "Sin categoria"}
                </p>
                <div className="mt-4 space-y-2 text-sm text-slate-600">
                  <p>Precio actual: <span className="font-semibold text-ink">{formatMoney(product.precio_actual)}</span></p>
                  <p>Vendedor: <span className="font-semibold text-ink">{product.vendedor_nombre || "Asignación pendiente"}</span></p>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    to={`/cliente/producto/${product.id_producto}`}
                    className="primary-button"
                  >
                    Ver producto
                  </Link>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => handleAddToCart(product)}
                  >
                    Añadir al carrito
                  </button>
                </div>
              </article>
            ))}
          </div>

          <div className="flex flex-col gap-3 border-t border-sand pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Página {page} de {totalPages} · {PAGE_SIZE} productos por vista
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={isLoading || page <= 1}
                onClick={() => loadProducts(page - 1, search)}
              >
                Anterior
              </button>
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={isLoading || page >= totalPages}
                onClick={() => loadProducts(page + 1, search)}
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <section className="glass-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-lg font-semibold text-ink">Carrito</h4>
                <p className="mt-1 text-sm text-slate-600">{cartSummary.items} artículos seleccionados</p>
              </div>
              <span className="text-sm font-semibold text-ink">{formatMoney(cartSummary.total)}</span>
            </div>
            <div className="mt-4 space-y-3">
              {cartItems.length === 0 ? (
                <p className="text-sm text-slate-500">No tienes productos agregados todavía.</p>
              ) : (
                cartItems.map((item) => (
                  <div key={item.id_producto} className="rounded-2xl border border-sand bg-white/70 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-ink">{item.nombre}</p>
                        <p className="text-xs text-slate-500">{item.marca || "Sin marca"}</p>
                      </div>
                      <p className="text-sm font-semibold text-ink">{formatMoney(Number(item.precio_actual || 0) * item.quantity)}</p>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        className="secondary-button px-3 py-2 text-xs"
                        onClick={() => handleQuantityChange(item.id_producto, item.quantity - 1)}
                      >
                        -
                      </button>
                      <span className="min-w-10 text-center text-sm font-semibold text-ink">{item.quantity}</span>
                      <button
                        type="button"
                        className="secondary-button px-3 py-2 text-xs"
                        onClick={() => handleQuantityChange(item.id_producto, item.quantity + 1)}
                      >
                        +
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
            <button
              type="button"
              className="primary-button mt-4 w-full disabled:opacity-50"
              disabled={!cartItems.length || isCheckingOut}
              onClick={handleCheckout}
            >
              {isCheckingOut ? "Procesando compra..." : "Comprar carrito"}
            </button>
          </section>

          <section className="glass-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-lg font-semibold text-ink">Últimas compras</h4>
                <p className="mt-1 text-sm text-slate-600">Historial de los últimos 30 días.</p>
              </div>
              <Link to="/cliente/historial" className="text-sm font-semibold text-ocean">
                Ver historial
              </Link>
            </div>
            <div className="mt-4 space-y-3">
              {recentPurchases.length === 0 ? (
                <p className="text-sm text-slate-500">Aún no hay compras recientes.</p>
              ) : (
                recentPurchases.map((purchase) => (
                  <div key={purchase.id_venta} className="rounded-2xl border border-sand bg-white/70 p-4">
                    <p className="text-sm font-semibold text-ink">{purchase.resumen || purchase.id_venta}</p>
                    <p className="mt-1 text-xs text-slate-500">{purchase.fecha_venta}</p>
                    <p className="mt-1 text-sm text-slate-600">
                      {purchase.total_unidades} unidades · {formatMoney(purchase.monto_total)}
                    </p>
                  </div>
                ))
              )}
            </div>
          </section>

          {ticket ? (
            <section className="glass-panel p-5">
              <h4 className="font-display text-lg font-semibold text-ink">Ticket reciente</h4>
              <p className="mt-1 text-sm text-slate-600">{ticket.id_venta}</p>
              <p className="mt-2 text-sm text-slate-600">Fecha: {ticket.fecha_venta}</p>
              <p className="mt-1 text-sm text-slate-600">Total: {formatMoney(ticket.monto_total)}</p>
            </section>
          ) : null}
        </div>
      </section>
    </ClientShell>
  );
}
