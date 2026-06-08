import PanelGraficoDashboard from "../components/PanelGraficoDashboard.jsx";
import ShellVendedor from "../components/ShellVendedor.jsx";
import { Link } from "react-router-dom";
import { agregar_notificacion } from "../utils/notificationEvents.js";

const metricas = [
  { etiqueta: "Ingresos totales", valor: 128450, variacion: "+8.4%" },
  { etiqueta: "Costos totales", valor: 79420, variacion: "+4.1%" },
  { etiqueta: "Margen de ganancia", valor: 38.2, variacion: "Objetivo 40%" },
];

const alertas = [
  { nombre: "Cereal integral", stock: 7 },
  { nombre: "Salsa gourmet", stock: 5 },
  { nombre: "Cafe organico", stock: 8 },
];

const ventas = [
  { id: "V-2041", nombre: "Aceite de coco", total: 1320 },
  { id: "V-2040", nombre: "Cafe organico", total: 980 },
  { id: "V-2039", nombre: "Cereal integral", total: 840 },
];

const tendencia = [42, 65, 55, 80, 48, 72, 60];

const opcionesGrafico = [
  {
    key: "sales-line",
    label: "Grafico de lineas de ventas",
    kind: "line",
    description: "Muestra la evolucion semanal del volumen de ventas. Es ideal para detectar si el periodo viene creciendo o cayendo.",
    labels: ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"],
    values: tendencia,
    unitLabel: "%",
    insights: [
      "Sirve para leer comportamiento por dia.",
      "Ayuda a detectar picos y caidas en la semana.",
    ],
  },
  {
    key: "revenue-bars",
    label: "Grafico de barras por producto",
    kind: "bar",
    description: "Compara las ventas de los productos destacados para ver cuales generan mas ingreso.",
    labels: ventas.map((venta) => venta.nombre),
    values: ventas.map((venta) => venta.total),
    unitLabel: "MXN",
    insights: [
      "Es util para decidir promociones por articulo.",
      "Permite identificar tu top de ventas sin leer tablas.",
    ],
  },
  {
    key: "stock-histogram",
    label: "Histograma de stock bajo",
    kind: "histogram",
    description: "Agrupa las alertas por nivel de stock para mostrar cuantos productos estan en zona de riesgo.",
    labels: ["1-3", "4-6", "7-9", "10+"],
    values: [1, 1, 1, 0],
    insights: [
      "Resulta util para reposicion y planeacion de compras.",
      "Ayuda a enfocar primero los productos con urgencia.",
    ],
  },
  {
    key: "cost-share",
    label: "Grafico de dona de ingresos y costos",
    kind: "donut",
    description: "Resume el peso relativo de ingresos, costos y margen para entender la salud financiera de un vistazo.",
    slices: [
      { label: "Ingresos", value: metricas[0].valor, color: "#1E4BB8" },
      { label: "Costos", value: metricas[1].valor, color: "#F26B5B" },
      { label: "Margen", value: 39030, color: "#5CC49D" },
    ],
    insights: [
      "Convierte cifras grandes en proporcion visual.",
      "Es buena para mostrar mezcla de ingresos vs egresos.",
    ],
  },
];

const formatoDinero = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 0,
});

export default function ReporteFinanciero() {
  return (
    <ShellVendedor
      title="Reporte financiero"
      subtitle="Resumen de ingresos, costos y margen para el rol vendedor. Incluye alertas de stock bajo y ventas destacadas."
    >
      <div className="mb-4 flex flex-wrap gap-3">
        <Link to="/vendedor" className="secondary-button">
          Volver a productos
        </Link>
      </div>

      <PanelGraficoDashboard
        title="Selector de graficos financieros"
        description="Cambia entre lineas, barras, histogramas y dona para leer el mismo negocio desde distintas perspectivas."
        options={opcionesGrafico}
        defaultKey="sales-line"
      />

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="glass-panel p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-xl font-semibold text-ink">
                Desempeño del periodo
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                Comparativa con el periodo anterior.
              </p>
            </div>
            <select className="input-field w-full sm:w-48">
              <option>Ultimos 30 dias</option>
              <option>Ultimos 90 dias</option>
              <option>Anual</option>
            </select>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {metricas.map((metrica) => (
              <div key={metrica.etiqueta} className="rounded-2xl border border-sand bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {metrica.etiqueta}
                </p>
                <p className="mt-3 font-display text-2xl font-semibold text-ink">
                  {metrica.etiqueta === "Margen de ganancia"
                    ? `${metrica.valor}%`
                    : formatoDinero.format(metrica.valor)}
                </p>
                <p className="mt-2 text-xs text-slate-600">{metrica.variacion}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-2xl border border-sand bg-white/70 p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Tendencia semanal</p>
              <p className="text-xs text-slate-500">Ventas por dia</p>
            </div>
            <div className="mt-4 flex h-40 items-end gap-2">
              {tendencia.map((valor, indice) => (
                <div
                  key={`${valor}-${indice}`}
                  className="flex-1 rounded-2xl bg-[linear-gradient(180deg,rgba(31,78,95,0.8),rgba(147,183,161,0.45))]"
                  style={{ height: `${valor}%` }}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">
              Alertas de stock bajo
            </h4>
            <p className="mt-2 text-sm text-slate-600">
              Productos con riesgo de agotarse.
            </p>
            <div className="mt-4 space-y-3">
              {alertas.map((alerta) => (
                <div
                  key={alerta.nombre}
                  className="flex items-center justify-between rounded-2xl border border-sand bg-white/70 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-semibold text-ink">{alerta.nombre}</p>
                    <p className="text-xs text-slate-500">Stock actual</p>
                  </div>
                  <span className="rounded-full bg-[rgba(184,92,56,0.15)] px-3 py-1 text-xs font-semibold text-copper">
                    {alerta.stock} unidades
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-panel p-5">
            <h4 className="font-display text-lg font-semibold text-ink">
              Ventas destacadas
            </h4>
            <div className="mt-4 space-y-3">
              {ventas.map((venta) => (
                <div
                  key={venta.id}
                  className="flex items-center justify-between rounded-2xl border border-sand bg-white/70 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-semibold text-ink">{venta.nombre}</p>
                    <p className="text-xs text-slate-500">{venta.id}</p>
                  </div>
                  <span className="text-sm font-semibold text-ink">
                    {formatoDinero.format(venta.total)}
                  </span>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="primary-button mt-4 w-full"
              onClick={() => {
                const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
                const url = `${apiBase}/api/vendedor/reportes/ventas/csv?period=30d`;
                agregar_notificacion({
                  kind: "csv-download",
                  title: "Reporte CSV descargado",
                  detail: "Se inicio la descarga del reporte de ventas de los ultimos 30 dias.",
                  source: "Finanzas",
                });
                window.location.href = url;
              }}
            >
              Descargar reporte (CSV)
            </button>
          </div>
        </div>
      </section>
    </ShellVendedor>
  );
}
