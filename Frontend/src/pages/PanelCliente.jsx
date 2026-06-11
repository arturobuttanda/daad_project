import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import ShellCliente from "../components/ShellCliente.jsx";
import { agregar_item_carrito_cliente, vaciar_carrito_cliente, obtener_carrito_cliente, actualizar_item_carrito_cliente } from "../utils/clientCart.js";
import { agregar_notificacion } from "../utils/notificationEvents.js";

const URL_API = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
const TAMANO_PAGINA = 12;

function formatearDinero(valor) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number(valor || 0));
}

export default function PanelCliente() {
  const navegar = useNavigate();
  const idUsuario = localStorage.getItem("userId");
  const [productos, setProductos] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [totalPaginas, setTotalPaginas] = useState(1);
  const [totalElementos, setTotalElementos] = useState(0);
  const [busqueda, setBusqueda] = useState("");
  const [elementosCarrito, setElementosCarrito] = useState(() => obtener_carrito_cliente(idUsuario));
  const [comprasRecientes, setComprasRecientes] = useState([]);
  const [ticket, setTicket] = useState(null);
  const [procesandoCompra, setProcesandoCompra] = useState(false);
  const [filtroCategoria, setFiltroCategoria] = useState("all");
  const [filtroPrecioMin, setFiltroPrecioMin] = useState(0);
  const [filtroPrecioMax, setFiltroPrecioMax] = useState(0);

  const cargarProductos = async (siguientePagina = pagina, siguienteBusqueda = busqueda) => {
    setCargando(true);
    try {
      const parametros = new URLSearchParams({
        page: String(siguientePagina),
        page_size: String(TAMANO_PAGINA),
      });
      if (siguienteBusqueda.trim()) {
        parametros.set("search", siguienteBusqueda.trim());
      }
      const respuesta = await fetch(`${URL_API}/api/cliente/productos?${parametros.toString()}`);
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudieron obtener los productos.");
      }
      setProductos(Array.isArray(datos.items) ? datos.items : []);
      setPagina(Number(datos.page || siguientePagina));
      setTotalPaginas(Number(datos.total_pages || 1));
      setTotalElementos(Number(datos.total_items || 0));
    } catch (error) {
      toast.error(error.message || "No se pudieron obtener los productos.");
    } finally {
      setCargando(false);
    }
  };

  const cargarComprasRecientes = async () => {
    if (!idUsuario) {
      return;
    }
    try {
      const respuesta = await fetch(
        `${URL_API}/api/cliente/compras?id_cliente=${encodeURIComponent(idUsuario)}&period=30d&page=1&page_size=4`
      );
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo cargar el historial.");
      }
      setComprasRecientes(Array.isArray(datos.items) ? datos.items : []);
    } catch {
      setComprasRecientes([]);
    }
  };

  useEffect(() => {
    cargarProductos(1, busqueda);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    cargarComprasRecientes();
  }, [idUsuario]);

  useEffect(() => {
    setElementosCarrito(obtener_carrito_cliente(idUsuario));
  }, [idUsuario, ticket]);

  const resumenCarrito = useMemo(() => {
    const articulos = elementosCarrito.reduce((acum, elemento) => acum + elemento.quantity, 0);
    const total = elementosCarrito.reduce(
      (acum, elemento) => acum + Number(elemento.precio_actual || 0) * elemento.quantity,
      0
    );
    return { articulos, total };
  }, [elementosCarrito]);

  const precioMaximoCatalogo = useMemo(() => {
    if (!productos.length) {
      return 0;
    }
    return Math.max(...productos.map((producto) => Number(producto.precio_actual || 0)));
  }, [productos]);

  useEffect(() => {
    setFiltroPrecioMin(0);
    setFiltroPrecioMax(precioMaximoCatalogo);
  }, [precioMaximoCatalogo]);

  const opcionesCategorias = useMemo(() => {
    const categorias = new Set();
    for (const producto of productos) {
      const nombreCategoria = String(producto.categoria || "").trim();
      if (nombreCategoria) {
        categorias.add(nombreCategoria);
      }
    }
    return ["all", ...Array.from(categorias).sort((a, b) => a.localeCompare(b))];
  }, [productos]);

  const maxSlider = Math.max(1, Math.ceil(precioMaximoCatalogo));
  const minSeleccionado = Math.min(filtroPrecioMin, filtroPrecioMax);
  const maxSeleccionado = Math.max(filtroPrecioMin, filtroPrecioMax);
  const inicioRango = (minSeleccionado / maxSlider) * 100;
  const finRango = (maxSeleccionado / maxSlider) * 100;

  const productosFiltrados = useMemo(() => {
    return productos.filter((producto) => {
      const precio = Number(producto.precio_actual || 0);
      const nombreCategoria = String(producto.categoria || "").trim();
      const coincideCategoria = filtroCategoria === "all" || nombreCategoria === filtroCategoria;
      const coincidePrecio = precio >= minSeleccionado && precio <= maxSeleccionado;
      return coincideCategoria && coincidePrecio;
    });
  }, [productos, filtroCategoria, minSeleccionado, maxSeleccionado]);

  const truncarNombre = (valor, longitudMaxima = 28) => {
    const valorLimpio = String(valor || "").trim();
    if (!valorLimpio) {
      return "Producto";
    }
    if (valorLimpio.length <= longitudMaxima) {
      return valorLimpio;
    }
    return `${valorLimpio.slice(0, longitudMaxima - 3)}...`;
  };

  const manejar_agregar_carrito = (producto) => {
    const nuevoCarrito = agregar_item_carrito_cliente(idUsuario, producto, 1);
    setElementosCarrito(nuevoCarrito);
    toast.success(`${producto.nombre} agregado al carrito.`);
    agregar_notificacion({
      kind: "cart",
      title: "Producto agregado al carrito",
      detail: `${producto.nombre} se sumó al carrito del cliente.`,
      source: "Marketplace",
    });
  };

  const manejar_cambio_cantidad = (idProducto, siguienteCantidad) => {
    const nuevoCarrito = actualizar_item_carrito_cliente(idUsuario, idProducto, siguienteCantidad);
    setElementosCarrito(nuevoCarrito);
  };

  const manejar_pagar = async () => {
    if (!elementosCarrito.length || !idUsuario) {
      return;
    }
    setProcesandoCompra(true);
    try {
      const respuesta = await fetch(`${URL_API}/api/cliente/compras`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id_cliente: idUsuario,
          items: elementosCarrito.map((elemento) => ({
            id_producto: elemento.id_producto,
            cantidad: elemento.quantity,
          })),
        }),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo completar la compra.");
      }
      setTicket(datos);
      vaciar_carrito_cliente(idUsuario);
      setElementosCarrito([]);
      await cargarProductos(pagina, busqueda);
      await cargarComprasRecientes();
      toast.success("Compra registrada correctamente.");
      agregar_notificacion({
        kind: "purchase",
        title: "Compra completada",
        detail: `Se registró una compra con ${elementosCarrito.length} productos.`,
        source: "Marketplace",
      });
    } catch (error) {
      toast.error(error.message || "No se pudo completar la compra.");
    } finally {
      setProcesandoCompra(false);
    }
  };

  return (
    <ShellCliente
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
                  {totalElementos} productos listados con stock disponible.
                </p>
              </div>
              <div className="flex gap-3">
                <input
                  type="search"
                  value={busqueda}
                  onChange={(evento) => setBusqueda(evento.target.value)}
                  placeholder="Buscar producto o marca"
                  className="input-field min-w-[240px]"
                />
                <button type="button" className="secondary-button" onClick={() => cargarProductos(1, busqueda)}>
                  Buscar
                </button>
              </div>
            </div>
          </div>

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
                    value={filtroCategoria}
                    onChange={(evento) => setFiltroCategoria(evento.target.value)}
                  >
                    {opcionesCategorias.map((categoria) => (
                      <option key={categoria} value={categoria}>
                        {categoria === "all" ? "Todas" : categoria}
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
                      <span>{Math.round(minSeleccionado)}</span>
                      <span>{Math.round(maxSeleccionado)}</span>
                    </div>

                    <div className="relative mt-4 h-7">
                      <div className="absolute left-0 right-0 top-1/2 h-3 -translate-y-1/2 rounded-full border border-[#B8C3DA] bg-[#E5EAF7]" />
                      <div
                        className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,#7BC9FF_0%,#3C9BE8_55%,#1E4BB8_100%)]"
                        style={{
                          left: `${inicioRango}%`,
                          width: `${Math.max(0, finRango - inicioRango)}%`,
                        }}
                      />

                      <input
                        type="range"
                        min="0"
                        max={maxSlider}
                        step="1"
                        value={minSeleccionado}
                        onChange={(evento) => {
                          const siguienteMin = Number(evento.target.value);
                          setFiltroPrecioMin(Math.min(siguienteMin, maxSeleccionado));
                        }}
                        className="absolute left -1 top-1/4 z-40 w-full -translate-y-1/4 appearance-none bg-transparent [&::-webkit-slider-runnable-track]:h-0 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-[#B5BDCF] [&::-webkit-slider-thumb]:bg-[#ECEFF7] [&::-webkit-slider-thumb]:shadow-[0_2px_0_#9AA3B7]"
                      />

                      <input
                        type="range"
                        min="0"
                        max={maxSlider}
                        step="1"
                        value={maxSeleccionado}
                        onChange={(evento) => {
                          const siguienteMax = Number(evento.target.value);
                          setFiltroPrecioMax(Math.max(siguienteMax, minSeleccionado));
                        }}
                        className="absolute left-1 top-1/4 z-40 w-full -translate-y-1/4 appearance-none bg-transparent [&::-webkit-slider-runnable-track]:h-0 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-[#B5BDCF] [&::-webkit-slider-thumb]:bg-[#ECEFF7] [&::-webkit-slider-thumb]:shadow-[0_2px_0_#9AA3B7]"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <div className="grid gap-4 md:grid-cols-2">
              {productosFiltrados.map((producto) => (
                <article
                  key={producto.id_producto}
                  role="button"
                  tabIndex={0}
                  onClick={() => navegar(`/cliente/producto/${producto.id_producto}`)}
                  onKeyDown={(evento) => {
                    if (evento.key === "Enter" || evento.key === " ") {
                      evento.preventDefault();
                      navegar(`/cliente/producto/${producto.id_producto}`);
                    }
                  }}
                  className="glass-panel group relative cursor-pointer overflow-hidden p-5 transition duration-150 hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="rounded-full bg-[#EEF2FF] px-3 py-1 text-xs font-semibold text-ocean">
                      {producto.categoria || "Sin categoria"}
                    </span>
                    <span className="rounded-full bg-[rgba(26,127,143,0.12)] px-3 py-1 text-xs font-semibold text-ocean">
                      Stock {producto.stock ?? 0}
                    </span>
                  </div>

                  <h4 className="mt-3 h-7 overflow-hidden text-ellipsis whitespace-nowrap font-display text-lg font-semibold text-ink">
                    {truncarNombre(producto.nombre)}
                  </h4>

                  <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                    {producto.marca || "Marca no indicada"}
                  </p>

                  <div className="mt-4">
                    <p className="font-display text-3xl font-semibold text-ocean">
                      {formatearDinero(producto.precio_actual)}
                    </p>
                  </div>

                  <div className="pointer-events-none absolute inset-x-4 bottom-4 translate-y-3 opacity-0 transition-all duration-150 group-hover:translate-y-0 group-hover:opacity-100">
                    <button
                      type="button"
                      className="primary-button pointer-events-auto w-full"
                      onClick={(evento) => {
                        evento.stopPropagation();
                        manejar_agregar_carrito(producto);
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
              Página {pagina} de {totalPaginas}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={cargando || pagina <= 1}
                onClick={() => cargarProductos(pagina - 1, busqueda)}
              >
                Anterior
              </button>
              <button
                type="button"
                className="secondary-button disabled:opacity-50"
                disabled={cargando || pagina >= totalPaginas}
                onClick={() => cargarProductos(pagina + 1, busqueda)}
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
                <p className="mt-1 text-sm text-slate-600">{resumenCarrito.articulos} artículos seleccionados</p>
              </div>
              <span className="text-sm font-semibold text-ink">{formatearDinero(resumenCarrito.total)}</span>
            </div>
            <div className="mt-4 space-y-3">
              {elementosCarrito.length === 0 ? (
                <p className="text-sm text-slate-500">No tienes productos agregados todavía.</p>
              ) : (
                elementosCarrito.map((elemento) => (
                  <div key={elemento.id_producto} className="rounded-2xl border border-sand bg-white/70 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-ink">{elemento.nombre}</p>
                        <p className="text-xs text-slate-500">{elemento.marca || "Sin marca"}</p>
                      </div>
                      <p className="text-sm font-semibold text-ink">{formatearDinero(Number(elemento.precio_actual || 0) * elemento.quantity)}</p>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        className="secondary-button px-3 py-2 text-xs"
                        onClick={() => manejar_cambio_cantidad(elemento.id_producto, elemento.quantity - 1)}
                      >
                        -
                      </button>
                      <span className="min-w-10 text-center text-sm font-semibold text-ink">{elemento.quantity}</span>
                      <button
                        type="button"
                        className="secondary-button px-3 py-2 text-xs"
                        onClick={() => manejar_cambio_cantidad(elemento.id_producto, elemento.quantity + 1)}
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
              disabled={!elementosCarrito.length || procesandoCompra}
              onClick={manejar_pagar}
            >
              {procesandoCompra ? "Procesando compra..." : "Comprar"}
            </button>
          </section>

          <section className="glass-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-lg font-semibold text-ink">Últimas compras</h4>
                <p className="mt-1 text-sm text-slate-600"></p>
              </div>
              <Link to="/cliente/historial" className="text-sm font-semibold text-ocean">
                Ver historial
              </Link>
            </div>
            <div className="mt-4 space-y-3">
              {comprasRecientes.length === 0 ? (
                <p className="text-sm text-slate-500">Aún no hay compras recientes.</p>
              ) : (
                comprasRecientes.map((compra) => (
                  <div key={compra.id_venta} className="rounded-2xl border border-sand bg-white/70 p-4">
                    <p className="text-sm font-semibold text-ink">{compra.resumen || compra.id_venta}</p>
                    <p className="mt-1 text-xs text-slate-500">{compra.fecha_venta}</p>
                    <p className="mt-1 text-sm text-slate-600">
                      {compra.total_unidades} unidades · {formatearDinero(compra.monto_total)}
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
    </ShellCliente>
  );
}
