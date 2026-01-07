/**
 * @file today_panel.js
 * @description Panneau "Aujourd'hui" - Vue en temps réel des coûts
 */

import HistoryAPI from '../history.api.js';

export class TodayPanel {
    constructor(container, mainController) {
        this.container = container;
        this.mainController = mainController;
        this.data = null;
    }

    /**
     * Formate un prix au format français
     */
    formatPrice(value) {
        return value.toFixed(2).replace('.', ',') + ' €';
    }

    /**
     * Formate une énergie avec 3 décimales
     */
    formatEnergy(value) {
        return value.toFixed(3) + ' kWh';
    }

    /**
     * Initialise le panneau
     */
    async init() {
        console.log('[TODAY-PANEL] Initializing...');
        this.render();
        await this.loadData();
    }

    /**
     * Charge les données depuis l'API
     */
    async loadData() {
        try {
            console.log('[TODAY-PANEL] Loading data...');
            this.data = await HistoryAPI.fetchCurrentCosts();
            console.log('[TODAY-PANEL] Data loaded:', this.data);
            this.render();
        } catch (error) {
            console.error('[TODAY-PANEL] Load failed:', error);
            this.renderError(error.message);
        }
    }

    /**
     * Affiche le panneau
     */
    render() {
        if (!this.data) {
            this.container.innerHTML = this.renderLoading();
            return;
        }

        const html = `
            <div class="today-panel">
                ${this.renderHeader()}
                ${this.renderSummary()}
                ${this.renderTopSensors()}
                ${this.renderOtherSensors()}
            </div>
        `;

        this.container.innerHTML = html;
        this.attachEventListeners();
    }

    /**
     * En-tête avec bouton rafraîchir
     */
    renderHeader() {
        return `
            <div class="panel-header">
                <h2>📊 Coûts d'aujourd'hui</h2>
                <button id="refresh-today" class="btn-refresh">
                    🔄 Rafraîchir
                </button>
            </div>
        `;
    }

    /**
     * Résumé global
     */
    renderSummary() {
        return `
            <div class="summary-card">
                <div class="summary-item">
                    <span class="label">Total TTC:</span>
                    <span class="value">${this.formatPrice(this.data.total_cost_ttc)}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Total HT:</span>
                    <span class="value">${this.formatPrice(this.data.total_cost_ht)}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Énergie totale:</span>
                    <span class="value">${this.formatEnergy(this.data.total_energy_kwh)}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Capteurs:</span>
                    <span class="value">${this.data.sensor_count}</span>
                </div>
            </div>
        `;
    }

    /**
     * Top 10 des capteurs
     */
    renderTopSensors() {
        if (!this.data.top_10 || this.data.top_10.length === 0) {
            return '<div class="info-message">Aucun capteur à afficher</div>';
        }

        const cards = this.data.top_10
            .map((sensor, index) => this.renderSensorCard(sensor, index + 1))
            .join('');

        return `
            <div class="top-sensors-section">
                <h3>💰 Top 10 des capteurs les plus coûteux</h3>
                <div class="sensors-grid">
                    ${cards}
                </div>
            </div>
        `;
    }

    /**
     * Autres capteurs (scrollable)
     */
    renderOtherSensors() {
        if (!this.data.other_sensors || this.data.other_sensors.length === 0) {
            return '';
        }

        const cards = this.data.other_sensors
            .map((sensor, index) => this.renderSensorCard(sensor, index + 11))
            .join('');

        return `
            <div class="other-sensors-section">
                <h3>📦 Autres capteurs (${this.data.other_sensors.length})</h3>
                <div class="sensors-list-scrollable">
                    ${cards}
                </div>
            </div>
        `;
    }

    /**
     * Carte individuelle d'un capteur
     */
    renderSensorCard(sensor, rank) {
        return `
            <div class="sensor-card" data-entity="${sensor.entity_id}">
                <div class="sensor-rank">#${rank}</div>
                <div class="sensor-info">
                    <div class="sensor-name" title="${sensor.entity_id}">
                        ${sensor.friendly_name}
                    </div>
                    <div class="sensor-source" title="${sensor.source_entity || 'N/A'}">
                        ${sensor.source_entity || 'Source inconnue'}
                    </div>
                </div>
                <div class="sensor-metrics">
                    <div class="metric-row">
                        <span class="metric-label">Coût TTC:</span>
                        <span class="metric-value metric-ttc">${this.formatPrice(sensor.cost_ttc)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Coût HT:</span>
                        <span class="metric-value metric-ht">${this.formatPrice(sensor.cost_ht)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Énergie:</span>
                        <span class="metric-value metric-energy">${this.formatEnergy(sensor.energy_kwh)}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Indicateur de chargement
     */
    renderLoading() {
        return `
            <div class="loading-indicator">
                <div class="spinner"></div>
                <p>Chargement des données...</p>
            </div>
        `;
    }

    /**
     * Message d'erreur
     */
    renderError(message) {
        this.container.innerHTML = `
            <div class="error-message">
                <h3>❌ Erreur</h3>
                <p>${message}</p>
                <button id="retry-today" class="btn-retry">Réessayer</button>
            </div>
        `;
        
        document.getElementById('retry-today')?.addEventListener('click', () => {
            this.loadData();
        });
    }

    /**
     * Attache les événements
     */
    attachEventListeners() {
        const refreshBtn = document.getElementById('refresh-today');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                console.log('[TODAY-PANEL] Refresh button clicked');
                this.loadData();
            });
        }
    }
}

export default TodayPanel;