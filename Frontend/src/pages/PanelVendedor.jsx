import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Link, useLocation, useNavigate } from "react-router-dom";
import PanelGraficoDashboard from "../components/PanelGraficoDashboard.jsx";
import ShellVendedor from "../components/ShellVendedor.jsx";
import { agregar_notificacion } from "../utils/notificationEvents.js";

const URL_API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TAMANO_PAGINA = 20;

const formularioInicial = {
  id_producto: "",
  nombre: "",
  marca: "",
  categoria: "",
  precio_actual: "",
  stock: "0",
  precio_fabricacion: "",
  fecha_caducidad: "",
  imagen_url: "",
};

const formatoDinero = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 2,
});

function formatearDinero(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return "—";
  }
  return formatoDinero.format(Number(valor));
}

function normalizarValorApi(valor) {
  return valor === null || valor === undefined ? "" : String(valor);
}

function convertirAValoresFormulario(producto) {
  return {
    id_producto: normalizarValorApi(producto.id_producto),
    nombre: normalizarValorApi(producto.nombre),
    marca: normalizarValorApi(producto.marca),
    categoria: normalizarValorApi(producto.categoria),
    precio_actual: normalizarValorApi(producto.precio_actual),
    stock: normalizarValorApi(producto.stock ?? 0),
    precio_fabricacion: normalizarValorApi(producto.precio_fabricacion),
    fecha_caducidad: normalizarValorApi(producto.fecha_caducidad),
    imagen_url: normalizarValorApi(producto.imagen_url),
  };
}

function limpiarTexto(valor) {
  const recortado = valor.trim();
  return recortado.length > 0 ? recortado : null;
}

