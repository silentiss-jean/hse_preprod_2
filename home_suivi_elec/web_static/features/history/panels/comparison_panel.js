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

        // Header avec méta-info
        const header = this.renderHeader(meta);
        this.container.appendChild(header);

        // Comparaison totale
        const totalCard = this.renderTotalComparison(comparison.total, meta);
        this.container.appendChild(totalCard);

        // Focus entity (si présent)
        if (comparison.focus_entity) {
            const focusCard = this.renderFocusComparison(comparison.focus_entity, meta);
            this.container.appendChild(focusCard);
        }

        // Extrêmes (max delta)
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
                <strong>Baseline:</strong> ${formatDurationHuman(meta.baseline_duration_s)}
            </span>
            <span class="meta-item">
                <strong>Event:</strong> ${formatDurationHuman(meta.event_duration_s)}
            </span>
            ${!meta.normalized_supported ? '<span class="meta-warning">⚠️ Périodes trop courtes (&lt;1h) - normalisation limitée</span>' : ''}
        `;
        header.appendChild(info);

        return header;
    }

    renderTotalComparison(total, meta) {
        const content = createElement('div', { class: 'comparison-content' });

        // ... (tout le code HTML reste identique jusqu'à content.appendChild(deltaBox))
        
        // ✅ CORRECTION : utilise Card.create() au lieu de new Card()
        const card = Card.create('📊 Total (tous capteurs)', content);
        card.classList.add('comparison-card', 'total-card');
        return card;
    }

    renderFocusComparison(focus, meta) {
        const content = createElement('div', { class: 'comparison-content' });
        
        // ... (tout le code HTML reste identique)
        
        // ✅ CORRECTION
        const card = Card.create(`🎯 Focus: ${focus.display_name}`, content);
        card.classList.add('comparison-card', 'focus-card');
        return card;
    }

    renderExtreme(extreme) {
        const content = createElement('div', { class: 'extreme-content' });
        content.innerHTML = `...`; // (reste identique)
        
        // ✅ CORRECTION
        const card = Card.create('🔥 Plus grande variation', content);
        card.classList.add('comparison-card', 'extreme-card');
        return card;
    }
 }