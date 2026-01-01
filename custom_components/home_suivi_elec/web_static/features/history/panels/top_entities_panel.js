/**
 * Panel affichant le top N des capteurs responsables
 */
import { createElement } from '../../../shared/utils/dom.js';
import { Card } from '../../../shared/components/Card.js';
import { Table } from '../../../shared/components/Table.js';
import { formatEuro, formatKwh, formatPercent, formatDeltaWithSign, getVarianceClass } from '../logic/formatters.js';

export class TopEntitiesPanel {
    constructor(state) {
        this.state = state;
        this.container = null;
    }

    render(topEntities) {
        this.container = createElement('div', { class: 'history-top-entities-panel' });

        if (!topEntities || topEntities.length === 0) {
            this.container.appendChild(
                createElement('p', { textContent: 'Aucun capteur à afficher', class: 'empty-state' })
            );
            return this.container;
        }

        // ✅ CORRECTION : Prépare les données pour Table.create()
        const headers = ['#', 'Capteur', 'Baseline', 'Event', 'Différence', 'Variation'];
        const rows = topEntities.map((entity, index) => {
            const deltaCost = formatDeltaWithSign(entity.delta_cost_ttc, formatEuro);
            const pctClass = getVarianceClass(entity.pct_cost_ttc);

            return [
                index + 1,
                `<div class="sensor-cell">
                    <strong>${entity.display_name}</strong>
                    <span class="entity-id-small">${entity.entity_id}</span>
                </div>`,
                `<div class="cost-cell">
                    <div>${formatKwh(entity.baseline_energy_kwh)}</div>
                    <div class="cost-secondary">${formatEuro(entity.baseline_cost_ttc)}</div>
                </div>`,
                `<div class="cost-cell">
                    <div>${formatKwh(entity.event_energy_kwh)}</div>
                    <div class="cost-secondary">${formatEuro(entity.event_cost_ttc)}</div>
                </div>`,
                `<div class="delta-cell ${deltaCost.color}">
                    <div>${formatDeltaWithSign(entity.delta_energy_kwh, formatKwh).text}</div>
                    <div class="cost-secondary">${deltaCost.text}</div>
                </div>`,
                `<span class="badge badge-${pctClass}">${formatPercent(entity.pct_cost_ttc)}</span>`
            ];
        });

        // ✅ CORRECTION : Utilise Table.create() avec un tableau d'en-têtes et un tableau de lignes
        const table = Table.create(headers, rows);
        table.classList.add('top-entities-table');

        // ✅ CORRECTION : Utilise Card.create()
        const card = Card.create(`🏆 Top ${topEntities.length} des capteurs responsables`, table);
        card.classList.add('top-entities-card');

        this.container.appendChild(card);

        return this.container;
    }
}