export default function PanelVendedor() {
  const ubicacion = useLocation();
  const navegar = useNavigate();
  const [productos, setProductos] = useState([]);
  const [valoresFormulario, setValoresFormulario] = useState(formularioInicial);
  const [idEditando, setIdEditando] = useState(null);
  const [modalProductoAbierto, setModalProductoAbierto] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [paginaActual, setPaginaActual] = useState(1);
  const [totalPaginas, setTotalPaginas] = useState(1);
  const [totalElementos, setTotalElementos] = useState(0);
  const [recomendacionPrecio, setRecomendacionPrecio] = useState(null);
  const [cargandoRecomendacion, setCargandoRecomendacion] = useState(false);
  const idVendedor = localStorage.getItem("userId");

  const cargarProductos = async (pagina = 1) => {
    if (!idVendedor) {
      toast.error("No se pudo identificar al vendedor.");
      return;
    }
    setCargando(true);
    try {
      const respuesta = await fetch(
        `${URL_API}/api/vendedor/productos?vendedor_id=${encodeURIComponent(idVendedor)}&page=${pagina}&page_size=${TAMANO_PAGINA}`
      );
      const datos = await respuesta.json().catch(() => []);
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudieron obtener los productos del vendedor.");
      }
      const elementos = Array.isArray(datos.items) ? datos.items : [];
      setProductos(elementos);
      setPaginaActual(Number(datos.page || pagina));
      setTotalPaginas(Number(datos.total_pages || 1));
      setTotalElementos(Number(datos.total_items || 0));
    } catch (error) {
      toast.error(error.message || "No se pudieron obtener los productos del vendedor.");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarProductos();
  }, []);

  useEffect(() => {
    if (ubicacion.hash === "#add-product") {
      setModalProductoAbierto(true);
    }
  }, [ubicacion.hash]);

  useEffect(() => {
    if (!modalProductoAbierto) {
      setRecomendacionPrecio(null);
      return;
    }

    const idProducto = valoresFormulario.id_producto.trim().toUpperCase();
    const nombre = valoresFormulario.nombre.trim();
    if (!idProducto || !nombre) {
      setRecomendacionPrecio(null);
      return;
    }

    const controlador = new AbortController();
    const idTemporizador = window.setTimeout(async () => {
      setCargandoRecomendacion(true);
      try {
        const respuesta = await fetch(`${URL_API}/api/productos/recomendacion-precio`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          signal: controlador.signal,
          body: JSON.stringify({
            id_producto: idProducto,
            nombre,
            marca: limpiarTexto(valoresFormulario.marca),
            categoria: limpiarTexto(valoresFormulario.categoria),
            precio_actual: valoresFormulario.precio_actual === "" ? null : Number(valoresFormulario.precio_actual),
            stock: valoresFormulario.stock === "" ? 0 : Number(valoresFormulario.stock),
            precio_fabricacion: valoresFormulario.precio_fabricacion === "" ? null : Number(valoresFormulario.precio_fabricacion),
            fecha_caducidad: valoresFormulario.fecha_caducidad || null,
            imagen_url: limpiarTexto(valoresFormulario.imagen_url),
          }),
        });
        const datos = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) {
          throw new Error(datos.detail || "No se pudo calcular la recomendación de precio.");
        }
        setRecomendacionPrecio(datos);
      } catch (error) {
        if (error.name !== "AbortError") {
          setRecomendacionPrecio(null);
        }
      } finally {
        setCargandoRecomendacion(false);
      }
    }, 450);

    return () => {
      window.clearTimeout(idTemporizador);
      controlador.abort();
    };
  }, [
    modalProductoAbierto,
    valoresFormulario.id_producto,
    valoresFormulario.nombre,
    valoresFormulario.marca,
    valoresFormulario.categoria,
    valoresFormulario.precio_actual,
    valoresFormulario.stock,
    valoresFormulario.precio_fabricacion,
    valoresFormulario.fecha_caducidad,
    valoresFormulario.imagen_url,
  ]);

  const estadisticas = useMemo(() => {
    const stockBajo = productos.filter((producto) => Number(producto.stock || 0) < 10).length;
    const conCosto = productos.filter(
      (producto) => producto.precio_fabricacion !== null && producto.precio_fabricacion !== undefined
    ).length;
    const conCaducidad = productos.filter((producto) => producto.fecha_caducidad).length;

    return [
      { etiqueta: "Productos", valor: totalElementos },
      { etiqueta: "Stock bajo", valor: stockBajo },
      { etiqueta: "Con costo", valor: conCosto },
      { etiqueta: "Con caducidad", valor: conCaducidad },
    ];
  }, [productos, totalElementos]);

  const opcionesGrafico = useMemo(() => {
    const mapaCategorias = new Map();
    const rangoStock = [
      { label: "0-4", value: 0 },
      { label: "5-9", value: 0 },
      { label: "10-19", value: 0 },
      { label: "20+", value: 0 },
    ];

    const preciosOrdenados = [...productos]
      .map((producto) => ({
        label: producto.nombre ? String(producto.nombre).slice(0, 14) : producto.id_producto,
        value: Number(producto.precio_actual || 0),
      }))
      .sort((izq, der) => der.value - izq.value)
      .slice(0, 8)
      .reverse();

    for (const producto of productos) {
      const categoria = String(producto.categoria || "Sin categoria").trim() || "Sin categoria";
      mapaCategorias.set(categoria, (mapaCategorias.get(categoria) || 0) + 1);

      const stock = Number(producto.stock || 0);
      if (stock <= 4) {
        rangoStock[0].value += 1;
      } else if (stock <= 9) {
        rangoStock[1].value += 1;
      } else if (stock <= 19) {
        rangoStock[2].value += 1;
      } else {
        rangoStock[3].value += 1;
      }
    }

    const entradasCategorias = Array.from(mapaCategorias.entries())
      .sort((izq, der) => der[1] - izq[1])
      .slice(0, 8);

    return [
      {
        key: "categories",
        label: "Grafico de barras por categoria",
        kind: "bar",
        description: "Muestra en que categorias se concentra mas inventario. Es util para decidir que familias ampliar o depurar.",
        labels: entradasCategorias.map(([categoria]) => categoria),
        values: entradasCategorias.map(([, conteo]) => conteo),
        unitLabel: "productos",
        insights: [
          "Sirve para comparar volumen por familia.",
          "Ayuda a detectar categorias demasiado cargadas o vacias.",
        ],
      },
      {
        key: "stock-histogram",
        label: "Histograma de stock",
        kind: "histogram",
        description: "Agrupa el inventario por rangos de stock. Es util para identificar agotados, riesgo y productos holgados.",
        labels: rangoStock.map((rango) => rango.label),
        values: rangoStock.map((rango) => rango.value),
        insights: [
          "Destaca si hay muchos productos en stock muy bajo.",
          "Ayuda a planear reposiciones por lote.",
        ],
      },
      {
        key: "price-line",
        label: "Grafico de lineas de precios",
        kind: "line",
        description: "Ordena los productos por precio para ver la curva del catalogo y detectar saltos o segmentos premium.",
        labels: preciosOrdenados.map((elemento) => elemento.label),
        values: preciosOrdenados.map((elemento) => elemento.value),
        unitLabel: "MXN",
        insights: [
          "Es util para comparar productos caros y economicos en una misma vista.",
          "Permite ver si el catalogo tiene una escalera de precios equilibrada.",
        ],
      },
      {
        key: "inventory-share",
        label: "Grafico de dona de inventario",
        kind: "donut",
        description: "Resume el estado del inventario entre stock bajo, medio y alto para visualizar la salud general del catalogo.",
        slices: [
          { label: "Stock bajo (0-4)", value: rangoStock[0].value, color: "#F26B5B" },
          { label: "Stock medio (5-19)", value: rangoStock[1].value + rangoStock[2].value, color: "#3C9BE8" },
          { label: "Stock alto (20+)", value: rangoStock[3].value, color: "#5CC49D" },
        ],
        insights: [
          "Resume el inventario en una sola lectura.",
          "Sirve para decidir si conviene comprar mas o liberar espacio.",
        ],
      },
    ];
  }, [productos]);

  const manejar_cambio = (evento) => {
    const { name, value } = evento.target;
    const siguienteValor = name === "id_producto" ? value.toUpperCase() : value;
    setValoresFormulario((actual) => ({
      ...actual,
      [name]: siguienteValor,
    }));
  };

  const manejar_cambio_archivo_imagen = (evento) => {
    const archivo = evento.target.files?.[0];
    if (!archivo) {
      return;
    }

    const lector = new FileReader();
    lector.onload = () => {
      setValoresFormulario((actual) => ({
        ...actual,
        imagen_url: String(lector.result || ""),
      }));
    };
    lector.onerror = () => {
      toast.error("No se pudo leer la imagen seleccionada.");
    };
    lector.readAsDataURL(archivo);
    evento.target.value = "";
  };

  const limpiar_formulario = () => {
    setValoresFormulario(formularioInicial);
    setIdEditando(null);
  };

  const abrir_modal_nuevo_producto = () => {
    setValoresFormulario(formularioInicial);
    setIdEditando(null);
    setModalProductoAbierto(true);
    if (ubicacion.hash !== "#add-product") {
      navegar({ pathname: ubicacion.pathname, hash: "add-product" }, { replace: false });
    }
  };

  const cerrar_modal_producto = () => {
    limpiar_formulario();
    setModalProductoAbierto(false);
    if (ubicacion.hash === "#add-product") {
      navegar({ pathname: ubicacion.pathname }, { replace: true });
    }
  };

  const manejar_edicion = (producto) => {
    setIdEditando(producto.id_producto);
    setValoresFormulario(convertirAValoresFormulario(producto));
    setModalProductoAbierto(true);
  };

  const manejar_eliminar = async (idProducto) => {
    const producto = productos.find((elemento) => elemento.id_producto === idProducto);
    const confirmado = window.confirm("¿Deseas eliminar este producto?");
    if (!confirmado) {
      return;
    }

    try {
      const respuesta = await fetch(`${URL_API}/api/productos/${encodeURIComponent(idProducto)}`, {
        method: "DELETE",
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo eliminar el producto.");
      }
      toast.success(datos.detail || "Producto eliminado correctamente.");
      agregar_notificacion({
        kind: "product-delete",
        title: "Producto eliminado",
        detail: `${producto?.nombre || idProducto} fue retirado del inventario.`,
        source: "Inventario",
      });
      if (idEditando === idProducto) {
        cerrar_modal_producto();
      }
      await cargarProductos(paginaActual);
    } catch (error) {
      toast.error(error.message || "No se pudo eliminar el producto.");
    }
  };

  const manejar_envio = async (evento) => {
    evento.preventDefault();
    if (enviando) {
      return;
    }

    const idProducto = valoresFormulario.id_producto.trim().toUpperCase();
    const nombre = valoresFormulario.nombre.trim();
    const precioActual = valoresFormulario.precio_actual === "" ? null : Number(valoresFormulario.precio_actual);
    const stock = valoresFormulario.stock === "" ? 0 : Number(valoresFormulario.stock);
    const precioFabricacion = valoresFormulario.precio_fabricacion === "" ? null : Number(valoresFormulario.precio_fabricacion);
    const fechaCaducidad = valoresFormulario.fecha_caducidad || null;
    const imagenUrl = limpiarTexto(valoresFormulario.imagen_url);

    if (!idProducto || !nombre) {
      toast.error("El id y el nombre del producto son obligatorios.");
      return;
    }
    if (Number.isNaN(precioActual) || precioActual === null) {
      toast.error("Debes capturar un precio valido.");
      return;
    }
    if (Number.isNaN(stock)) {
      toast.error("Debes capturar un stock valido.");
      return;
    }
    if (precioFabricacion !== null && Number.isNaN(precioFabricacion)) {
      toast.error("El costo de fabricacion debe ser un numero valido.");
      return;
    }

    const carga = {
      id_producto: idProducto,
      nombre,
      marca: limpiarTexto(valoresFormulario.marca),
      categoria: limpiarTexto(valoresFormulario.categoria),
      precio_actual: precioActual,
      stock,
      precio_fabricacion: precioFabricacion,
      fecha_caducidad: fechaCaducidad,
      imagen_url: imagenUrl,
    };

    setEnviando(true);
    try {
      const respuesta = await fetch(
        idEditando
          ? `${URL_API}/api/productos/${encodeURIComponent(idEditando)}`
          : `${URL_API}/api/productos`,
        {
          method: idEditando ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(carga),
        }
      );
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(datos.detail || "No se pudo guardar el producto.");
      }
      toast.success(idEditando ? "Producto actualizado correctamente." : "Producto creado correctamente.");
      agregar_notificacion({
        kind: idEditando ? "product-update" : "product-create",
        title: idEditando ? "Producto actualizado" : "Producto agregado",
        detail: `${carga.nombre} ya forma parte del catalogo activo.`,
        source: "Inventario",
      });
      cerrar_modal_producto();
      await cargarProductos(paginaActual);
    } catch (error) {
      toast.error(error.message || "No se pudo guardar el producto.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <ShellVendedor
      title="Gestión de productos"
      subtitle="Crea, edita, consulta y elimina productos desde Oracle. El primer acceso del vendedor se centra en este módulo."
    >
      <section id="add-product" className="glass-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="tag">CRUD de productos</p>
            <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
              Mantén el catálogo operativo
            </h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Abre el modal para crear o editar productos sin mostrar el formulario completo desde el inicio.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={abrir_modal_nuevo_producto} className="primary-button">
              Agregar producto
            </button>
            <button type="button" onClick={() => cargarProductos(paginaActual)} className="secondary-button">
              Recargar
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {estadisticas.map((estadistica) => (
            <div key={estadistica.etiqueta} className="rounded-2xl border border-sand bg-white/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {estadistica.etiqueta}
              </p>
              <p className="mt-2 font-display text-2xl font-semibold text-ink">
                {estadistica.valor}
              </p>
            </div>
          ))}
        </div>
      </section>

      <PanelGraficoDashboard
        title="Explora el inventario con distintos graficos"
        description="Elige barras, histograma, lineas o dona segun el tipo de dato que quieras leer. Cada opcion muestra una lectura distinta del catalogo activo."
        options={opcionesGrafico}
        defaultKey="categories"
      />

      <div className="flex flex-wrap gap-3">
        <Link to="/vendedor/reporte" className="primary-button">
          Ir a reporte financiero
        </Link>
      </div>

      <section className="glass-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-xl font-semibold text-ink">
              Productos en base de datos
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              Las acciones editan o eliminan directamente los registros persistidos.
            </p>
          </div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {cargando ? "Cargando..." : `${totalElementos} registros`}
          </p>
        </div>

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-[1100px] w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="pb-3">Id</th>
                <th className="pb-3">Nombre</th>
                <th className="pb-3">Marca</th>
                <th className="pb-3">Categoria</th>
                <th className="pb-3">Precio</th>
                <th className="pb-3">Stock</th>
                <th className="pb-3">Costo</th>
                <th className="pb-3">Caducidad</th>
                <th className="pb-3">Actualizado</th>
                <th className="pb-3">Acciones</th>
              </tr>
            </thead>
            <tbody className="text-slate-700">
              {productos.map((producto) => (
                <tr key={producto.id_producto} className="border-t border-sand align-top">
                  <td className="py-3 font-semibold text-ink">{producto.id_producto}</td>
                  <td className="py-3">
                    <div className="font-semibold text-ink">{producto.nombre}</div>
                  </td>
                  <td className="py-3">{producto.marca || "—"}</td>
                  <td className="py-3">{producto.categoria || "—"}</td>
                  <td className="py-3">{formatearDinero(producto.precio_actual)}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <span>{producto.stock ?? 0}</span>
                      {Number(producto.stock || 0) < 10 ? (
                        <span className="rounded-full bg-[rgba(242,107,91,0.15)] px-2 py-1 text-[10px] font-semibold uppercase text-copper">
                          Stock bajo
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="py-3">{formatearDinero(producto.precio_fabricacion)}</td>
                  <td className="py-3">{producto.fecha_caducidad || "—"}</td>
                  <td className="py-3">{producto.fecha_actualizacion || "—"}</td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-2">
                      <button type="button" className="secondary-button" onClick={() => manejar_edicion(producto)}>
                        Editar
                      </button>
                      <button
                        type="button"
                        className="rounded-2xl border border-copper px-4 py-2 text-xs font-semibold text-copper transition hover:bg-[rgba(242,107,91,0.08)]"
                        onClick={() => manejar_eliminar(producto.id_producto)}
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!cargando && productos.length === 0 ? (
                <tr>
                  <td colSpan="10" className="py-8 text-center text-sm text-slate-500">
                    No hay productos registrados todavía.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-sand pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">
            Página {paginaActual} de {totalPaginas} · {TAMANO_PAGINA} productos por vista
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="secondary-button disabled:cursor-not-allowed disabled:opacity-50"
              disabled={cargando || paginaActual <= 1}
              onClick={() => cargarProductos(paginaActual - 1)}
            >
              Anterior
            </button>
            <button
              type="button"
              className="secondary-button disabled:cursor-not-allowed disabled:opacity-50"
              disabled={cargando || paginaActual >= totalPaginas}
              onClick={() => cargarProductos(paginaActual + 1)}
            >
              Siguiente
            </button>
          </div>
        </div>
      </section>

      {modalProductoAbierto ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6 backdrop-blur-sm" onClick={cerrar_modal_producto}>
          <div
            className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[32px] border border-sand bg-white p-6 shadow-[0_30px_80px_rgba(11,27,43,0.25)]"
            onClick={(evento) => evento.stopPropagation()}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="tag">{idEditando ? "Editar producto" : "Nuevo producto"}</p>
                <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                  {idEditando ? "Actualizar producto" : "Agregar producto"}
                </h3>
                <p className="mt-2 max-w-2xl text-sm text-slate-600">
                  Captura los datos del producto desde esta ventana. Puedes pegar una URL de imagen o cargar una imagen para convertirla en un enlace base64.
                </p>
              </div>
              <button type="button" onClick={cerrar_modal_producto} className="secondary-button">
                Cerrar
              </button>
            </div>

            <form className="mt-6 grid gap-5" onSubmit={manejar_envio}>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Id producto
                  </label>
                  <input
                    type="text"
                    name="id_producto"
                    value={valoresFormulario.id_producto}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="P-0001"
                    maxLength={20}
                    required
                    disabled={Boolean(idEditando)}
                  />
                </div>
                <div className="xl:col-span-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Nombre
                  </label>
                  <input
                    type="text"
                    name="nombre"
                    value={valoresFormulario.nombre}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="Nombre del producto"
                    maxLength={1000}
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Marca
                  </label>
                  <input
                    type="text"
                    name="marca"
                    value={valoresFormulario.marca}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="Marca"
                    maxLength={150}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Categoria
                  </label>
                  <input
                    type="text"
                    name="categoria"
                    value={valoresFormulario.categoria}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="Categoria"
                    maxLength={100}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Precio actual
                  </label>
                  <input
                    type="number"
                    name="precio_actual"
                    value={valoresFormulario.precio_actual}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="0.00"
                    min="0"
                    step="0.01"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Stock
                  </label>
                  <input
                    type="number"
                    name="stock"
                    value={valoresFormulario.stock}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="0"
                    min="0"
                    step="1"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Precio fabricacion
                  </label>
                  <input
                    type="number"
                    name="precio_fabricacion"
                    value={valoresFormulario.precio_fabricacion}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                    placeholder="0.00"
                    min="0"
                    step="0.01"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Fecha caducidad
                  </label>
                  <input
                    type="date"
                    name="fecha_caducidad"
                    value={valoresFormulario.fecha_caducidad}
                    onChange={manejar_cambio}
                    className="input-field mt-2"
                  />
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      URL de imagen
                    </label>
                    <input
                      type="url"
                      name="imagen_url"
                      value={valoresFormulario.imagen_url}
                      onChange={manejar_cambio}
                      className="input-field mt-2"
                      placeholder="https://..."
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      Subir imagen
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={manejar_cambio_archivo_imagen}
                      className="input-field mt-2 pt-2"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      Vista previa
                    </label>
                    <div className="mt-2 flex min-h-[180px] items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#BFC9DE] bg-[#F8FAFF] p-3">
                      {valoresFormulario.imagen_url ? (
                        <img
                          src={valoresFormulario.imagen_url}
                          alt={valoresFormulario.nombre || "Vista previa del producto"}
                          className="max-h-[160px] w-full rounded-xl object-contain"
                        />
                      ) : (
                        <p className="text-sm text-slate-500">Sin imagen cargada todavía.</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-sand bg-[#F8FAFF] p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Recomendación de precio
                  </p>
                  {cargandoRecomendacion ? (
                    <p className="mt-2 text-sm text-slate-600">Calculando precio sugerido...</p>
                  ) : recomendacionPrecio ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      <div className="rounded-2xl border border-white/80 bg-white p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Precio sugerido</p>
                        <p className="mt-1 text-2xl font-semibold text-ink">
                          {formatearDinero(recomendacionPrecio.suggested_price)}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">{recomendacionPrecio.reason}</p>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Mercado comparable</p>
                          <p className="mt-1 font-semibold text-ink">
                            {formatearDinero(recomendacionPrecio.market_reference_price)}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Compra recomendada</p>
                          <p className="mt-1 font-semibold text-ink">
                            {recomendacionPrecio.buy_now ? "Sí, es competitivo" : "Conviene revisar"}
                          </p>
                        </div>
                      </div>
                      {Array.isArray(recomendacionPrecio.similar_products) && recomendacionPrecio.similar_products.length > 0 ? (
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Similares detectados</p>
                          <div className="mt-2 space-y-2">
                            {recomendacionPrecio.similar_products.slice(0, 3).map((elemento) => (
                              <div key={elemento.id_producto} className="rounded-xl bg-[#F8FAFF] px-3 py-2">
                                <p className="font-medium text-ink">{elemento.nombre || elemento.id_producto}</p>
                                <p className="text-xs text-slate-500">
                                  {formatearDinero(elemento.precio_actual)} · similitud {(Number(elemento.similarity_score || 0) * 100).toFixed(1)}%
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-600">
                      Completa nombre, marca o categoria para calcular un precio sugerido basado en productos similares.
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-3 border-t border-sand pt-4">
                <button
                  type="submit"
                  className="primary-button disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={enviando}
                >
                  {enviando
                    ? idEditando
                      ? "Actualizando..."
                      : "Creando..."
                    : idEditando
                    ? "Actualizar producto"
                    : "Crear producto"}
                </button>
                <button type="button" onClick={limpiar_formulario} className="secondary-button">
                  Limpiar formulario
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </ShellVendedor>
  );
}
