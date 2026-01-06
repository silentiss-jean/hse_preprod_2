/**
 * @file today_panel.js
 * @description Panel for "Aujourd'hui" view - Real-time current costs
 */

export class TodayPanel {
    constructor(container, api) {
        this.container = container;
        this.api = api;
        this.data = null;
        this.isLoading = false;
    }

    /**
     * Render the "Aujourd'hui" panel
     */
    async render() {
        this.container.innerHTML = `
            <div class="today-panel">
                <div class="panel-header">
                    <h2>📊 Coûts du jour</h2>
                    <button id="refresh-today" class="btn-refresh">
                        🔄 Rafraîchir
                    </button>
                </div>
                
                <div id="today-loading" class="loading-indicator" style="display: none;">
                    <div class="spinner"></div>
                    <p>Chargement des données en temps réel...</p>
                </div>

                <div id="today-content" class="panel-content">
                    <div id="today-summary" class="summary-card"></div>
                    <div id="today-top10" class="top-sensors-list"></div>
                    <div id="today-others" class="other-sensors-list"></div>
                </div>

                <div id="today-error" class="error-message" style="display: none;"></div>
            </div>
        `;

        // Attach event listeners
        document.getElementById('refresh-today')?.addEventListener('click', () => {
            this.loadData();
        });

        // Initial load
        await this.loadData();
    }

    /**
     * Load current costs data from API
     */
    async loadData() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showLoading(true);
        this.hideError();

        try {
            this.data = await this.api.fetchCurrentCosts();
            this.renderContent();
        } catch (error) {
            console.error('[TODAY-PANEL] Load failed:', error);
            this.showError(error.message || 'Erreur lors du chargement des données');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }

    /**
     * Render the data content
     */
    renderContent() {
        if (!this.data) return;

        // Summary
        this.renderSummary();

        // Top 10
        this.renderTop10();

        // Others (scrollable)
        this.renderOthers();
    }

    /**
     * Render summary card
     */
    renderSummary() {
        const summaryEl = document.getElementById('today-summary');
        if (!summaryEl) return;

        summaryEl.innerHTML = `
            <div class="summary-header">
                <h3>Résumé global</h3>
                <span class="timestamp">${new Date().toLocaleString('fr-FR')}</span>
            </div>
            <div class="summary-metrics">
                <div class="metric">
                    <span class="label">Coût total (TTC)</span>
                    <span class="value">${this.data.total_cost_ttc.toFixed(2)} €</span>
                </div>
                <div class="metric">
                    <span class="label">Énergie totale</span>
                    <span class="value">${this.data.total_energy_kwh.toFixed(3)} kWh</span>
                </div>
                <div class="metric">
                    <span class="label">Capteurs actifs</span>
                    <span class="value">${this.data.sensor_count}</span>
                </div>
            </div>
        `;
    }

    /**
     * Render top 10 sensors
     */
    renderTop10() {
        const top10El = document.getElementById('today-top10');
        if (!top10El) return;

        const top10 = this.data.top_10 || [];

        if (top10.length === 0) {
            top10El.innerHTML = '<p class="no-data">Aucun capteur trouvé</p>';
            return;
        }

        top10El.innerHTML = `
            <h3>🔝 Top 10 des capteurs les plus coûteux</h3>
            <div class="sensors-grid">
                ${top10.map((sensor, index) => this.renderSensorCard(sensor, index + 1)).join('')}
            </div>
        `;
    }

    /**
     * Render other sensors (scrollable list)
     */
    renderOthers() {
        const othersEl = document.getElementById('today-others');
        if (!othersEl) return;

        const others = this.data.other_sensors || [];

        if (others.length === 0) {
            othersEl.innerHTML = '';
            return;
        }

        othersEl.innerHTML = `
            <h3>📋 Autres capteurs (${others.length})</h3>
            <div class="sensors-scrollable">
                ${others.map((sensor, index) => this.renderSensorCard(sensor, index + 11, true)).join('')}
            </div>
        `;
    }

    /**
     * Render a single sensor card
     */
    renderSensorCard(sensor, rank, compact = false) {
        const costClass = sensor.current_cost_ttc > 1 ? 'high-cost' : sensor.current_cost_ttc > 0.5 ? 'medium-cost' : 'low-cost';

        return `
            <div class="sensor-card ${compact ? 'compact' : ''} ${costClass}">
                <div class="sensor-rank">#${rank}</div>
                <div class="sensor-info">
                    <div class="sensor-name">${sensor.friendly_name}</div>
                    <div class="sensor-source">${sensor.source_entity || sensor.entity_id}</div>
                </div>
                <div class="sensor-metrics">
                    <div class="metric-row">
                        <span class="label">Coût:</span>
                        <span class="value cost">${sensor.current_cost_ttc.toFixed(4)} €</span>
                    </div>
                    <div class="metric-row">
                        <span class="label">Énergie:</span>
                        <span class="value energy">${sensor.current_energy_kwh.toFixed(3)} kWh</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Show/hide loading indicator
     */
    showLoading(show) {
        const loadingEl = document.getElementById('today-loading');
        const contentEl = document.getElementById('today-content');

        if (loadingEl) loadingEl.style.display = show ? 'block' : 'none';
        if (contentEl) contentEl.style.display = show ? 'none' : 'block';
    }

    /**
     * Show error message
     */
    showError(message) {
        const errorEl = document.getElementById('today-error');
        if (errorEl) {
            errorEl.textContent = `❌ ${message}`;
            errorEl.style.display = 'block';
        }
    }

    /**
     * Hide error message
     */
    hideError() {
        const errorEl = document.getElementById('today-error');
        if (errorEl) {
            errorEl.style.display = 'none';
        }
    }
}

export default TodayPanel;
