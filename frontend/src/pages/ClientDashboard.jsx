import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import DashboardChartPanel from "../components/DashboardChartPanel.jsx";
import ClientShell from "../components/ClientShell.jsx";
import { addClientCartItem, clearClientCart, getClientCart, updateClientCartItem } from "../utils/clientCart.js";
import { addNotification } from "../utils/notificationEvents.js";

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
  const navigate = useNavigate();
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
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [minPriceFilter, setMinPriceFilter] = useState(0);
  const [maxPriceFilter, setMaxPriceFilter] = useState(0);

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

  const maxCatalogPrice = useMemo(() => {
    if (!products.length) {
      return 0;
    }
    return Math.max(...products.map((product) => Number(product.precio_actual || 0)));
  }, [products]);

  useEffect(() => {
    setMinPriceFilter(0);
    setMaxPriceFilter(maxCatalogPrice);
  }, [maxCatalogPrice]);

  const categoryOptions = useMemo(() => {
    const categories = new Set();
    for (const product of products) {
      const categoryName = String(product.categoria || "").trim();
      if (categoryName) {
        categories.add(categoryName);
      }
    }
    return ["all", ...Array.from(categories).sort((a, b) => a.localeCompare(b))];
  }, [products]);

  const sliderMax = Math.max(1, Math.ceil(maxCatalogPrice));
  const selectedMin = Math.min(minPriceFilter, maxPriceFilter);
  const selectedMax = Math.max(minPriceFilter, maxPriceFilter);
  const rangeStart = (selectedMin / sliderMax) * 100;
  const rangeEnd = (selectedMax / sliderMax) * 100;

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const price = Number(product.precio_actual || 0);
      const categoryName = String(product.categoria || "").trim();
      const matchesCategory = categoryFilter === "all" || categoryName === categoryFilter;
      const matchesPrice = price >= selectedMin && price <= selectedMax;
      return matchesCategory && matchesPrice;
    });
  }, [products, categoryFilter, selectedMin, selectedMax]);

  const chartOptions = useMemo(() => {
    const categoryCounts = new Map();
    const priceBuckets = [
      { label: "0-49", value: 0 },
      { label: "50-149", value: 0 },
      { label: "150-299", value: 0 },
      { label: "300+", value: 0 },
    ];

    for (const product of products) {
      const categoryName = String(product.categoria || "Sin categoria").trim() || "Sin categoria";
      categoryCounts.set(categoryName, (categoryCounts.get(categoryName) || 0) + 1);

      const price = Number(product.precio_actual || 0);
      if (price < 50) {
        priceBuckets[0].value += 1;
      } else if (price < 150) {
        priceBuckets[1].value += 1;
      } else if (price < 300) {
        priceBuckets[2].value += 1;
      } else {
        priceBuckets[3].value += 1;
      }
    }

    const recentTrend = recentPurchases.length
      ? recentPurchases.map((purchase) => Number(purchase.monto_total || 0))
      : [0, 0, 0, 0];

    return [
      {
        key: "catalog-bars",
        label: "Grafico de barras del catalogo",
        kind: "bar",
        description: "Muestra cuantas referencias hay por categoria. Es util para ver que familias dominan la tienda.",
        labels: Array.from(categoryCounts.entries()).slice(0, 6).map(([category]) => category),
        values: Array.from(categoryCounts.entries()).slice(0, 6).map(([, count]) => count),
        unitLabel: "productos",
        insights: [
          "Sirve para comparar variedad de categorias.",
          "Ayuda a detectar si el catalogo esta muy concentrado en pocas familias.",
        ],
      },
      {
        key: "price-histogram",
        label: "Histograma de precios",
        kind: "histogram",
        description: "Agrupa los productos por rangos de precio para ver si el catalogo esta orientado a bajo, medio o alto costo.",
        labels: priceBuckets.map((bucket) => bucket.label),
        values: priceBuckets.map((bucket) => bucket.value),
        insights: [
          "Es util para comparar accesibilidad del catalogo.",
          "Permite ver si predominan productos economicos o premium.",
        ],
      },
      {
        key: "purchase-line",
        label: "Grafico de lineas de compras recientes",
        kind: "line",
        description: "Resume tus compras mas recientes para visualizar el ritmo del gasto o del consumo.",
        labels: recentPurchases.length
          ? recentPurchases.map((purchase, index) => `#${index + 1}`)
          : ["1", "2", "3", "4"],
        values: recentTrend,
        unitLabel: "MXN",
        insights: [
          "Sirve para comparar tus compras recientes sin abrir el historial completo.",
          "Ayuda a detectar si tus tickets estan creciendo o bajando.",
        ],
      },
      {
        key: "cart-share",
        label: "Grafico de dona del carrito",
        kind: "donut",
        description: "Muestra la composicion del carrito entre articulos de bajo, medio y alto precio.",
        slices: [
          { label: "Bajo precio", value: cartItems.filter((item) => Number(item.precio_actual || 0) < 50).length, color: "#5CC49D" },
          { label: "Precio medio", value: cartItems.filter((item) => Number(item.precio_actual || 0) >= 50 && Number(item.precio_actual || 0) < 300).length, color: "#3C9BE8" },
          { label: "Precio alto", value: cartItems.filter((item) => Number(item.precio_actual || 0) >= 300).length, color: "#F26B5B" },
        ],
        insights: [
          "Resume la mezcla del carrito en una sola vista.",
          "Es practica para revisar si compras sobre todo productos baratos o de ticket alto.",
        ],
      },
    ];
  }, [cartItems, products, recentPurchases]);

  const truncateName = (value, maxLength = 28) => {
    const cleanValue = String(value || "").trim();
    if (!cleanValue) {
      return "Producto";
    }
    if (cleanValue.length <= maxLength) {
      return cleanValue;
    }
    return `${cleanValue.slice(0, maxLength - 3)}...`;
  };

  const handleAddToCart = (product) => {
    const nextCart = addClientCartItem(userId, product, 1);
    setCartItems(nextCart);
    toast.success(`${product.nombre} agregado al carrito.`);
    addNotification({
      kind: "cart",
      title: "Producto agregado al carrito",
      detail: `${product.nombre} se sumó al carrito del cliente.`,
      source: "Marketplace",
    });
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
      addNotification({
        kind: "purchase",
        title: "Compra completada",
        detail: `Se registró una compra con ${cartItems.length} productos.`,
        source: "Marketplace",
      });
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
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
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

          <DashboardChartPanel
            title="Explora el comportamiento del cliente con graficos"
            description="Elige la vista que te convenga: barras para categorias, histograma para precios, lineas para compras recientes o dona para el carrito."
            options={chartOptions}
            defaultKey="catalog-bars"
          />

          <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="glass-panel h-fit p-5">
              <h4 className="font-display text-lg font-semibold text-ink">Filtros</h4>
              <div className="mt-4 space-y-5">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Filtrar por categoría
                  </label>
                  <select
                    className="input-field mt-2"
                    value={categoryFilter}
                    onChange={(event) => setCategoryFilter(event.target.value)}
                  >
                    {categoryOptions.map((category) => (
                      <option key={category} value={category}>
                        {category === "all" ? "Todas" : category}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Rango de precio
                  </label>
                  <div className="mt-3 rounded-2xl border border-[#D6DEEE] bg-[#F8FAFF] p-4">
                    <div className="mt-2 flex items-center justify-between text-lg font-semibold text-ink">
                      <span>{Math.round(selectedMin)}</span>
                      <span>{Math.round(selectedMax)}</span>
                    </div>

                    <div className="relative mt-4 h-7">
                      <div className="absolute left-0 right-0 top-1/2 h-3 -translate-y-1/2 rounded-full border border-[#B8C3DA] bg-[#E5EAF7]" />
                      <div
                        className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,#7BC9FF_0%,#3C9BE8_55%,#1E4BB8_100%)]"
                        style={{
                          left: `${rangeStart}%`,
                          width: `${Math.max(0, rangeEnd - rangeStart)}%`,
                        }}
                      />

                      <input
                        type="range"
                        min="0"
                        max={sliderMax}
                        step="1"
                        value={selectedMin}
                        onChange={(event) => {
                          const nextMin = Number(event.target.value);
                          setMinPriceFilter(Math.min(nextMin, selectedMax));
                        }}
                        className="absolute left -1 top-1/4 z-40 w-full -translate-y-1/4 appearance-none bg-transparent [&::-webkit-slider-runnable-track]:h-0 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-[#B5BDCF] [&::-webkit-slider-thumb]:bg-[#ECEFF7] [&::-webkit-slider-thumb]:shadow-[0_2px_0_#9AA3B7]"
                      />

                      <input
                        type="range"
                        min="0"
                        max={sliderMax}
                        step="1"
                        value={selectedMax}
                        onChange={(event) => {
                          const nextMax = Number(event.target.value);
                          setMaxPriceFilter(Math.max(nextMax, selectedMin));
                        }}
                        className="absolute left-1 top-1/4 z-40 w-full -translate-y-1/4 appearance-none bg-transparent [&::-webkit-slider-runnable-track]:h-0 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-[#B5BDCF] [&::-webkit-slider-thumb]:bg-[#ECEFF7] [&::-webkit-slider-thumb]:shadow-[0_2px_0_#9AA3B7]"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <div className="grid gap-4 md:grid-cols-2">
              {filteredProducts.map((product) => (
                <article
                  key={product.id_producto}
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/cliente/producto/${product.id_producto}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      navigate(`/cliente/producto/${product.id_producto}`);
                    }
                  }}
                  className="glass-panel group relative cursor-pointer overflow-hidden p-5 transition duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="rounded-full bg-[#EEF2FF] px-3 py-1 text-xs font-semibold text-ocean">
                      {product.categoria || "Sin categoria"}
                    </span>
                    <span className="rounded-full bg-[rgba(26,127,143,0.12)] px-3 py-1 text-xs font-semibold text-ocean">
                      Stock {product.stock ?? 0}
                    </span>
                  </div>

                  <h4 className="mt-3 h-7 overflow-hidden text-ellipsis whitespace-nowrap font-display text-lg font-semibold text-ink">
                    {truncateName(product.nombre)}
                  </h4>

                  <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                    {product.marca || "Marca no indicada"}
                  </p>

                  <div className="mt-4">
                    <p className="font-display text-3xl font-semibold text-ocean">
                      {formatMoney(product.precio_actual)}
                    </p>
                  </div>

                  <div className="pointer-events-none absolute inset-x-4 bottom-4 translate-y-3 opacity-0 transition-all duration-150 group-hover:translate-y-0 group-hover:opacity-100">
                    <button
                      type="button"
                      className="primary-button pointer-events-auto w-full"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleAddToCart(product);
                      }}
                    >
                      Añadir al carrito
                    </button>
                </div>
              </article>
            ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-sand pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Página {page} de {totalPages} · {filteredProducts.length} productos visibles
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
