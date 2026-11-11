const clamp01 = (value) => Math.max(0, Math.min(Number(value) || 0, 1));

// Stessa scala cromatica del gauge chart: 5 fasce da 20 punti percentuali.
const BAND_COLORS = ['#d9534f', '#f0ad4e', '#e9d85a', '#8cc16a', '#3f9b4f'];
const TICKS = [20, 40, 60, 80];

// Progress bar a termometro con marcatore verticale nero per la media cittadina.
function buildBar(label, value, average, color, { small = false } = {}) {

    const BAR_DESCRIPTIONS = {
        'Vicinanza (Prossimità)': 'Tempo necessario per raggiungere tutti i servizi essenziali.',
        'Quantità (Densità)': 'Numero di servizi presenti nell’area raggiungibile entro il tempo di percorrenza considerato.',
        'Varietà (Diversità)': 'Diversità delle tipologie di servizi disponibili, che misura la capacità dell’area di soddisfare esigenze differenti.',
        'Collegamento (Connettività)': 'Centralità della rete stradale, che esprime quanto rapidamente l’area è collegata al resto della rete urbana.',
        'Accessibilità ai servizi': 'Indicatore complessivo che sintetizza la facilità con cui è possibile raggiungere un’offerta ampia e diversificata di servizi.'
    };




    const row = document.createElement('div');
    row.className = `pbc-row${small ? ' pbc-row-small' : ''}`;

    const head = document.createElement('div');
    head.className = 'pbc-label';
    const percent = Math.round(clamp01(value) * 100);

    const labelText = document.createElement('span');
    labelText.textContent = `${label} (${percent}%)`;
    head.appendChild(labelText);

    if (BAR_DESCRIPTIONS[label]) {
        const info = document.createElement('span');
        info.className = 'pbc-info';
        info.textContent = 'ⓘ';
        info.title = BAR_DESCRIPTIONS[label];
        info.setAttribute('aria-label', BAR_DESCRIPTIONS[label]);
        head.appendChild(info);
    }

    const track = document.createElement('div');
    track.className = 'pbc-track';

    const fill = document.createElement('div');
    fill.className = 'pbc-fill';
    // Il riempimento è diviso in segmenti, ognuno col colore della propria fascia, fino al valore raggiunto.
    const reached = clamp01(value) * 100;
    BAND_COLORS.forEach((bandColor, index) => {
        const start = index * 20;
        const end = Math.min(start + 20, reached);
        if (end > start) {
            const segment = document.createElement('div');
            segment.className = 'pbc-segment';
            segment.style.left = `${start}%`;
            segment.style.width = `${end - start}%`;
            segment.style.background = bandColor;
            fill.appendChild(segment);
        }
    });
    track.appendChild(fill);

    TICKS.forEach((tick) => {
        const mark = document.createElement('div');
        mark.className = 'pbc-tick';
        mark.style.left = `${tick}%`;
        track.appendChild(mark);

        const tickLabel = document.createElement('span');
        tickLabel.className = 'pbc-tick-label';
        tickLabel.style.left = `${tick}%`;
        tickLabel.textContent = `${tick}%`;
        track.appendChild(tickLabel);
    });

    if (Number.isFinite(average)) {
        const marker = document.createElement('div');
        marker.className = 'pbc-avg';
        marker.style.setProperty('--avg', clamp01(average) * 100);
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


function buildInfoLabel(title, description) {
    const wrapper = document.createElement('span');
    wrapper.className = 'info-label';

    wrapper.textContent = title;

    const info = document.createElement('span');
    info.className = 'info-tooltip';
    info.textContent = 'ⓘ';
    info.title = description;

    wrapper.appendChild(info);

    return wrapper;
}



/**
 * values / averages: oggetti con proximity_score, density_score, entropy_score,
 * poi_accessibility, closeness. averages può essere null.
 */



export function renderProgressBarChart(containerId, values, averages, color = '#483d8b') {

    console.log('===== PROGRESS BAR CHART =====');
    console.log('Container:', containerId);
    console.log('Values:', values);
    console.log('Averages:', averages);

    console.log('Media accessibilità:',averages);
    console.log('Media prossimità:', averages);
    console.log('Media varietà:', averages);
    console.log('Media densità:', averages,);
    console.log('Media connettività:', averages);

    console.log('==============================');

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
        'Accessibilità ai servizi',
        clamp01(values.poi_accessibility),
        num(averages, 'poi_accessibility'),
        color,
    );
    accessibility.classList.add('pbc-hoverable');

    const details = document.createElement('div');
    details.className = 'pbc-details';
    details.appendChild(buildBar('Vicinanza (Prossimità)', prox(values), prox(averages), color, { small: true }));
    details.appendChild(buildBar('Varietà (Diversità)', clamp01(values.entropy_score), num(averages, 'entropy_score'), color, { small: true }));
    details.appendChild(buildBar('Quantità (Densità)', clamp01(values.density_score), num(averages, 'density_score'), color, { small: true }));
    const group = document.createElement('div');
    group.className = 'pbc-group';
    group.appendChild(accessibility);
    group.appendChild(details);

    container.appendChild(group);
    container.appendChild(buildBar('Collegamento (Connettività)', clamp01(values.closeness), num(averages, 'closeness'), color));

    const legend = document.createElement('div');
    legend.className = 'pbc-legend';
    legend.innerHTML = '<span class="pbc-avg-sample"></span> Media città';
    container.appendChild(legend);
}
