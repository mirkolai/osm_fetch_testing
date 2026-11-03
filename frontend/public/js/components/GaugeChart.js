const SVG_NS = 'http://www.w3.org/2000/svg';
const RANGE = 100; // il quadrante copre da -100% a +100% rispetto alla media
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

const formatSigned = (percent) => `${percent > 0 ? '+' : ''}${percent}%`;

/**
 * Indice sintetico = media tra Accessibilità ai POI e Connettività (closeness).
 * Il gauge mostra di quanto l'indice della via si discosta da quello della media cittadina.
 */
export function computeGaugeDifference(values, averages) {
    if (!values || !averages) {
        return null;
    }
    const streetIndex = (clamp01(values.poi_accessibility) + clamp01(values.closeness)) / 2;
    const cityIndex = (clamp01(averages.poi_accessibility) + clamp01(averages.closeness)) / 2;
    if (!Number.isFinite(cityIndex) || cityIndex <= 0) {
        return null;
    }
    return {
        streetIndex,
        cityIndex,
        percent: ((streetIndex - cityIndex) / cityIndex) * 100,
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
    title.textContent = 'Confronto complessivo con la media della città';

    const subtitle = document.createElement('div');
    subtitle.className = 'gauge-subtitle';
    subtitle.textContent = 'Accessibilità ai POI e Connettività combinate in un unico indice';

    const svg = el('svg', {
        viewBox: '0 0 300 205',
        class: 'gauge-svg',
        role: 'img',
        'aria-label': `Questo indirizzo è ${Math.abs(percent)}% ${percent >= 0 ? 'migliore' : 'peggiore'} della media cittadina`,
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
        svg.appendChild(buildText(tick === 0 ? '0%' : formatSigned(tick), x, y + 4, { size: 11, color: '#666' }));
    });

    // Tacca nera sulla media cittadina (0%).
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

    svg.appendChild(buildText(formatSigned(percent), CX, CY + 36, { size: 26, weight: 700, color: band.color === '#e9d85a' ? '#8a7d1f' : band.color }));
    svg.appendChild(buildText('rispetto alla media città', CX, CY + 52, { size: 12, color: '#555' }));

    const caption = document.createElement('div');
    caption.className = 'gauge-caption';
    const verdict = percent === 0
        ? 'in linea con la media della città'
        : `${Math.abs(percent)}% ${percent > 0 ? 'migliore' : 'peggiore'} rispetto alla media della città`;
    caption.textContent = `Questo indirizzo è ${verdict} `
        + `(indice ${Math.round(result.streetIndex * 100)}% contro ${Math.round(result.cityIndex * 100)}%).`;

    container.appendChild(title);
    container.appendChild(subtitle);
    container.appendChild(svg);
    container.appendChild(caption);
}
