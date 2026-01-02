/**
 * Panel d'affichage de la comparaison baseline vs event
 */
import { createElement } from '../../../shared/utils/dom.js';
import { Card } from '../../../shared/components/Card.js';
import { formatEuro, formatKwh, formatPercent, formatDurationHuman, formatDeltaWithSign, getVarianceClass } from '../logic/formatters.js';

export class ComparisonPanel {
    constructor(state) {
        this.state = state;
        this.container = null;
    }

    render(data) {
        this.container = createElement('div', { class: 'history-comparison-panel' });

        if (!data) {
            this.container.appendChild(
                createElement('p', { textContent: 'Aucune donnée disponible', class: 'empty-state' })
            );
            return this.container;
        }

        const { meta, comparison } = data;

        const header = this.renderHeader(meta);
        this.container.appendChild(header);

        const totalCard = this.renderTotalComparison(comparison.total, meta);
        this.container.appendChild(totalCard);

        if (comparison.focus_entity) {
            const focusCard = this.renderFocusComparison(comparison.focus_entity, meta);
            this.container.appendChild(focusCard);
        }

        if (comparison.extremes?.max_delta_entity) {
            const extremeCard = this.renderExtreme(comparison.extremes.max_delta_entity);
            this.container.appendChild(extremeCard);
        }

        return this.container;
    }

    renderHeader(meta) {
        const header = createElement('div', { class: 'comparison-header' });
        const title = createElement('h3', { textContent: 'Résultats de l\'analyse' });
        header.appendChild(title);

        const info = createElement('div', { class: 'meta-info' });
        info.innerHTML = `
            <span class="meta-item">
                <strong>${meta.entity_count}</strong> capteur${meta.entity_count > 1 ? 's' : ''}
            </span>
            <span class="meta-item">
                <strong>Période de référence:</strong> ${formatDurationHuman(meta.baseline_duration_s)}
            </span>
            <span class="meta-item">
                <strong>Période analysée:</strong> ${formatDurationHuman(meta.event_duration_s)}
            </span>
            ${!meta.normalized_supported ? '<span class="meta-warning">⚠️ Périodes trop courtes (&lt;1h) - normalisation limitée</span>' : ''}
        `;
        header.appendChild(info);

        return header;
    }

    renderTotalComparison(total, meta) {
        const content = createElement('div', { class: 'comparison-content' });

        const deltaCost = formatDeltaWithSign(total.delta_cost_ttc, formatEuro);
        const pctClass = getVarianceClass(total.pct_cost_ttc);

        content.innerHTML = `
            <div class="comparison-grid">
                <div class="comparison-column baseline">
                    <h4>📅 Période de référence</h4>
                    <div class="value-main">${formatEuro(total.baseline_cost_ttc)}</div>
                    <div class="value-secondary">${formatKwh(total.baseline_energy_kwh)}</div>
                    ${meta.normalized_supported ? `
                        <div class="value-normalized">
                            <strong>Par jour:</strong> ${formatEuro(total.baseline_cost_ttc_per_day)}
                        </div>
                    ` : ''}
                </div>

                <div class="comparison-column event">
                    <h4>🎯 Période analysée</h4>
                    <div class="value-main">${formatEuro(total.event_cost_ttc)}</div>
                    <div class="value-secondary">${formatKwh(total.event_energy_kwh)}</div>
                    ${meta.normalized_supported ? `
                        <div class="value-normalized">
                            <strong>Par jour:</strong> ${formatEuro(total.event_cost_ttc_per_day)}
                        </div>
                    ` : ''}
                </div>

                <div class="comparison-column delta ${deltaCost.color}">
                    <h4>📊 Évolution</h4>
                    <div class="value-main">${deltaCost.text}</div>
                    <div class="value-secondary">${formatDeltaWithSign(total.delta_energy_kwh, formatKwh).text}</div>
                    <div class="badge badge-${pctClass}">${formatPercent(total.pct_cost_ttc)}</div>
                    ${meta.normalized_supported ? `
                        <div class="value-normalized">
                            <strong>Par jour:</strong> ${formatDeltaWithSign(total.delta_cost_ttc_per_day, formatEuro).text}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        const card = Card.create('📊 Total (tous capteurs)', content);
        card.classList.add('comparison-card', 'total-card');
        return card;
    }

    renderFocusComparison(focus, meta) {
        const content = createElement('div', { class: 'comparison-content' });

        const deltaCost = formatDeltaWithSign(focus.delta_cost_ttc, formatEuro);
        const pctClass = getVarianceClass(focus.pct_cost_ttc);

        content.innerHTML = `
            <div class="comparison-grid">
                <div class="comparison-column baseline">
                    <h4>📅 Période de référence</h4>
                    <div class="value-main">${formatEuro(focus.baseline_cost_ttc)}</div>
                    <div class="value-secondary">${formatKwh(focus.baseline_energy_kwh)}</div>
                </div>

                <div class="comparison-column event">
                    <h4>🎯 Période analysée</h4>
                    <div class="value-main">${formatEuro(focus.event_cost_ttc)}</div>
                    <div class="value-secondary">${formatKwh(focus.event_energy_kwh)}</div>
                </div>

                <div class="comparison-column delta ${deltaCost.color}">
                    <h4>📊 Évolution</h4>
                    <div class="value-main">${deltaCost.text}</div>
                    <div class="value-secondary">${formatDeltaWithSign(focus.delta_energy_kwh, formatKwh).text}</div>
                    <div class="badge badge-${pctClass}">${formatPercent(focus.pct_cost_ttc)}</div>
                </div>
            </div>
        `;

        const card = Card.create(`🎯 Focus: ${focus.display_name}`, content);
        card.classList.add('comparison-card', 'focus-card');
        return card;
    }

    renderExtreme(extreme) {
        const content = createElement('div', { class: 'extreme-content' });

        const deltaCost = formatDeltaWithSign(extreme.delta_cost_ttc, formatEuro);

        content.innerHTML = `
            <div class="extreme-info">
                <strong>${extreme.display_name}</strong>
                <span class="entity-id-small">${extreme.entity_id}</span>
            </div>
            <div class="extreme-delta ${deltaCost.color}">
                ${deltaCost.text}
            </div>
        `;

        const card = Card.create('🔥 Plus grande variation', content);
        card.classList.add('comparison-card', 'extreme-card');
        return card;
    }
}
