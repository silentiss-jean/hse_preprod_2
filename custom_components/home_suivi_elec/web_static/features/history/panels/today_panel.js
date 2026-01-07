/**
 * @file today_panel.js
 * @description Panneau "Aujourd'hui" - Vue en temps réel des coûts avec capteur de référence
 */

export class TodayPanel {
    constructor(container, api) {
        this.container = container;
        this.api = api;
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
        this.renderLoading();
        await this.loadData();
    }

    /**
     * Charge les données depuis l'API
     */
    async loadData() {
        try {
            console.log('[TODAY-PANEL] Loading data...');
            this.data = await this.api.fetchCurrentCosts();
            console.log('[TODAY-PANEL] Data loaded:', this.data);
            this.render();
        } catch (error) {
            console.error('[TODAY-PANEL] Load failed:', error);
            this.renderError(error.message);
        }
    }

    /**
     * Affiche le panneau complet
     */
    render() {
        if (!this.data) {
            this.renderLoading();
            return;
        }

        const html = `
            <div class="today-panel">
                ${this.renderHeader()}
                ${this.renderReferenceSensor()}
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
     * 🆕 Panel du capteur de référence (compteur principal)
     */
    renderReferenceSensor() {
        const refSensor = this.data.reference_sensor;
        const gap = this.data.gap;

        if (!refSensor) {
            return `
                <div class="reference-sensor-placeholder">
                    <p>💡 Aucun capteur de référence configuré</p>
                    <p class="subtitle">Configurez un capteur externe (ex: Linky) pour suivre la consommation totale au compteur</p>
                </div>
            `;
        }

        const gapHtml = gap && Math.abs(gap.percent) > 5 ? `
            <div class="gap-alert ${gap.energy_kwh > 0 ? 'warning' : 'info'}">
                <span class="gap-icon">${gap.energy_kwh > 0 ? '⚠️' : 'ℹ️'}</span>
                <div class="gap-content">
                    <strong>Écart avec capteurs internes:</strong><br>
                    ${gap.energy_kwh > 0 ? '+' : ''}${gap.energy_kwh.toFixed(3)} kWh 
                    (${gap.energy_kwh > 0 ? '+' : ''}${gap.percent.toFixed(1)}%) 
                    → ${gap.energy_kwh > 0 ? '+' : ''}${gap.cost_ttc.toFixed(2)} € TTC
                    <p class="gap-explanation">
                        ${gap.energy_kwh > 0 
                            ? 'Consommation non tracée par les capteurs internes' 
                            : 'Suivi cohérent avec le compteur'}
                    </p>
                </div>
            </div>
        ` : '';

        return `
            <div class="reference-panel-today">
                <div class="ref-header">
                    <span class="ref-badge">🏠 RÉFÉRENCE</span>
                    <h3>${refSensor.friendly_name}</h3>
                    <p class="ref-subtitle">Consommation totale au compteur</p>
                </div>
                <div class="ref-metrics">
                    <div class="metric-item">
                        <span class="metric-label">⚡ Énergie</span>
                        <span class="metric-value">${refSensor.energy_kwh.toFixed(3)} kWh</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">💵 Coût HT</span>
                        <span class="metric-value">${refSensor.cost_ht.toFixed(2)} €</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">💰 Coût TTC</span>
                        <span class="metric-value primary">${refSensor.cost_ttc.toFixed(2)} €</span>
                    </div>
                </div>
                ${gapHtml}
            </div>
        `;
    }

    /**
     * Résumé global des capteurs internes
     */
    renderSummary() {
        // Badge d'information si des capteurs sont exclus
        const excludedBadge = this.data.excluded_count > 0 ? `
            <div class="summary-alert">
                <span class="alert-icon">⚠️</span>
                <div class="alert-content">
                    <strong>${this.data.excluded_count} capteur(s) exclu(s)</strong>
                    ${this.renderExcludedDetails()}
                </div>
            </div>
        ` : '';

        return `
            <div class="summary-section">
                <h3>📋 Capteurs internes</h3>
                ${excludedBadge}
                <div class="summary-grid">
                    <div class="summary-metric">
                        <span class="metric-icon">💶</span>
                        <div class="metric-content">
                            <div class="metric-label">Total TTC</div>
                            <div class="metric-value">${this.formatPrice(this.data.total_cost_ttc)}</div>
                        </div>
                    </div>
                    <div class="summary-metric">
                        <span class="metric-icon">💵</span>
                        <div class="metric-content">
                            <div class="metric-label">Total HT</div>
                            <div class="metric-value">${this.formatPrice(this.data.total_cost_ht)}</div>
                        </div>
                    </div>
                    <div class="summary-metric">
                        <span class="metric-icon">⚡</span>
                        <div class="metric-content">
                            <div class="metric-label">Énergie totale</div>
                            <div class="metric-value">${this.formatEnergy(this.data.total_energy_kwh)}</div>
                        </div>
                    </div>
                    <div class="summary-metric">
                        <span class="metric-icon">📊</span>
                        <div class="metric-content">
                            <div class="metric-label">Capteurs actifs</div>
                            <div class="metric-value">${this.data.sensor_count}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Détails des capteurs exclus
     */
    renderExcludedDetails() {
        const reasons = this.data.excluded_reasons || {};
        const details = [];

        if (reasons.unavailable > 0) {
            details.push(`${reasons.unavailable} indisponible(s)`);
        }
        if (reasons.source_unavailable > 0) {
            details.push(`${reasons.source_unavailable} source(s) indisponible(s)`);
        }
        if (reasons.zero_values > 0) {
            details.push(`${reasons.zero_values} inactif(s)`);
        }

        if (details.length === 0) return '';

        return `<span class="excluded-details">(${details.join(' • ')})</span>`;
    }

    /**
     * Top 10 des capteurs
     */
    renderTopSensors() {
        if (!this.data.top_10 || this.data.top_10.length === 0) {
            return '<div class="no-data">Aucun capteur à afficher</div>';
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
                <div class="sensors-scrollable">
                    ${cards}
                </div>
            </div>
        `;
    }

    /**
     * Carte individuelle d'un capteur
     */
    renderSensorCard(sensor, rank) {
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;

        return `
            <div class="sensor-card">
                <div class="card-rank">
                    <span class="rank-badge">${medal}</span>
                </div>
                <div class="card-content">
                    <h4 class="sensor-name">${sensor.friendly_name}</h4>
                    <p class="sensor-source">${sensor.source_entity || 'Source inconnue'}</p>
                    <div class="sensor-metrics">
                        <div class="metric-row">
                            <span class="label">💶 Coût TTC:</span>
                            <span class="value">${this.formatPrice(sensor.cost_ttc)}</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">💵 Coût HT:</span>
                            <span class="value">${this.formatPrice(sensor.cost_ht)}</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">⚡ Énergie:</span>
                            <span class="value">${this.formatEnergy(sensor.energy_kwh)}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Indicateur de chargement
     */
    renderLoading() {
        this.container.innerHTML = `
            <div class="loading-panel">
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
            <div class="error-panel">
                <h3>❌ Erreur</h3>
                <p>${message}</p>
                <button id="retry-today" class="btn-retry">
                    🔄 Réessayer
                </button>
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
