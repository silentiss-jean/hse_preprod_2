/**
 * Vue principale du module History
 */
import { createElement, clearElement } from '../../shared/utils/dom.js';
import { renderLoader, renderError } from '../../shared/views/commonViews.js';
import * as EventBus from '../../shared/eventBus.js';
import { PeriodSelectorPanel } from './panels/period_selector_panel.js';
import { FocusSelectorPanel } from './panels/focus_selector_panel.js';
import { ComparisonPanel } from './panels/comparison_panel.js';
import { TopEntitiesPanel } from './panels/top_entities_panel.js';

export class HistoryView {
    constructor(state, api) {
        this.state = state;
        this.api = api;
        this.container = null;
        this.periodPanel = null;
        this.focusPanel = null;
        this.comparisonPanel = null;
        this.topPanel = null;
    }

    async init() {
        this.container = document.getElementById('history');
        if (!this.container) {
            console.error('[HISTORY-VIEW] Container #history not found');
            return;
        }

        // Injecte un petit correctif CSS pour harmoniser le rendu avec les thèmes HSE
        // (évite une dépendance à des couleurs en dur + corrige le mismatch .comparison-column vs CSS legacy)
        this.ensureThemeCompatibleStyles();

        EventBus.on('history:analyze:requested', () => this.handleAnalyze());
        EventBus.on('history:state:changed', () => this.render());

        await this.loadAvailableSensors();
        this.state.applyPreset('today_vs_yesterday');
        this.render();
    }

    ensureThemeCompatibleStyles() {
        const STYLE_ID = 'hse-history-polish';
        if (document.getElementById(STYLE_ID)) return;

        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
/* =====================================================================
   HSE History – visual polish (theme-compatible)
   - Corrige le mismatch entre comparison_panel.js (.comparison-column)
     et les anciens sélecteurs CSS (.comparison-col)
   - Remplace les couleurs inline (warning) par tokens HSE
   ===================================================================== */

#history .history-module .comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: var(--spacing-lg, 24px);
  margin-bottom: var(--spacing-lg, 24px);
}

#history .history-module .comparison-column {
  background: var(--bg-secondary, var(--hse-surface-muted, rgba(255,255,255,0.06)));
  padding: var(--spacing-md, 16px);
  border-radius: var(--border-radius, var(--hse-radius-md, 12px));
  border: 1px solid var(--border-color-light, var(--hse-border-soft, rgba(255,255,255,0.12)));
  box-shadow: var(--shadow-md, var(--hse-shadow-md, 0 10px 24px rgba(0,0,0,.14)));
  transition: transform var(--transition-base, 180ms ease), box-shadow var(--transition-base, 180ms ease), border-color var(--transition-base, 180ms ease);
}

