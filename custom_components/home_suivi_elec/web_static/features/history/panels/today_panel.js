/**
 * @file today_panel.js
 * @description Panneau "Aujourd'hui" - Vue en temps réel des coûts
 */

export class TodayPanel {
    constructor(container, api) { // ✅ Recevoir l'instance API
        this.container = container;
        this.api = api; // ✅ Stocker l'instance
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
            this.data = await this.api.fetchCurrentCosts(); // ✅ Utiliser l'instance
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
        // Badge d'information si des capteurs sont exclus
        const excludedBadge = this.data.excluded_count > 0 
            ? `<div class="summary-alert">
                <span class="alert-icon">⚠️</span>
                <div class="alert-content">
                    <strong>${this.data.excluded_count} capteur(s) exclu(s)</strong>
                    ${this.renderExcludedDetails()}
                </div>
            </div>`
            : '';
        
        return `
            <div class="summary-section">
                ${excludedBadge}
                
                <div class="summary-grid">
                    <div class="summary-metric">
                        <div class="metric-icon">💶</div>
                        <div class="metric-content">
                            <div class="metric-label">Total TTC</div>
                            <div class="metric-value primary">${this.formatPrice(this.data.total_cost_ttc)}</div>
                        </div>
                    </div>
                    
                    <div class="summary-metric">
                        <div class="metric-icon">💵</div>
                        <div class="metric-content">
                            <div class="metric-label">Total HT</div>
                            <div class="metric-value">${this.formatPrice(this.data.total_cost_ht)}</div>
                        </div>
                    </div>
                    
                    <div class="summary-metric">
                        <div class="metric-icon">⚡</div>
                        <div class="metric-content">
                            <div class="metric-label">Énergie totale</div>
                            <div class="metric-value">${this.formatEnergy(this.data.total_energy_kwh)}</div>
                        </div>
                    </div>
                    
                    <div class="summary-metric">
                        <div class="metric-icon">📊</div>
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
 * Render the "Today" view with reference sensor
 */
async renderTodayView() {
    try {
        const response = await this.api.getCurrentCosts();
        
        if (!response) {
            this.showError("Impossible de charger les coûts");
            return;
        }
        
        const { reference_sensor, top_10, other_sensors, total_cost_ttc, total_cost_ht, total_energy_kwh, gap, sensor_count } = response;
        
        let html = '<div class="today-view">';
        
        // 🆕 PANEL RÉFÉRENCE (si configuré)
        if (reference_sensor) {
            html += this.renderReferenceSensorToday(reference_sensor, gap);
        }
        
        // TOTAUX INTERNES
        html += `
            <div class="totals-section">
                <h3>📊 Capteurs internes (${sensor_count} actifs)</h3>
                <div class="totals-cards">
                    <div class="total-card">
                        <span class="card-icon">💰</span>
                        <span class="card-label">Total TTC</span>
                        <span class="card-value">${total_cost_ttc.toFixed(2)} €</span>
                    </div>
                    <div class="total-card">
                        <span class="card-icon">💵</span>
                        <span class="card-label">Total HT</span>
                        <span class="card-value">${total_cost_ht.toFixed(2)} €</span>
                    </div>
                    <div class="total-card">
                        <span class="card-icon">⚡</span>
                        <span class="card-label">Énergie</span>
                        <span class="card-value">${total_energy_kwh.toFixed(3)} kWh</span>
                    </div>
                </div>
            </div>
        `;
        
        // 🆕 ALERTE ÉCART (si significatif)
        if (gap && Math.abs(gap.percent) > 5) {
            html += this.renderGapAlert(gap);
        }
        
        // TOP 10
        html += '<div class="top-consumers"><h3>💰 Top 10 des plus coûteux</h3>';
        html += '<div class="sensors-grid">';
        top_10.forEach((sensor, index) => {
            html += this.renderSensorCard(sensor, index + 1);
        });
        html += '</div></div>';
        
        // Autres capteurs
        if (other_sensors && other_sensors.length > 0) {
            html += `
                <div class="other-sensors">
                    <details>
                        <summary>📋 Autres capteurs (${other_sensors.length})</summary>
                        <div class="sensors-list">
                            ${other_sensors.map(s => this.renderCompactSensor(s)).join('')}
                        </div>
                    </details>
                </div>
            `;
        }
        
        html += '</div>';
        
        this.container.innerHTML = html;
        
    } catch (error) {
        console.error('[HISTORY] Error rendering today view:', error);
        this.showError(`Erreur: ${error.message}`);
    }
}

    /**
     * 🆕 Render reference sensor for "Today" view
     */
    renderReferenceSensorToday(refSensor, gap) {
        const gapHtml = gap ? `
            <div class="ref-gap-indicator ${gap.energy_kwh > 0 ? 'positive' : 'negative'}">
                <span class="gap-icon">⚠️</span>
                <div class="gap-text">
                    <strong>Écart avec capteurs internes :</strong><br>
                    ${gap.energy_kwh > 0 ? '+' : ''}${gap.energy_kwh.toFixed(3)} kWh 
                    (${gap.energy_kwh > 0 ? '+' : ''}${gap.percent.toFixed(1)}%) 
                    → ${gap.energy_kwh > 0 ? '+' : ''}${gap.cost_ttc.toFixed(2)} € TTC
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
                
                <div class="ref-stats">
                    <div class="ref-stat">
                        <span class="stat-label">Énergie</span>
                        <span class="stat-value">${refSensor.energy_kwh.toFixed(3)} kWh</span>
                    </div>
                    <div class="ref-stat">
                        <span class="stat-label">Coût HT</span>
                        <span class="stat-value">${refSensor.cost_ht.toFixed(2)} €</span>
                    </div>
                    <div class="ref-stat primary">
                        <span class="stat-label">Coût TTC</span>
                        <span class="stat-value">${refSensor.cost_ttc.toFixed(2)} €</span>
                    </div>
                </div>
                
                ${gapHtml}
            </div>
        `;
    }

    /**
     * 🆕 Render gap alert
     */
    renderGapAlert(gap) {
        const isPositive = gap.energy_kwh > 0;
        return `
            <div class="gap-alert ${isPositive ? 'warning' : 'info'}">
                <div class="alert-icon">${isPositive ? '⚠️' : 'ℹ️'}</div>
                <div class="alert-content">
                    <strong>${isPositive ? 'Consommation non tracée détectée' : 'Suivi cohérent'}</strong>
                    <p>
                        ${Math.abs(gap.energy_kwh).toFixed(3)} kWh 
                        (${Math.abs(gap.percent).toFixed(1)}%) 
                        ${isPositive ? 'non tracés par les capteurs internes' : 'en trop dans les capteurs internes'}
                        → ${Math.abs(gap.cost_ttc).toFixed(2)} € TTC
                    </p>
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
        
        return `<div class="alert-details">${details.join(' • ')}</div>`;
    }


    /**
     * Détails des capteurs exclus (tooltip/badge)
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
        
        return `<span class="excluded-details">(${details.join(', ')})</span>`;
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
