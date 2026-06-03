import { useEffect, useMemo, useState } from "react";

function formatDefaultValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0";
  }
  return new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 }).format(Number(value));
}

function buildLinePath(values) {
  if (!values.length) {
    return "";
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;

  return values
    .map((value, index) => {
      const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
      const y = 92 - (((value - min) / span) * 72);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function ChartLegend({ option }) {
  if (option.kind === "donut") {
    return (
      <div className="space-y-2">
        {option.slices.map((slice) => (
          <div key={slice.label} className="flex items-center justify-between gap-3 rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: slice.color }} />
              <span className="font-medium text-slate-700">{slice.label}</span>
            </div>
            <span className="font-semibold text-ink">{formatDefaultValue(slice.value)}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {option.labels.map((label, index) => (
        <div key={label} className="rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {formatDefaultValue(option.values[index])} {option.unitLabel || ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function BarChart({ option }) {
  const max = Math.max(...option.values, 1);

  return (
    <div className="flex h-72 items-end gap-3 rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] px-4 py-5">
      {option.values.map((value, index) => {
        const height = (value / max) * 100;
        return (
          <div key={`${option.labels[index]}-${index}`} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <div className="flex h-full w-full items-end">
              <div
                className="w-full rounded-t-2xl bg-[linear-gradient(180deg,#7BC9FF_0%,#3C9BE8_55%,#1E4BB8_100%)] shadow-[0_10px_20px_rgba(30,75,184,0.18)]"
                style={{ height: `${Math.max(8, height)}%` }}
              />
            </div>
            <div className="text-center">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{option.labels[index]}</p>
              <p className="mt-1 text-xs font-semibold text-ink">{formatDefaultValue(value)} {option.unitLabel || ""}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function HistogramChart({ option }) {
  const max = Math.max(...option.values, 1);

  return (
    <div className="flex h-72 items-end gap-3 rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] px-4 py-5">
      {option.values.map((value, index) => {
        const height = (value / max) * 100;
        return (
          <div key={`${option.labels[index]}-${index}`} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
            <div className="flex h-full w-full items-end">
              <div
                className="w-full rounded-t-2xl bg-[linear-gradient(180deg,#B7F4D6_0%,#5CC49D_55%,#1F7F8F_100%)] shadow-[0_10px_20px_rgba(31,127,143,0.18)]"
                style={{ height: `${Math.max(8, height)}%` }}
              />
            </div>
            <div className="text-center">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{option.labels[index]}</p>
              <p className="mt-1 text-xs font-semibold text-ink">{formatDefaultValue(value)} casos</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LineChart({ option }) {
  const points = useMemo(() => buildLinePath(option.values), [option.values]);
  const max = Math.max(...option.values, 1);
  const min = Math.min(...option.values, 0);
  const span = max - min || 1;

  return (
    <div className="rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] p-4">
      <svg viewBox="0 0 100 100" className="h-72 w-full overflow-visible">
        <defs>
          <linearGradient id="dashboard-line-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#7BC9FF" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#7BC9FF" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={`${points} L 100 100 L 0 100 Z`} fill="url(#dashboard-line-gradient)" />
        <path d={points} fill="none" stroke="#1E4BB8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {option.values.map((value, index) => {
          const x = option.values.length === 1 ? 50 : (index / (option.values.length - 1)) * 100;
          const y = 92 - (((value - min) / span) * 72);
          return (
            <g key={`${option.labels[index]}-${index}`}>
              <circle cx={x} cy={y} r="2.8" fill="#1E4BB8" stroke="#FFFFFF" strokeWidth="1.4" />
              <text x={x} y="98" textAnchor="middle" fontSize="4" fill="#64748B">{option.labels[index]}</text>
            </g>
          );
        })}
      </svg>
      <div className="-mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {option.values.map((value, index) => (
          <div key={`${option.labels[index]}-${index}-legend`} className="rounded-2xl border border-[#E6ECF6] bg-white/80 px-3 py-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{option.labels[index]}</p>
            <p className="mt-1 text-sm font-semibold text-ink">{formatDefaultValue(value)} {option.unitLabel || ""}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function DonutChart({ option }) {
  const total = option.slices.reduce((sum, slice) => sum + Number(slice.value || 0), 0) || 1;
  let accumulated = 0;

  const segments = option.slices
    .map((slice) => {
      const start = (accumulated / total) * 100;
      accumulated += Number(slice.value || 0);
      const end = (accumulated / total) * 100;
      return `${slice.color} ${start}% ${end}%`;
    })
    .join(", ");

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(240px,0.9fr)_minmax(0,1.1fr)]">
      <div className="flex items-center justify-center rounded-[28px] border border-[#E6ECF6] bg-[#FBFCFF] p-6">
        <div className="relative flex h-64 w-64 items-center justify-center rounded-full" style={{ background: `conic-gradient(${segments})` }}>
          <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full border border-[#E6ECF6] bg-white shadow-[0_12px_30px_rgba(11,27,43,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Total</p>
            <p className="mt-1 font-display text-3xl font-semibold text-ink">{formatDefaultValue(total)}</p>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        <ChartLegend option={option} />
      </div>
    </div>
  );
}

function ChartBody({ option }) {
  if (option.kind === "bar") {
    return <BarChart option={option} />;
  }

  if (option.kind === "histogram") {
    return <HistogramChart option={option} />;
  }

  if (option.kind === "line") {
    return <LineChart option={option} />;
  }

  return <DonutChart option={option} />;
}

export default function DashboardChartPanel({ title, description, options, defaultKey }) {
  const initialKey = defaultKey || options[0]?.key || "";
  const [selectedKey, setSelectedKey] = useState(initialKey);

  useEffect(() => {
    const hasCurrent = options.some((option) => option.key === selectedKey);
    if (!hasCurrent) {
      setSelectedKey(initialKey);
    }
  }, [initialKey, options, selectedKey]);

  const activeOption = useMemo(() => {
    return options.find((option) => option.key === selectedKey) || options[0];
  }, [options, selectedKey]);

  if (!activeOption) {
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
          <select className="input-field mt-2" value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
            {options.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.45fr)]">
        <div>
          <ChartBody option={activeOption} />
        </div>
        <aside className="rounded-[28px] border border-[#E6ECF6] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Datos utiles</p>
          <p className="mt-2 text-sm text-slate-600">{activeOption.description}</p>
          <div className="mt-4 space-y-2">
            {(activeOption.insights || []).map((insight) => (
              <div key={insight} className="rounded-2xl border border-[#E6ECF6] bg-[#FBFCFF] px-3 py-2 text-sm text-slate-700">
                {insight}
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-[#E6ECF6] bg-[#F8FAFF] px-4 py-3 text-sm text-slate-600">
            <p className="font-semibold text-ink">Sugerencia</p>
            <p className="mt-1">Este grafico ayuda a comparar volumen, concentracion y tendencia segun el tipo de datos que quieras analizar.</p>
          </div>
          <div className="mt-4">
            <ChartLegend option={activeOption} />
          </div>
        </aside>
      </div>
    </section>
  );
}
