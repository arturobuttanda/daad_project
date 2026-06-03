import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Link, useLocation, useNavigate } from "react-router-dom";
import DashboardChartPanel from "../components/DashboardChartPanel.jsx";
import VendorShell from "../components/VendorShell.jsx";
import { addNotification } from "../utils/notificationEvents.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PAGE_SIZE = 20;

const initialForm = {
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

const money = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 2,
});

function formatMoney(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return money.format(Number(value));
}

function normalizeApiValue(value) {
  return value === null || value === undefined ? "" : String(value);
}

function toFormValues(product) {
  return {
    id_producto: normalizeApiValue(product.id_producto),
    nombre: normalizeApiValue(product.nombre),
    marca: normalizeApiValue(product.marca),
    categoria: normalizeApiValue(product.categoria),
    precio_actual: normalizeApiValue(product.precio_actual),
    stock: normalizeApiValue(product.stock ?? 0),
    precio_fabricacion: normalizeApiValue(product.precio_fabricacion),
    fecha_caducidad: normalizeApiValue(product.fecha_caducidad),
    imagen_url: normalizeApiValue(product.imagen_url),
  };
}

function cleanText(value) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export default function VendorDashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [formValues, setFormValues] = useState(initialForm);
  const [editingId, setEditingId] = useState(null);
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [priceRecommendation, setPriceRecommendation] = useState(null);
  const [isPriceRecommendationLoading, setIsPriceRecommendationLoading] = useState(false);
  const vendorId = localStorage.getItem("userId");

  const loadProducts = async (page = 1) => {
    if (!vendorId) {
      toast.error("No se pudo identificar al vendedor.");
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_URL}/api/vendedor/productos?vendedor_id=${encodeURIComponent(vendorId)}&page=${page}&page_size=${PAGE_SIZE}`
      );
      const data = await response.json().catch(() => []);
      if (!response.ok) {
        throw new Error(data.detail || "No se pudieron obtener los productos del vendedor.");
      }
      const items = Array.isArray(data.items) ? data.items : [];
      setProducts(items);
      setCurrentPage(Number(data.page || page));
      setTotalPages(Number(data.total_pages || 1));
      setTotalItems(Number(data.total_items || 0));
    } catch (error) {
      toast.error(error.message || "No se pudieron obtener los productos del vendedor.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    if (location.hash === "#add-product") {
      setIsProductModalOpen(true);
    }
  }, [location.hash]);

  useEffect(() => {
    if (!isProductModalOpen) {
      setPriceRecommendation(null);
      return;
    }

    const productId = formValues.id_producto.trim().toUpperCase();
    const nombre = formValues.nombre.trim();
    if (!productId || !nombre) {
      setPriceRecommendation(null);
      return;
    }

    const controller = new AbortController();
    const timerId = window.setTimeout(async () => {
      setIsPriceRecommendationLoading(true);
      try {
        const response = await fetch(`${API_URL}/api/productos/recomendacion-precio`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          signal: controller.signal,
          body: JSON.stringify({
            id_producto: productId,
            nombre,
            marca: cleanText(formValues.marca),
            categoria: cleanText(formValues.categoria),
            precio_actual: formValues.precio_actual === "" ? null : Number(formValues.precio_actual),
            stock: formValues.stock === "" ? 0 : Number(formValues.stock),
            precio_fabricacion: formValues.precio_fabricacion === "" ? null : Number(formValues.precio_fabricacion),
            fecha_caducidad: formValues.fecha_caducidad || null,
            imagen_url: cleanText(formValues.imagen_url),
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || "No se pudo calcular la recomendación de precio.");
        }
        setPriceRecommendation(data);
      } catch (error) {
        if (error.name !== "AbortError") {
          setPriceRecommendation(null);
        }
      } finally {
        setIsPriceRecommendationLoading(false);
      }
    }, 450);

    return () => {
      window.clearTimeout(timerId);
      controller.abort();
    };
  }, [
    isProductModalOpen,
    formValues.id_producto,
    formValues.nombre,
    formValues.marca,
    formValues.categoria,
    formValues.precio_actual,
    formValues.stock,
    formValues.precio_fabricacion,
    formValues.fecha_caducidad,
    formValues.imagen_url,
  ]);

  const stats = useMemo(() => {
    const stockBajo = products.filter((product) => Number(product.stock || 0) < 10).length;
    const conCosto = products.filter(
      (product) => product.precio_fabricacion !== null && product.precio_fabricacion !== undefined
    ).length;
    const conCaducidad = products.filter((product) => product.fecha_caducidad).length;

    return [
      { label: "Productos", value: totalItems },
      { label: "Stock bajo", value: stockBajo },
      { label: "Con costo", value: conCosto },
      { label: "Con caducidad", value: conCaducidad },
    ];
  }, [products, totalItems]);

  const chartOptions = useMemo(() => {
    const categoryMap = new Map();
    const stockBuckets = [
      { label: "0-4", value: 0 },
      { label: "5-9", value: 0 },
      { label: "10-19", value: 0 },
      { label: "20+", value: 0 },
    ];

    const sortedPrices = [...products]
      .map((product) => ({
        label: product.nombre ? String(product.nombre).slice(0, 14) : product.id_producto,
        value: Number(product.precio_actual || 0),
      }))
      .sort((left, right) => right.value - left.value)
      .slice(0, 8)
      .reverse();

    for (const product of products) {
      const category = String(product.categoria || "Sin categoria").trim() || "Sin categoria";
      categoryMap.set(category, (categoryMap.get(category) || 0) + 1);

      const stock = Number(product.stock || 0);
      if (stock <= 4) {
        stockBuckets[0].value += 1;
      } else if (stock <= 9) {
        stockBuckets[1].value += 1;
      } else if (stock <= 19) {
        stockBuckets[2].value += 1;
      } else {
        stockBuckets[3].value += 1;
      }
    }

    const categoryEntries = Array.from(categoryMap.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 8);

    return [
      {
        key: "categories",
        label: "Grafico de barras por categoria",
        kind: "bar",
        description: "Muestra en que categorias se concentra mas inventario. Es util para decidir que familias ampliar o depurar.",
        labels: categoryEntries.map(([category]) => category),
        values: categoryEntries.map(([, count]) => count),
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
        labels: stockBuckets.map((bucket) => bucket.label),
        values: stockBuckets.map((bucket) => bucket.value),
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
        labels: sortedPrices.map((item) => item.label),
        values: sortedPrices.map((item) => item.value),
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
          { label: "Stock bajo (0-4)", value: stockBuckets[0].value, color: "#F26B5B" },
          { label: "Stock medio (5-19)", value: stockBuckets[1].value + stockBuckets[2].value, color: "#3C9BE8" },
          { label: "Stock alto (20+)", value: stockBuckets[3].value, color: "#5CC49D" },
        ],
        insights: [
          "Resume el inventario en una sola lectura.",
          "Sirve para decidir si conviene comprar mas o liberar espacio.",
        ],
      },
    ];
  }, [products]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === "id_producto" ? value.toUpperCase() : value;
    setFormValues((current) => ({
      ...current,
      [name]: nextValue,
    }));
  };

  const handleImageFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setFormValues((current) => ({
        ...current,
        imagen_url: String(reader.result || ""),
      }));
    };
    reader.onerror = () => {
      toast.error("No se pudo leer la imagen seleccionada.");
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  const clearForm = () => {
    setFormValues(initialForm);
    setEditingId(null);
  };

  const openNewProductModal = () => {
    setFormValues(initialForm);
    setEditingId(null);
    setIsProductModalOpen(true);
    if (location.hash !== "#add-product") {
      navigate({ pathname: location.pathname, hash: "add-product" }, { replace: false });
    }
  };

  const closeProductModal = () => {
    clearForm();
    setIsProductModalOpen(false);
    if (location.hash === "#add-product") {
      navigate({ pathname: location.pathname }, { replace: true });
    }
  };

  const handleEdit = (product) => {
    setEditingId(product.id_producto);
    setFormValues(toFormValues(product));
    setIsProductModalOpen(true);
  };

  const handleDelete = async (productId) => {
    const product = products.find((item) => item.id_producto === productId);
    const confirmed = window.confirm("¿Deseas eliminar este producto?");
    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/productos/${encodeURIComponent(productId)}`, {
        method: "DELETE",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo eliminar el producto.");
      }
      toast.success(data.detail || "Producto eliminado correctamente.");
      addNotification({
        kind: "product-delete",
        title: "Producto eliminado",
        detail: `${product?.nombre || productId} fue retirado del inventario.`,
        source: "Inventario",
      });
      if (editingId === productId) {
        closeProductModal();
      }
      await loadProducts(currentPage);
    } catch (error) {
      toast.error(error.message || "No se pudo eliminar el producto.");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    const productId = formValues.id_producto.trim().toUpperCase();
    const nombre = formValues.nombre.trim();
    const precioActual = formValues.precio_actual === "" ? null : Number(formValues.precio_actual);
    const stock = formValues.stock === "" ? 0 : Number(formValues.stock);
    const precioFabricacion = formValues.precio_fabricacion === "" ? null : Number(formValues.precio_fabricacion);
    const fechaCaducidad = formValues.fecha_caducidad || null;
    const imagenUrl = cleanText(formValues.imagen_url);

    if (!productId || !nombre) {
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

    const payload = {
      id_producto: productId,
      nombre,
      marca: cleanText(formValues.marca),
      categoria: cleanText(formValues.categoria),
      precio_actual: precioActual,
      stock,
      precio_fabricacion: precioFabricacion,
      fecha_caducidad: fechaCaducidad,
      imagen_url: imagenUrl,
    };

    setIsSubmitting(true);
    try {
      const response = await fetch(
        editingId
          ? `${API_URL}/api/productos/${encodeURIComponent(editingId)}`
          : `${API_URL}/api/productos`,
        {
          method: editingId ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "No se pudo guardar el producto.");
      }
      toast.success(editingId ? "Producto actualizado correctamente." : "Producto creado correctamente.");
      addNotification({
        kind: editingId ? "product-update" : "product-create",
        title: editingId ? "Producto actualizado" : "Producto agregado",
        detail: `${payload.nombre} ya forma parte del catalogo activo.`,
        source: "Inventario",
      });
      closeProductModal();
      await loadProducts(currentPage);
    } catch (error) {
      toast.error(error.message || "No se pudo guardar el producto.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <VendorShell
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
            <button type="button" onClick={openNewProductModal} className="primary-button">
              Add product
            </button>
            <button type="button" onClick={() => loadProducts(currentPage)} className="secondary-button">
              Recargar
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-sand bg-white/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {stat.label}
              </p>
              <p className="mt-2 font-display text-2xl font-semibold text-ink">
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      </section>

      <DashboardChartPanel
        title="Explora el inventario con distintos graficos"
        description="Elige barras, histograma, lineas o dona segun el tipo de dato que quieras leer. Cada opcion muestra una lectura distinta del catalogo activo."
        options={chartOptions}
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
            {isLoading ? "Cargando..." : `${totalItems} registros`}
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
              {products.map((product) => (
                <tr key={product.id_producto} className="border-t border-sand align-top">
                  <td className="py-3 font-semibold text-ink">{product.id_producto}</td>
                  <td className="py-3">
                    <div className="font-semibold text-ink">{product.nombre}</div>
                  </td>
                  <td className="py-3">{product.marca || "—"}</td>
                  <td className="py-3">{product.categoria || "—"}</td>
                  <td className="py-3">{formatMoney(product.precio_actual)}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <span>{product.stock ?? 0}</span>
                      {Number(product.stock || 0) < 10 ? (
                        <span className="rounded-full bg-[rgba(242,107,91,0.15)] px-2 py-1 text-[10px] font-semibold uppercase text-copper">
                          Stock bajo
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="py-3">{formatMoney(product.precio_fabricacion)}</td>
                  <td className="py-3">{product.fecha_caducidad || "—"}</td>
                  <td className="py-3">{product.fecha_actualizacion || "—"}</td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-2">
                      <button type="button" className="secondary-button" onClick={() => handleEdit(product)}>
                        Editar
                      </button>
                      <button
                        type="button"
                        className="rounded-2xl border border-copper px-4 py-2 text-xs font-semibold text-copper transition hover:bg-[rgba(242,107,91,0.08)]"
                        onClick={() => handleDelete(product.id_producto)}
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!isLoading && products.length === 0 ? (
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
            Página {currentPage} de {totalPages} · {PAGE_SIZE} productos por vista
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="secondary-button disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isLoading || currentPage <= 1}
              onClick={() => loadProducts(currentPage - 1)}
            >
              Anterior
            </button>
            <button
              type="button"
              className="secondary-button disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isLoading || currentPage >= totalPages}
              onClick={() => loadProducts(currentPage + 1)}
            >
              Siguiente
            </button>
          </div>
        </div>
      </section>

      {isProductModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6 backdrop-blur-sm" onClick={closeProductModal}>
          <div
            className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[32px] border border-sand bg-white p-6 shadow-[0_30px_80px_rgba(11,27,43,0.25)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="tag">{editingId ? "Editar producto" : "Nuevo producto"}</p>
                <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                  {editingId ? "Actualizar producto" : "Agregar producto"}
                </h3>
                <p className="mt-2 max-w-2xl text-sm text-slate-600">
                  Captura los datos del producto desde esta ventana. Puedes pegar una URL de imagen o cargar una imagen para convertirla en un enlace base64.
                </p>
              </div>
              <button type="button" onClick={closeProductModal} className="secondary-button">
                Cerrar
              </button>
            </div>

            <form className="mt-6 grid gap-5" onSubmit={handleSubmit}>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Id producto
                  </label>
                  <input
                    type="text"
                    name="id_producto"
                    value={formValues.id_producto}
                    onChange={handleChange}
                    className="input-field mt-2"
                    placeholder="P-0001"
                    maxLength={20}
                    required
                    disabled={Boolean(editingId)}
                  />
                </div>
                <div className="xl:col-span-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Nombre
                  </label>
                  <input
                    type="text"
                    name="nombre"
                    value={formValues.nombre}
                    onChange={handleChange}
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
                    value={formValues.marca}
                    onChange={handleChange}
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
                    value={formValues.categoria}
                    onChange={handleChange}
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
                    value={formValues.precio_actual}
                    onChange={handleChange}
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
                    value={formValues.stock}
                    onChange={handleChange}
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
                    value={formValues.precio_fabricacion}
                    onChange={handleChange}
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
                    value={formValues.fecha_caducidad}
                    onChange={handleChange}
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
                      value={formValues.imagen_url}
                      onChange={handleChange}
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
                      onChange={handleImageFileChange}
                      className="input-field mt-2 pt-2"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      Vista previa
                    </label>
                    <div className="mt-2 flex min-h-[180px] items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#BFC9DE] bg-[#F8FAFF] p-3">
                      {formValues.imagen_url ? (
                        <img
                          src={formValues.imagen_url}
                          alt={formValues.nombre || "Vista previa del producto"}
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
                  {isPriceRecommendationLoading ? (
                    <p className="mt-2 text-sm text-slate-600">Calculando precio sugerido...</p>
                  ) : priceRecommendation ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-600">
                      <div className="rounded-2xl border border-white/80 bg-white p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-500">Precio sugerido</p>
                        <p className="mt-1 text-2xl font-semibold text-ink">
                          {formatMoney(priceRecommendation.suggested_price)}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">{priceRecommendation.reason}</p>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Mercado comparable</p>
                          <p className="mt-1 font-semibold text-ink">
                            {formatMoney(priceRecommendation.market_reference_price)}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Compra recomendada</p>
                          <p className="mt-1 font-semibold text-ink">
                            {priceRecommendation.buy_now ? "Sí, es competitivo" : "Conviene revisar"}
                          </p>
                        </div>
                      </div>
                      {Array.isArray(priceRecommendation.similar_products) && priceRecommendation.similar_products.length > 0 ? (
                        <div className="rounded-2xl border border-white/80 bg-white p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-500">Similares detectados</p>
                          <div className="mt-2 space-y-2">
                            {priceRecommendation.similar_products.slice(0, 3).map((item) => (
                              <div key={item.id_producto} className="rounded-xl bg-[#F8FAFF] px-3 py-2">
                                <p className="font-medium text-ink">{item.nombre || item.id_producto}</p>
                                <p className="text-xs text-slate-500">
                                  {formatMoney(item.precio_actual)} · similitud {(Number(item.similarity_score || 0) * 100).toFixed(1)}%
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
                  disabled={isSubmitting}
                >
                  {isSubmitting
                    ? editingId
                      ? "Actualizando..."
                      : "Creando..."
                    : editingId
                    ? "Actualizar producto"
                    : "Crear producto"}
                </button>
                <button type="button" onClick={clearForm} className="secondary-button">
                  Limpiar formulario
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </VendorShell>
  );
}
