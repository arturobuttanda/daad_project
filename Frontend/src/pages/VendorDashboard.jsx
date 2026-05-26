import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import VendorShell from "../components/VendorShell.jsx";

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
  };
}

function cleanText(value) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export default function VendorDashboard() {
  const [products, setProducts] = useState([]);
  const [formValues, setFormValues] = useState(initialForm);
  const [editingId, setEditingId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
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

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === "id_producto" ? value.toUpperCase() : value;
    setFormValues((current) => ({
      ...current,
      [name]: nextValue,
    }));
  };

  const resetForm = () => {
    setFormValues(initialForm);
    setEditingId(null);
  };

  const handleEdit = (product) => {
    setEditingId(product.id_producto);
    setFormValues(toFormValues(product));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (productId) => {
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
      if (editingId === productId) {
        resetForm();
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
      resetForm();
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
      <section className="glass-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="tag">CRUD de productos</p>
            <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
              Mantén el catálogo operativo
            </h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              El formulario escribe directamente en la tabla de productos y el listado refleja lo que existe en la base de datos.
            </p>
          </div>
          <button type="button" onClick={() => loadProducts(currentPage)} className="secondary-button">
            Recargar
          </button>
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

      <div className="flex flex-wrap gap-3">
        <Link to="/vendedor/reporte" className="primary-button">
          Ir a reporte financiero
        </Link>
      </div>

      <section className="glass-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-xl font-semibold text-ink">
              {editingId ? "Editar producto" : "Nuevo producto"}
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              Usa los campos disponibles en la plantilla del vendedor para crear o actualizar registros.
            </p>
          </div>
          {editingId ? (
            <button type="button" onClick={resetForm} className="secondary-button">
              Cancelar edición
            </button>
          ) : null}
        </div>

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
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

          <div className="flex flex-wrap gap-3">
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
            <button type="button" onClick={resetForm} className="secondary-button">
              Limpiar formulario
            </button>
          </div>
        </form>
      </section>

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
    </VendorShell>
  );
}
