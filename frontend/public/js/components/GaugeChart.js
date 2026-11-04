const SVG_NS = 'http://www.w3.org/2000/svg';
const RANGE = 100; // il quadrante va da -100 a +100, con 0 sulla mediana della città
const CX = 150;
const CY = 140;
const R_OUTER = 120;
const R_INNER = 78;

const BANDS = [
    { from: -100, to: -60, color: '#d9534f', label: 'Molto peggiore' },
    { from: -60, to: -20, color: '#f0ad4e', label: 'Peggiore' },
    { from: -20, to: 20, color: '#e9d85a', label: 'In linea' },
    { from: 20, to: 60, color: '#8cc16a', label: 'Migliore' },
    { from: 60, to: 100, color: '#3f9b4f', label: 'Molto migliore' },
];

const clamp01 = (value) => Math.max(0, Math.min(Number(value) || 0, 1));

const el = (name, attrs = {}) => {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
};

// Percentuale (-RANGE..+RANGE) -> angolo in radianti (da PI a 0, da sinistra a destra).
const toAngle = (percent) => {
    const clamped = Math.max(-RANGE, Math.min(percent, RANGE));
    return Math.PI * (1 - (clamped + RANGE) / (2 * RANGE));
};

const point = (radius, angle) => [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)];

function arcPath(fromPercent, toPercent) {
    const a1 = toAngle(fromPercent);
    const a2 = toAngle(toPercent);
    const [x1, y1] = point(R_OUTER, a1);
    const [x2, y2] = point(R_OUTER, a2);
    const [x3, y3] = point(R_INNER, a2);
    const [x4, y4] = point(R_INNER, a1);
    return `M ${x1} ${y1} A ${R_OUTER} ${R_OUTER} 0 0 1 ${x2} ${y2} L ${x3} ${y3} A ${R_INNER} ${R_INNER} 0 0 0 ${x4} ${y4} Z`;
}

function buildText(content, x, y, { size = 12, weight = 400, color = '#333', anchor = 'middle' } = {}) {
    const text = el('text', {
        x,
        y,
        'text-anchor': anchor,
        'font-size': size,
        'font-weight': weight,
        fill: color,
    });
    text.textContent = content;
    return text;
}

const formatSigned = (value) => `${value > 0 ? '+' : ''}${value}`;

// Posizioni sul quadrante dei percentili 5, 20, 40, 50, 60, 80, 95 dell'indice cittadino:
// i limiti dei quintili coincidono con i confini delle fasce colorate.
const SCALE_POSITIONS = [-100, -60, -20, 0, 20, 60, 100];

// Interpolazione lineare a tratti dell'indice sui nodi della scala (-100..+100).
function interpolateOnScale(value, knots) {
    if (value <= knots[0]) {
        return SCALE_POSITIONS[0];
    }
    for (let i = 1; i < knots.length; i += 1) {
        if (value <= knots[i]) {
            const width = knots[i] - knots[i - 1];
            if (width <= 0) {
                return SCALE_POSITIONS[i];
            }
            const t = (value - knots[i - 1]) / width;
            return SCALE_POSITIONS[i - 1] + t * (SCALE_POSITIONS[i] - SCALE_POSITIONS[i - 1]);
        }
    }
    return SCALE_POSITIONS[SCALE_POSITIONS.length - 1];
}

/**
 * Indice sintetico = media tra Accessibilità ai POI e Connettività (closeness).
 * La scala del gauge deriva dalla distribuzione dello stesso indice sul campione di nodi
 * della città: 0 = mediana, estremi = 5° e 95° percentile, fasce = quintili.
 */
export function computeGaugeDifference(values, averages) {
    if (!values || !averages) {
        return null;
    }
    const scale = averages.gauge_scale;
    if (!scale || !Array.isArray(scale.knots) || scale.knots.length !== SCALE_POSITIONS.length) {
        return null;
    }
    const streetIndex = (clamp01(values.poi_accessibility) + clamp01(values.closeness)) / 2;
    const medianIndex = scale.knots[3];
    const sample = Array.isArray(scale.sample_indices) ? scale.sample_indices : [];
    const rank = sample.length
        ? (sample.filter((v) => v <= streetIndex + 1e-9).length / sample.length) * 100
        : null;
    return {
        streetIndex,
        cityIndex: medianIndex,
        percent: interpolateOnScale(streetIndex, scale.knots),
        rank,
    };
}

