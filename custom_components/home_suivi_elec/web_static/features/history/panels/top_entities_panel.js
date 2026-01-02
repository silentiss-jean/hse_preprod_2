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

        const columns = [
            {
                key: 'index',
                label: '#',
                render: (value) => value + 1
            },
            {
                key: 'display_name',
                label: 'Capteur',
                render: (value, row) => `
                    <div class="sensor-cell">
                        <strong>${row.display_name}</strong>
                        <span class="entity-id-small">${row.entity_id}</span>
                    </div>
                `
            },
            {
                key: 'baseline',
                label: 'Période de référence',
                render: (value, row) => `
                    <div class="cost-cell">
                        <div>${formatKwh(row.baseline_energy_kwh)}</div>
                        <div class="cost-secondary">${formatEuro(row.baseline_cost_ttc)}</div>
                    </div>
                `
            },
            {
                key: 'event',
                label: 'Période analysée',
                render: (value, row) => `
                    <div class="cost-cell">
                        <div>${formatKwh(row.event_energy_kwh)}</div>
                        <div class="cost-secondary">${formatEuro(row.event_cost_ttc)}</div>
                    </div>
                `
            },
            {
                key: 'delta',
                label: 'Évolution',
                render: (value, row) => {
                    const deltaCost = formatDeltaWithSign(row.delta_cost_ttc, formatEuro);
                    const deltaEnergy = formatDeltaWithSign(row.delta_energy_kwh, formatKwh);
                    return `
                        <div class="delta-cell ${deltaCost.color}">
                            <div>${deltaEnergy.text}</div>
                            <div class="cost-secondary">${deltaCost.text}</div>
                        </div>
                    `;
                }
            },
            {
                key: 'variation',
                label: 'Variation %',
                render: (value, row) => {
                    const pctClass = getVarianceClass(row.pct_cost_ttc);
                    return `<span class="badge badge-${pctClass}">${formatPercent(row.pct_cost_ttc)}</span>`;
                }
            }
        ];

        const dataWithIndex = topEntities.map((entity, index) => ({
            ...entity,
            index
        }));

        const table = Table.create(columns, dataWithIndex);
        table.classList.add('top-entities-table');

        const card = Card.create(`🏆 Top ${topEntities.length} des capteurs responsables`, table);
        card.classList.add('top-entities-card');

        this.container.appendChild(card);

        return this.container;
    }
}
