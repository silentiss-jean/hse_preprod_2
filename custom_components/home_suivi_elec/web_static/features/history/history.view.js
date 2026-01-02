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

        EventBus.on('history:analyze:requested', () => this.handleAnalyze());
        EventBus.on('history:state:changed', () => this.render());

        await this.loadAvailableSensors();
        this.state.applyPreset('today_vs_yesterday');
        this.render();
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
                class: 'card',
                style: 'background: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; margin-bottom: 24px;'
            });
            warningBox.innerHTML = `
                <strong>⚠️ Aucun capteur sélectionné</strong>
                <p style="margin: 8px 0 0 0; color: #856404;">
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