export function renderGaugeChart(containerId, values, averages) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.replaceChildren();

    const result = computeGaugeDifference(values, averages);
    if (!result) {
        container.style.display = 'none';
        return;
    }
    container.style.display = '';

    const percent = Math.round(result.percent);
    const band = BANDS.find((b) => result.percent >= b.from && result.percent < b.to)
        || (result.percent < 0 ? BANDS[0] : BANDS[BANDS.length - 1]);

    const title = document.createElement('div');
    title.className = 'gauge-title';
    title.textContent = 'Confronto complessivo con la città';

    const subtitle = document.createElement('div');
    subtitle.className = 'gauge-subtitle';
    subtitle.textContent = 'Accessibilità ai POI e Connettività combinate in un unico indice';

    const svg = el('svg', {
        viewBox: '0 0 300 205',
        class: 'gauge-svg',
        role: 'img',
        'aria-label': `Posizione sul quadrante: ${formatSigned(percent)} rispetto alla mediana cittadina (${band.label})`,
    });

    // Le fasce sono colorate solo fino alla lancetta; il resto resta grigio.
    BANDS.forEach((b) => {
        const track = el('path', { d: arcPath(b.from, b.to), fill: '#e5e7eb', stroke: '#fff', 'stroke-width': 2 });
        const tip = el('title');
        tip.textContent = b.label;
        track.appendChild(tip);
        svg.appendChild(track);

        const reachedTo = Math.min(b.to, result.percent);
        if (reachedTo > b.from) {
            svg.appendChild(el('path', { d: arcPath(b.from, reachedTo), fill: b.color, stroke: '#fff', 'stroke-width': 2 }));
        }
    });

    [-100, -60, -20, 0, 20, 60, 100].forEach((tick) => {
        const [x, y] = point(R_OUTER + 14, toAngle(tick));
        svg.appendChild(buildText(tick === 0 ? '0' : formatSigned(tick), x, y + 4, { size: 11, color: '#666' }));
    });

    // Tacca nera sulla mediana cittadina (0).
    const [mx1, my1] = point(R_INNER - 4, toAngle(0));
    const [mx2, my2] = point(R_OUTER + 4, toAngle(0));
    svg.appendChild(el('line', { x1: mx1, y1: my1, x2: mx2, y2: my2, stroke: '#000', 'stroke-width': 3 }));

    // Lancetta: ruota da -90° (sinistra) a +90° (destra) rispetto alla verticale.
    const needleAngle = toAngle(result.percent);
    const [nx, ny] = point(R_OUTER - 14, needleAngle);
    const needle = el('line', {
        x1: CX,
        y1: CY,
        x2: nx,
        y2: ny,
        stroke: '#333',
        'stroke-width': 4,
        'stroke-linecap': 'round',
    });
    svg.appendChild(needle);
    svg.appendChild(el('circle', { cx: CX, cy: CY, r: 9, fill: '#333' }));

    svg.appendChild(buildText(band.label, CX, CY + 36, { size: 22, weight: 700, color: band.color === '#e9d85a' ? '#8a7d1f' : band.color }));
    svg.appendChild(buildText('rispetto alla mediana della città', CX, CY + 52, { size: 12, color: '#555' }));

    const caption = document.createElement('div');
    caption.className = 'gauge-caption';
    const rankText = result.rank === null
        ? ''
        : `, meglio di circa il ${Math.round(result.rank)}% delle vie del campione cittadino`;
    caption.textContent = `Questo indirizzo è classificato "${band.label.toLowerCase()}"${rankText} `
        + `(indice ${Math.round(result.streetIndex * 100)}% contro una mediana di ${Math.round(result.cityIndex * 100)}%).`;

    container.appendChild(title);
    container.appendChild(subtitle);
    container.appendChild(svg);
    container.appendChild(caption);
}
