const clamp01 = (value) => Math.max(0, Math.min(Number(value) || 0, 1));

// Progress bar con marcatore verticale nero per la media cittadina.
function buildBar(label, value, average, color, { small = false } = {}) {
    const row = document.createElement('div');
    row.className = `pbc-row${small ? ' pbc-row-small' : ''}`;

    const head = document.createElement('div');
    head.className = 'pbc-label';
    const percent = Math.round(clamp01(value) * 100);
    head.textContent = `${label} (${percent}%)`;

    const track = document.createElement('div');
    track.className = 'pbc-track';

    const fill = document.createElement('div');
    fill.className = 'pbc-fill';
    fill.style.width = `${clamp01(value) * 100}%`;
    fill.style.background = color;
    track.appendChild(fill);

    if (Number.isFinite(average)) {
        const marker = document.createElement('div');
        marker.className = 'pbc-avg';
        marker.style.left = `${clamp01(average) * 100}%`;
        track.appendChild(marker);

        const v = clamp01(value);
        const a = clamp01(average);
        if (a > 0) {
            const diff = Math.round((Math.abs(v - a) / a) * 100);
            const verdict = v >= a ? 'migliore' : 'peggiore';
            row.title = `Questo indirizzo ha un valore di ${label}, ${verdict} del ${diff}% rispetto al resto della città (media ${Math.round(a * 100)}%)`;
        } else {
            row.title = `Questo indirizzo ha un valore di ${label}; la media della città è 0%`;
        }
    }

    row.appendChild(head);
    row.appendChild(track);
    return row;
}

/**
 * values / averages: oggetti con proximity_score, density_score, entropy_score,
 * poi_accessibility, closeness. averages può essere null.
 */
export function renderProgressBarChart(containerId, values, averages, color = '#483d8b') {
    const container = document.getElementById(containerId);
    if (!container || !values) {
        return;
    }
    container.replaceChildren();
    container.classList.add('pbc');

    // La prossimità è invertita: punteggio basso = più vicino = meglio.
    const prox = (p) => (p ? 1 - clamp01(p.proximity_score) : NaN);
    const num = (p, key) => (p && Number.isFinite(p[key]) ? clamp01(p[key]) : NaN);

    const accessibility = buildBar(
        'Accessibilità ai POI',
        clamp01(values.poi_accessibility),
        num(averages, 'poi_accessibility'),
        color,
    );
    accessibility.classList.add('pbc-hoverable');

    const details = document.createElement('div');
    details.className = 'pbc-details';
    details.appendChild(buildBar('Prossimità', prox(values), prox(averages), color, { small: true }));
    details.appendChild(buildBar('Varietà', clamp01(values.entropy_score), num(averages, 'entropy_score'), color, { small: true }));
    details.appendChild(buildBar('Densità', clamp01(values.density_score), num(averages, 'density_score'), color, { small: true }));

    const group = document.createElement('div');
    group.className = 'pbc-group';
    group.appendChild(accessibility);
    group.appendChild(details);

    container.appendChild(group);
    container.appendChild(buildBar('Connettività', clamp01(values.closeness), num(averages, 'closeness'), color));

    const legend = document.createElement('div');
    legend.className = 'pbc-legend';
    legend.innerHTML = '<span class="pbc-avg-sample"></span> Media città';
    container.appendChild(legend);
}