#history .history-module .comparison-column:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg, var(--hse-shadow-lg, 0 18px 45px rgba(0,0,0,.20)));
  border-color: var(--hse-accent, var(--hse-primary, #7c3aed));
}

#history .history-module .comparison-column.baseline { border-left: 4px solid var(--hse-info, #0284c7); }
#history .history-module .comparison-column.event { border-left: 4px solid var(--hse-warning, #f59e0b); }

#history .history-module .comparison-column.delta.success { border-left: 4px solid var(--hse-success, #16a34a); }
#history .history-module .comparison-column.delta.danger { border-left: 4px solid var(--hse-error, #ef4444); }
#history .history-module .comparison-column.delta.neutral { border-left: 4px solid var(--border-color-strong, var(--hse-border-strong, rgba(148,163,184,0.28))); }

#history .history-module .comparison-column h4 {
  margin: 0 0 var(--spacing-sm, 8px);
  font-size: 0.95rem;
  font-weight: 900;
  color: var(--text-primary, var(--hse-text-main, #e5e7eb));
}

#history .history-module .comparison-column .value-main {
  font-size: 1.8rem;
  font-weight: 900;
  color: var(--text-primary, var(--hse-text-main, #e5e7eb));
  font-variant-numeric: tabular-nums;
  margin: 2px 0 6px;
}

#history .history-module .comparison-column .value-secondary {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-secondary, var(--hse-text-muted, rgba(229,231,235,0.72)));
  margin-bottom: var(--spacing-sm, 8px);
}

#history .history-module .comparison-column .value-normalized {
  margin-top: var(--spacing-sm, 8px);
  padding-top: var(--spacing-sm, 8px);
  border-top: 1px solid var(--border-color-light, var(--hse-border-soft, rgba(255,255,255,0.12)));
  font-size: 0.9rem;
  color: var(--text-secondary, var(--hse-text-muted, rgba(229,231,235,0.72)));
}

#history .history-module .badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--spacing-sm, 8px);
  padding: 4px 10px;
  border-radius: var(--hse-badge-radius, 999px);
  font-weight: 900;
  font-size: 0.85rem;
  border: 1px solid var(--border-color, var(--hse-border, rgba(148,163,184,0.18)));
  background: var(--hse-badge-bg, rgba(255,255,255,0.06));
  color: var(--hse-badge-fg, var(--text-primary, var(--hse-text-main, #e5e7eb)));
}

#history .history-module .badge.badge-success {
  background: var(--hse-success-soft, rgba(22,163,74,0.12));
  border-color: var(--hse-success, #16a34a);
  color: var(--hse-success, #16a34a);
}

#history .history-module .badge.badge-warning {
  background: var(--hse-warning-soft, rgba(245,158,11,0.16));
  border-color: var(--hse-warning, #f59e0b);
  color: var(--hse-warning-dark, #b45309);
}

#history .history-module .badge.badge-danger {
  background: var(--hse-error-soft, rgba(239,68,68,0.12));
  border-color: var(--hse-error, #ef4444);
  color: var(--hse-error, #ef4444);
}

/* Warning card (plus de couleurs inline) */
#history .history-module .card.hse-warning-card {
  background: var(--hse-warning-soft, rgba(245,158,11,0.16));
  border: 1px solid var(--hse-warning, #f59e0b);
  border-left: 4px solid var(--hse-warning, #f59e0b);
  border-radius: var(--border-radius, var(--hse-radius-md, 12px));
  padding: var(--spacing-md, 16px);
  margin-bottom: var(--spacing-lg, 24px);
  color: var(--text-primary, var(--hse-text-main, #111827));
}

#history .history-module .card.hse-warning-card p {
  margin: 8px 0 0 0;
  color: var(--text-secondary, var(--hse-text-muted, rgba(15,23,42,0.65)));
}

@media (max-width: 980px) {
  #history .history-module .comparison-grid {
    grid-template-columns: 1fr;
  }
}
`;

        document.head.appendChild(style);
    }

    async loadAvailableSensors() {
        try {
            console.log('[HISTORY-VIEW] Loading available sensors...');
            const sensors = await this.api.fetchSelectedSensors();
            console.log('[HISTORY-VIEW] Sensors loaded:', sensors.length);
            this.state.update({ available_sensors: sensors });
        } catch (error) {
            console.error('[HISTORY-VIEW] Failed to load sensors:', error);
            this.state.update({ available_sensors: [] });
        }
    }

    render() {
        if (!this.container) return;

        clearElement(this.container);

        const wrapper = createElement('div', { class: 'history-module' });

        const header = createElement('div', { class: 'history-header' });
        const title = createElement('h2', { textContent: '📊 Analyse de coûts' });
        const subtitle = createElement('p', { 
            textContent: 'Comparez vos consommations entre deux périodes',
            class: 'subtitle',
        });
        header.appendChild(title);
        header.appendChild(subtitle);
        wrapper.appendChild(header);

        const sensors = this.state.get('available_sensors') || [];
        if (sensors.length === 0 && !this.state.get('loading')) {
            const warningBox = createElement('div', { 
                class: 'card hse-warning-card'
            });
            warningBox.innerHTML = `
                <strong>⚠️ Aucun capteur sélectionné</strong>
                <p>
                    Veuillez d'abord configurer vos capteurs dans l'onglet "Configuration".
                </p>
            `;
            wrapper.appendChild(warningBox);
            this.container.appendChild(wrapper);
            return;
        }

        this.periodPanel = new PeriodSelectorPanel(this.state);
        wrapper.appendChild(this.periodPanel.render());

        this.focusPanel = new FocusSelectorPanel(this.state);
        wrapper.appendChild(this.focusPanel.render(sensors));

        wrapper.appendChild(createElement('hr', { class: 'section-separator' }));

        const resultsContainer = createElement('div', { class: 'history-results' });

        if (this.state.get('loading')) {
            renderLoader(resultsContainer, 'Analyse en cours...');
        } else if (this.state.get('error')) {
            renderError(resultsContainer, this.state.get('error'));
        } else if (this.state.get('analysis_result')) {
            const data = this.state.get('analysis_result');

            this.comparisonPanel = new ComparisonPanel(this.state);
            resultsContainer.appendChild(this.comparisonPanel.render(data));

            if (data?.top_entities?.by_cost_ttc) {
                this.topPanel = new TopEntitiesPanel(this.state);
                resultsContainer.appendChild(this.topPanel.render(data.top_entities.by_cost_ttc));
            }
        } else {
            resultsContainer.appendChild(
                createElement('p', { 
                    textContent: 'Sélectionnez une période et lancez l\'analyse.',
                    class: 'empty-state',
                })
            );
        }

        wrapper.appendChild(resultsContainer);
        this.container.appendChild(wrapper);
    }

    async handleAnalyze() {
        this.state.update({ loading: true, error: null });

        try {
            const payload = this.state.buildPayload();
            const data = await this.api.fetchHistoryCosts(payload);
            
            this.state.update({ 
                analysis_result: data,
                loading: false,
            });
        } catch (error) {
            console.error('[HISTORY-VIEW] Analysis failed:', error);
            this.state.update({ 
                error: error.message || 'Erreur lors de l\'analyse',
                loading: false,
            });
        }
    }

    destroy() {
        EventBus.off('history:analyze:requested');
        EventBus.off('history:state:changed');
    }
}

export default HistoryView;
