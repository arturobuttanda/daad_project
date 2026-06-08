import { useEffect, useMemo, useState } from "react";

function formatearValorPredeterminado(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return "0";
  }
  return new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 }).format(Number(valor));
}

function construirRutaLinea(valores) {
  if (!valores.length) {
    return "";
  }

  const maximo = Math.max(...valores, 1);
  const minimo = Math.min(...valores, 0);
  const rango = maximo - minimo || 1;

  return valores
    .map((valor, indice) => {
      const x = valores.length === 1 ? 50 : (indice / (valores.length - 1)) * 100;
      const y = 92 - (((valor - minimo) / rango) * 72);
      return `${indice === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function LeyendaGrafico({ opcion }) {
  if (opcion.kind === "donut") {
    return (
      <div className="space-y-2">
        {opcion.slices.map((segmento) => (
          <div key={segmento.label} className="flex items-center justify-between gap-3 rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: segmento.color }} />
              <span className="font-medium text-slate-700">{segmento.label}</span>
            </div>
            <span className="font-semibold text-ink">{formatearValorPredeterminado(segmento.value)}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {opcion.labels.map((etiqueta, indice) => (
        <div key={etiqueta} className="rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{etiqueta}</p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {formatearValorPredeterminado(opcion.values[indice])} {opcion.unitLabel || ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function GraficoBarras({ opcion }) {
  const maximo = Math.max(...opcion.values, 1);

  return (
    <div className="flex h-72 items-end gap-3 rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] px-4 py-5">
      {opcion.values.map((valor, indice) => {
        const altura = (valor / maximo) * 100;
        return (
          <div key={`${opcion.labels[indice]}-${indice}`} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <div className="flex h-full w-full items-end">
              <div
                className="w-full rounded-t-2xl bg-[linear-gradient(180deg,#7BC9FF_0%,#3C9BE8_55%,#1E4BB8_100%)] shadow-[0_10px_20px_rgba(30,75,184,0.18)]"
                style={{ height: `${Math.max(8, altura)}%` }}
              />
            </div>
            <div className="text-center">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{opcion.labels[indice]}</p>
              <p className="mt-1 text-xs font-semibold text-ink">{formatearValorPredeterminado(valor)} {opcion.unitLabel || ""}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GraficoHistograma({ opcion }) {
  const maximo = Math.max(...opcion.values, 1);

  return (
    <div className="flex h-72 items-end gap-3 rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] px-4 py-5">
      {opcion.values.map((valor, indice) => {
        const altura = (valor / maximo) * 100;
        return (
          <div key={`${opcion.labels[indice]}-${indice}`} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <div className="flex h-full w-full items-end">
              <div
                className="w-full rounded-t-2xl bg-[linear-gradient(180deg,#B7F4D6_0%,#5CC49D_55%,#1F7F8F_100%)] shadow-[0_10px_20px_rgba(31,127,143,0.18)]"
                style={{ height: `${Math.max(8, altura)}%` }}
              />
            </div>
            <div className="text-center">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{opcion.labels[indice]}</p>
              <p className="mt-1 text-xs font-semibold text-ink">{formatearValorPredeterminado(valor)} casos</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GraficoLineas({ opcion }) {
  const puntos = useMemo(() => construirRutaLinea(opcion.values), [opcion.values]);
  const maximo = Math.max(...opcion.values, 1);
  const minimo = Math.min(...opcion.values, 0);
  const rango = maximo - minimo || 1;

  return (
    <div className="rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] p-4">
      <svg viewBox="0 0 100 100" className="h-72 w-full overflow-visible">
        <defs>
          <linearGradient id="degradado-linea-dashboard" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#7BC9FF" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#7BC9FF" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={`${puntos} L 100 100 L 0 100 Z`} fill="url(#degradado-linea-dashboard)" />
        <path d={puntos} fill="none" stroke="#1E4BB8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {opcion.values.map((valor, indice) => {
          const x = opcion.values.length === 1 ? 50 : (indice / (opcion.values.length - 1)) * 100;
          const y = 92 - (((valor - minimo) / rango) * 72);
          return (
            <g key={`${opcion.labels[indice]}-${indice}`}>
              <circle cx={x} cy={y} r="2.8" fill="#1E4BB8" stroke="#FFFFFF" strokeWidth="1.4" />
              <text x={x} y="98" textAnchor="middle" fontSize="4" fill="#64748B">{opcion.labels[indice]}</text>
            </g>
          );
        })}
      </svg>
      <div className="-mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {opcion.values.map((valor, indice) => (
          <div key={`${opcion.labels[indice]}-${indice}-leyenda`} className="rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{opcion.labels[indice]}</p>
            <p className="mt-1 text-sm font-semibold text-ink">{formatearValorPredeterminado(valor)} {opcion.unitLabel || ""}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function GraficoDonut({ opcion }) {
  const total = opcion.slices.reduce((suma, segmento) => suma + Number(segmento.value || 0), 0) || 1;
  let acumulado = 0;

  const segmentos = opcion.slices
    .map((segmento) => {
      const inicio = (acumulado / total) * 100;
      acumulado += Number(segmento.value || 0);
      const fin = (acumulado / total) * 100;
      return `${segmento.color} ${inicio}% ${fin}%`;
    })
    .join(", ");

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(240px,0.9fr)_minmax(0,1.1fr)]">
      <div className="flex items-center justify-center rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] p-6">
        <div className="relative flex h-64 w-64 items-center justify-center rounded-full" style={{ background: `conic-gradient(${segmentos})` }}>
          <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full border border-[#E6ECF6] bg-white shadow-[0_12px_30px_rgba(11,27,43,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Total</p>
            <p className="mt-1 font-display text-3xl font-semibold text-ink">{formatearValorPredeterminado(total)}</p>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        <LeyendaGrafico opcion={opcion} />
      </div>
    </div>
  );
}

function CuerpoGrafico({ opcion }) {
  if (opcion.kind === "bar") {
    return <GraficoBarras opcion={opcion} />;
  }

  if (opcion.kind === "histogram") {
    return <GraficoHistograma opcion={opcion} />;
  }

  if (opcion.kind === "line") {
    return <GraficoLineas opcion={opcion} />;
  }

  return <GraficoDonut opcion={opcion} />;
}

export default function PanelGraficoDashboard({ title, description, options, defaultKey }) {
  const claveInicial = defaultKey || options[0]?.key || "";
  const [claveSeleccionada, setClaveSeleccionada] = useState(claveInicial);

  useEffect(() => {
    const tieneClave = options.some((opcion) => opcion.key === claveSeleccionada);
    if (!tieneClave) {
      setClaveSeleccionada(claveInicial);
    }
  }, [claveInicial, options, claveSeleccionada]);

  const opcionActiva = useMemo(() => {
    return options.find((opcion) => opcion.key === claveSeleccionada) || options[0];
  }, [options, claveSeleccionada]);

  if (!opcionActiva) {
    return null;
  }

  return (
    <section className="glass-panel p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="tag">Analitica visual</p>
          <h3 className="mt-3 font-display text-2xl font-semibold text-ink">{title}</h3>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">{description}</p>
        </div>
        <div className="w-full max-w-sm">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo de grafico</label>
          <select className="input-field mt-2" value={claveSeleccionada} onChange={(evento) => setClaveSeleccionada(evento.target.value)}>
            {options.map((opcion) => (
              <option key={opcion.key} value={opcion.key}>
                {opcion.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.45fr)]">
        <div>
          <CuerpoGrafico opcion={opcionActiva} />
        </div>
        <aside className="rounded-[28px] border border-[#E6ECF6] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Datos utiles</p>
          <p className="mt-2 text-sm text-slate-600">{opcionActiva.description}</p>
          <div className="mt-4 space-y-2">
            {(opcionActiva.insights || []).map((perspectiva) => (
              <div key={perspectiva} className="rounded-2xl border border-[#E6ECF6] bg-[#FBFCFF] px-3 py-2 text-sm text-slate-700">
                {perspectiva}
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3 text-sm text-slate-600">
            <p className="font-semibold text-ink">Sugerencia</p>
            <p className="mt-1">Este grafico ayuda a comparar volumen, concentracion y tendencia segun el tipo de datos que quieras analizar.</p>
          </div>
          <div className="mt-4">
            <LeyendaGrafico opcion={opcionActiva} />
          </div>
        </aside>
      </div>
    </section>
  );
}
