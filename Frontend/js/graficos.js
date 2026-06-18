/**
 * Generacion de graficos SVG sin librerias externas.
 * Soporta: barras, dona, lineas.
 */

const COLORES = ["#d97706", "#ea580c", "#78350f", "#a16207", "#f59e0b", "#92400e", "#f97316", "#451a03"];

const Graficos = {
  /**
   * Grafico de barras horizontales.
   * @param {string} idContenedor - ID del elemento contenedor
   * @param {Array} datos - Array de {etiqueta, valor, color?}
   * @param {string} titulo - Titulo del grafico
   */
  barras: function (idContenedor, datos, titulo = "") {
    const contenedor = document.getElementById(idContenedor);
    if (!contenedor || !datos || datos.length === 0) return;

    const maxValor = Math.max(...datos.map((d) => d.valor), 1);
    let html = `<div class="grafico-contenedor">`;
    if (titulo) html += `<h3>${titulo}</h3>`;

    datos.forEach((d, i) => {
      const porcentaje = (d.valor / maxValor) * 100;
      const color = d.color || COLORES[i % COLORES.length];
      html += `
        <div class="grafico-barra-item">
          <span class="etiqueta-graf" title="${d.etiqueta}">${this._truncar(d.etiqueta, 18)}</span>
          <div class="barra">
            <div class="relleno" style="width:${porcentaje}%; background:${color};"></div>
          </div>
          <span class="valor-graf">${this._formatearValor(d.valor)}</span>
        </div>
      `;
    });

    html += `</div>`;
    contenedor.innerHTML = html;
  },

  /**
   * Grafico de dona.
   * @param {string} idContenedor
   * @param {Array} segmentos - Array de {etiqueta, valor, color?}
   * @param {string} titulo
   */
  dona: function (idContenedor, segmentos, titulo = "") {
    const contenedor = document.getElementById(idContenedor);
    if (!contenedor || !segmentos || segmentos.length === 0) return;

    const total = segmentos.reduce((s, seg) => s + seg.valor, 0) || 1;
    let conicGradients = [];
    let acumulado = 0;

    segmentos.forEach((seg, i) => {
      const color = seg.color || COLORES[i % COLORES.length];
      const porcentaje = (seg.valor / total) * 100;
      const inicio = acumulado;
      const fin = acumulado + porcentaje;
      conicGradients.push(`${color} ${inicio}% ${fin}%`);
      acumulado = fin;
    });

    let html = `<div class="grafico-contenedor">`;
    if (titulo) html += `<h3>${titulo}</h3>`;
    html += `<div class="dona-contenedor">`;
    html += `<div class="dona" style="background: conic-gradient(${conicGradients.join(", ")})"></div>`;
    html += `<div class="dona-leyenda">`;

    segmentos.forEach((seg, i) => {
      const color = seg.color || COLORES[i % COLORES.length];
      const porcentaje = ((seg.valor / total) * 100).toFixed(1);
      html += `
        <div class="dona-leyenda-item">
          <span class="color" style="background:${color}"></span>
          <span>${seg.etiqueta}: ${porcentaje}%</span>
        </div>
      `;
    });

    html += `</div></div></div>`;
    contenedor.innerHTML = html;
  },

  /**
   * Grafico de lineas SVG con soporte para multiples series.
   * @param {string} idContenedor
   * @param {Array} series - Array de {etiqueta, valores: [{etiqueta, valor}], color?}
   * @param {string} titulo
   * @param {number} alto - Alto del SVG en px
   */
  lineas: function (idContenedor, series, titulo = "", alto = 200) {
    const contenedor = document.getElementById(idContenedor);
    if (!contenedor || !series || series.length === 0) return;

    const todosPuntos = series.flatMap(s => s.valores);
    if (todosPuntos.length < 2) return;

    const maxValor = Math.max(...todosPuntos.map((p) => p.valor), 1);
    const ancho = contenedor.clientWidth || 600;
    const padding = { top: 20, right: 20, bottom: 40, left: 55 };
    const anchoUtil = ancho - padding.left - padding.right;
    const altoUtil = alto - padding.top - padding.bottom;

    const etiquetasX = series[0].valores.map(p => p.etiqueta);
    const pasoX = anchoUtil / Math.max(etiquetasX.length - 1, 1);

    let html = `<div class="grafico-contenedor">`;
    if (titulo) html += `<h3>${titulo}</h3>`;
    html += `<svg width="${ancho}" height="${alto}" style="max-width:100%;">`;

    // Ejes
    html += `<line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + altoUtil}" stroke="#d4d4d8" stroke-width="1"/>`;
    html += `<line x1="${padding.left}" y1="${padding.top + altoUtil}" x2="${padding.left + anchoUtil}" y2="${padding.top + altoUtil}" stroke="#d4d4d8" stroke-width="1"/>`;

    // Cada serie
    series.forEach((serie, sIdx) => {
      const color = serie.color || COLORES[sIdx % COLORES.length];
      const pts = serie.valores;
      let pathD = "";

      pts.forEach((p, i) => {
        const x = padding.left + i * pasoX;
        const y = padding.top + altoUtil - (p.valor / maxValor) * altoUtil;
        if (i === 0) pathD += `M ${x} ${y}`;
        else pathD += ` L ${x} ${y}`;
        // Puntos
        html += `<circle cx="${x}" cy="${y}" r="3.5" fill="${color}" stroke="white" stroke-width="1.5">
          <title>${serie.etiqueta}: ${p.etiqueta} - ${this._formatearValor(p.valor)}</title>
        </circle>`;
      });

      // Area bajo la primera serie
      if (sIdx === 0) {
        const ultimoX = padding.left + (pts.length - 1) * pasoX;
        const ultimoY = padding.top + altoUtil - (pts[pts.length - 1].valor / maxValor) * altoUtil;
        const areaD = pathD + ` L ${ultimoX} ${padding.top + altoUtil} L ${padding.left} ${padding.top + altoUtil} Z`;
        html += `<path d="${areaD}" fill="${color}15" stroke="none"/>`;
      }

      html += `<path d="${pathD}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" opacity="0.9"/>`;
    });

    // Etiquetas en eje X
    etiquetasX.forEach((et, i) => {
      if (i % Math.ceil(etiquetasX.length / 6) === 0 || i === etiquetasX.length - 1) {
        const x = padding.left + i * pasoX;
        html += `<text x="${x}" y="${alto - 10}" text-anchor="middle" font-size="11" fill="#78716c">${et}</text>`;
      }
    });

    // Leyenda
    if (series.length > 1) {
      const leyendaX = padding.left + 10;
      let leyendaY = padding.top + 5;
      html += `<g font-size="11" fill="#292524">`;
      series.forEach((serie, sIdx) => {
        const color = serie.color || COLORES[sIdx % COLORES.length];
        html += `<rect x="${leyendaX}" y="${leyendaY}" width="12" height="3" fill="${color}" rx="1.5"/>`;
        html += `<text x="${leyendaX + 18}" y="${leyendaY + 4}" fill="#78716c">${serie.etiqueta}</text>`;
        leyendaY += 16;
      });
      html += `</g>`;
    }

    html += `</svg></div>`;
    contenedor.innerHTML = html;
  },

  _truncar(texto, maximo) {
    if (!texto) return "";
    return texto.length > maximo ? texto.substring(0, maximo) + "..." : texto;
  },

  _formatearValor(valor) {
    if (typeof valor === "number") {
      if (valor >= 1000000) return (valor / 1000000).toFixed(1) + "M";
      if (valor >= 1000) return (valor / 1000).toFixed(1) + "K";
      return valor.toFixed(0);
    }
    return valor;
  },
};
