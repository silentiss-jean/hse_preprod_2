/**
 * @file comparison_controller.js
 * @description Controller for period comparisons
 */

export class ComparisonController {
    constructor(container, api) {
        this.container = container;
        this.api = api;
        this.data = null;
        this.isLoading = false;
        this.currentComparison = 'today_yesterday';
        this.focusEntityId = null;
    }

    /**
     * Format number with French locale (comma as decimal separator)
     */
    formatNumber(value, decimals = 2) {
        return value.toLocaleString('fr-FR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    /**
     * Initialize the comparison view (called by history_main.js)
     */
    async init() {
        console.log('[COMPARISON] Initializing comparison controller...');
        await this.render(this.currentComparison);
    }

    /**
     * Render the comparison interface
     */
    async render(comparisonType = 'today_yesterday') {
        this.currentComparison = comparisonType;
        
        this.container.innerHTML = `
            <div class="comparison-panel">
                <div class="comparison-header">
                    <h2>📊 Analyse comparative</h2>
                </div>

                <div class="comparison-tabs">
                    <button class="tab ${comparisonType === 'today_yesterday' ? 'active' : ''}" data-type="today_yesterday">
                        Aujourd'hui vs Hier
                    </button>
                    <button class="tab ${comparisonType === 'week_lastweek' ? 'active' : ''}" data-type="week_lastweek">
                        Cette semaine vs Dernière semaine
                    </button>
                    <button class="tab ${comparisonType === 'weekend_lastweekend' ? 'active' : ''}" data-type="weekend_lastweekend">
                        Ce weekend vs Weekend dernier
                    </button>
                    <button class="tab ${comparisonType === 'custom' ? 'active' : ''}" data-type="custom">
                        Périodes personnalisées
                    </button>
                </div>

                <div id="period-selector" class="period-selector"></div>

                <div class="action-buttons">
                    <button id="launch-analysis" class="btn-primary">
                        🚀 Lancer l'analyse
                    </button>
                    <button id="back-to-today" class="btn-secondary">
                        ← Retour à Aujourd'hui
                    </button>
                </div>

                <div id="comparison-loading" class="loading-indicator" style="display: none;">
                    <div class="spinner"></div>
                    <p>Analyse en cours...</p>
                </div>

                <div id="comparison-results" class="comparison-results" style="display: none;">
                    <!-- 🆕 PANEL RÉFÉRENCE (en premier) -->
                    <div id="comparison-reference-sensor"></div>
                    
                    <!-- RÉSUMÉ (capteurs internes seulement) -->
                    <div id="comparison-summary"></div>
                    
                    <!-- TOP VARIATIONS -->
                    <div id="comparison-top-variations"></div>
                    
                    <!-- AUTRES CAPTEURS -->
                    <div id="comparison-other-sensors"></div>
                    
                    <!-- FOCUS PANEL -->
                    <div id="comparison-focus"></div>
                </div>

                <div id="comparison-error" class="error-message" style="display: none;"></div>
            </div>
        `;

        // Attach event listeners
        this.attachEventListeners();
        
        // Render period selector based on type
        this.renderPeriodSelector(comparisonType);
    }


    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Tab switching
        document.querySelectorAll('.comparison-tabs .tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const type = e.target.dataset.type;
                this.render(type);
            });
        });

        // Launch analysis button
        document.getElementById('launch-analysis')?.addEventListener('click', () => {
            this.launchAnalysis();
        });

        // Back to today button
        document.getElementById('back-to-today')?.addEventListener('click', () => {
            // Dispatch event to main controller to switch view
            this.container.dispatchEvent(new CustomEvent('switchView', { 
                detail: { view: 'today' },
                bubbles: true 
            }));
        });
    }

    /**
     * Render period selector based on comparison type
     */
    renderPeriodSelector(type) {
        const selectorEl = document.getElementById('period-selector');
        if (!selectorEl) return;

        if (type === 'custom') {
            // Custom period selector with date pickers
            selectorEl.innerHTML = `
                <div class="custom-periods">
                    <div class="period-group">
                        <h4>Période de référence (baseline)</h4>
                        <div class="date-inputs">
                            <label>
                                Début:
                                <input type="datetime-local" id="baseline-start" />
                            </label>
                            <label>
                                Fin:
                                <input type="datetime-local" id="baseline-end" />
                            </label>
                        </div>
                    </div>
                    <div class="period-group">
                        <h4>Période à comparer (event)</h4>
                        <div class="date-inputs">
                            <label>
                                Début:
                                <input type="datetime-local" id="event-start" />
                            </label>
                            <label>
                                Fin:
                                <input type="datetime-local" id="event-end" />
                            </label>
                        </div>
                    </div>
                </div>
            `;
        } else {
            // Pre-defined period (auto-calculated)
            const periods = this.calculatePeriods(type);
            selectorEl.innerHTML = `
                <div class="predefined-periods">
                    <div class="period-info">
                        <div class="period-box baseline">
                            <h4>Période de référence</h4>
                            <p>${this.formatDateRange(periods.baseline_start, periods.baseline_end)}</p>
                        </div>
                        <div class="period-box event">
                            <h4>Période à comparer</h4>
                            <p>${this.formatDateRange(periods.event_start, periods.event_end)}</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Calculate period dates based on comparison type
     */
    calculatePeriods(type) {
        const now = new Date();
        let baseline_start, baseline_end, event_start, event_end;

        switch (type) {
            case 'today_yesterday':
                // Aujourd'hui: 00:00 → maintenant
                event_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
                event_end = now;

                // Hier: 00:00 → 23:59:59
                baseline_start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0);
                baseline_end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
                break;

            case 'week_lastweek':
                // Cette semaine: Lundi 00:00 → maintenant
                const dayOfWeek = now.getDay() || 7; // Sunday = 7
                const mondayThisWeek = new Date(now);
                mondayThisWeek.setDate(now.getDate() - dayOfWeek + 1);
                mondayThisWeek.setHours(0, 0, 0, 0);

                event_start = mondayThisWeek;
                event_end = now;

                // Semaine dernière: Lundi → Dimanche
                const mondayLastWeek = new Date(mondayThisWeek);
                mondayLastWeek.setDate(mondayThisWeek.getDate() - 7);

                baseline_start = mondayLastWeek;
                baseline_end = new Date(mondayLastWeek);
                baseline_end.setDate(mondayLastWeek.getDate() + 6);
                baseline_end.setHours(23, 59, 59);
                break;

            case 'weekend_lastweekend':
                // Ce weekend: Samedi 00:00 → maintenant (ou Dimanche 23:59 si passé)
                const today = now.getDay();
                let saturdayThisWeekend = new Date(now);

                if (today === 0) {
                    // Dimanche
                    saturdayThisWeekend.setDate(now.getDate() - 1);
                } else if (today === 6) {
                    // Samedi
                    saturdayThisWeekend.setDate(now.getDate());
                } else {
                    // En semaine: prendre le samedi prochain
                    saturdayThisWeekend.setDate(now.getDate() + (6 - today));
                }
                saturdayThisWeekend.setHours(0, 0, 0, 0);

                event_start = saturdayThisWeekend;
                event_end = now;

                // Weekend dernier: Samedi → Dimanche
                const saturdayLastWeekend = new Date(saturdayThisWeekend);
                saturdayLastWeekend.setDate(saturdayThisWeekend.getDate() - 7);

                baseline_start = saturdayLastWeekend;
                baseline_end = new Date(saturdayLastWeekend);
                baseline_end.setDate(saturdayLastWeekend.getDate() + 1);
                baseline_end.setHours(23, 59, 59);
                break;

            default:
                // Default: aujourd'hui vs hier
                event_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
                event_end = now;
                baseline_start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0);
                baseline_end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
        }

        return {
            baseline_start: baseline_start.toISOString(),
            baseline_end: baseline_end.toISOString(),
            event_start: event_start.toISOString(),
            event_end: event_end.toISOString()
        };
    }

    /**
     * Format date range for display
     */
    formatDateRange(startISO, endISO) {
        const start = new Date(startISO);
        const end = new Date(endISO);

        const options = { 
            day: 'numeric', 
            month: 'short', 
            hour: '2-digit', 
            minute: '2-digit' 
        };

        return `${start.toLocaleDateString('fr-FR', options)} → ${end.toLocaleDateString('fr-FR', options)}`;
    }

    /**
     * Launch the analysis
     */
    async launchAnalysis() {
        if (this.isLoading) return;

        let params;

        if (this.currentComparison === 'custom') {
            // Get custom dates from inputs
            const baselineStart = document.getElementById('baseline-start')?.value;
            const baselineEnd = document.getElementById('baseline-end')?.value;
            const eventStart = document.getElementById('event-start')?.value;
            const eventEnd = document.getElementById('event-end')?.value;

            if (!baselineStart || !baselineEnd || !eventStart || !eventEnd) {
                this.showError('Veuillez renseigner toutes les dates');
                return;
            }

            params = {
                baseline_start: new Date(baselineStart).toISOString(),
                baseline_end: new Date(baselineEnd).toISOString(),
                event_start: new Date(eventStart).toISOString(),
                event_end: new Date(eventEnd).toISOString()
            };
        } else {
            // Use pre-calculated periods
            params = this.calculatePeriods(this.currentComparison);
        }

        // Add pricing config (from global config or default)
        params.pricing = {
            contract_type: 'fixe',
            prix_kwh_ht: 0.2062,
            prix_kwh_ttc: 0.2516
        };

        params.top_limit = 10;
        params.sort_by = 'cost_ttc';

        this.isLoading = true;
        this.showLoading(true);
        this.hideError();
        this.hideResults();

        try {
            this.data = await this.api.analyzeCostComparison(params);
            this.renderResults();
        } catch (error) {
            console.error('[COMPARISON] Analysis failed:', error);
            this.showError(error.message || 'Erreur lors de l\'analyse');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }

    /**
     * 🆕 Render reference sensor panel (compteur principal)
     */
    renderReferenceSensor() {
        const refEl = document.getElementById('comparison-reference-sensor');
        if (!refEl) return;
        
        const refSensor = this.data.reference_sensor;
        
        if (!refSensor) {
            // Pas de capteur de référence configuré
            refEl.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #888; font-size: 0.9em;">
                    <p>💡 Aucun capteur de référence configuré</p>
                    <p style="font-size: 0.85em;">Configurez un capteur externe (ex: Atome) pour suivre la consommation totale au compteur</p>
                </div>
            `;
            return;
        }
        
        const deltaCost = refSensor.delta_cost_ttc;
        const deltaEnergy = refSensor.delta_energy_kwh;
        const pctCost = refSensor.pct_cost_ttc;
        
        const trendIcon = deltaCost > 0 ? '📈' : deltaCost < 0 ? '📉' : '➡️';
        const trendClass = deltaCost > 0 ? 'increase' : deltaCost < 0 ? 'decrease' : 'stable';
        const trendText = deltaCost > 0 ? 'augmenté' : deltaCost < 0 ? 'diminué' : 'stable';
        
        refEl.innerHTML = `
            <div class="reference-sensor-panel">
                <div class="reference-header">
                    <span class="reference-badge">🏠 RÉFÉRENCE</span>
                    <h3>${refSensor.display_name}</h3>
                    <p class="reference-subtitle">Consommation totale au compteur</p>
                </div>
                
                <div class="reference-comparison">
                    <div class="reference-period">
                        <div class="period-label">Période de référence</div>
                        <div class="period-values">
                            <div class="value-item">
                                <span class="value-label">Énergie</span>
                                <span class="value-number">${refSensor.baseline_energy_kwh.toFixed(3)} kWh</span>
                            </div>
                            <div class="value-item">
                                <span class="value-label">Coût HT</span>
                                <span class="value-number">${refSensor.baseline_cost_ht.toFixed(2)} €</span>
                            </div>
                            <div class="value-item">
                                <span class="value-label">Coût TTC</span>
                                <span class="value-number">${refSensor.baseline_cost_ttc.toFixed(2)} €</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="reference-arrow ${trendClass}">
                        <span class="trend-icon">${trendIcon}</span>
                        <div class="delta-summary">
                            <div>${deltaEnergy >= 0 ? '+' : ''}${deltaEnergy.toFixed(3)} kWh</div>
                            <div>${deltaCost >= 0 ? '+' : ''}${deltaCost.toFixed(2)} €</div>
                            <div class="delta-percent">(${pctCost >= 0 ? '+' : ''}${pctCost.toFixed(1)}%)</div>
                        </div>
                    </div>
                    
                    <div class="reference-period">
                        <div class="period-label">Période à comparer</div>
                        <div class="period-values">
                            <div class="value-item">
                                <span class="value-label">Énergie</span>
                                <span class="value-number">${refSensor.event_energy_kwh.toFixed(3)} kWh</span>
                            </div>
                            <div class="value-item">
                                <span class="value-label">Coût HT</span>
                                <span class="value-number">${refSensor.event_cost_ht.toFixed(2)} €</span>
                            </div>
                            <div class="value-item">
                                <span class="value-label">Coût TTC</span>
                                <span class="value-number">${refSensor.event_cost_ttc.toFixed(2)} €</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="reference-footer">
                    <button class="btn-focus-reference" data-entity="${refSensor.entity_id}">
                        🎯 Analyser en détail
                    </button>
                </div>
            </div>
        `;
        
        // Attach focus button
        const focusBtn = refEl.querySelector('.btn-focus-reference');
        if (focusBtn) {
            focusBtn.addEventListener('click', (e) => {
                const entityId = e.target.dataset.entity;
                this.showFocus(entityId);
            });
        }
    }

    /**
     * Render analysis results
     */
    renderResults() {
        if (!this.data) return;

        this.showResults();

        // 🆕 Render reference sensor panel FIRST (if exists)
        this.renderReferenceSensor();

        // Summary
        this.renderSummary();

        // Top variations
        this.renderTopVariations();

        // ➕ NOUVEAU : Top consommateurs
        this.renderTopConsumers();

        // Other sensors
        this.renderOtherSensors();

        // Focus (initially empty)
        this.renderFocusPanel();
    }

    /**
     * Render comparison summary
     */
    renderSummary() {
        const summaryEl = document.getElementById('comparison-summary');
        if (!summaryEl) return;

        const total = this.data.total_comparison;
        const baseline = this.data.baseline_period;
        const event = this.data.event_period;

        const trendIcon = total.trend === 'hausse' ? '📈' : total.trend === 'baisse' ? '📉' : '➡️';
        const trendClass = total.trend === 'hausse' ? 'trend-up' : total.trend === 'baisse' ? 'trend-down' : 'trend-stable';

        summaryEl.innerHTML = `
            <div class="comparison-summary-card">
                <h3>📊 Résumé de la comparaison</h3>
                <div class="summary-grid">
                    <div class="period-summary baseline">
                        <h4>Période de référence</h4>
                        <p class="date-range">${this.formatDateRange(baseline.start, baseline.end)}</p>
                        <div class="metrics">
                            <div class="metric">
                                <span class="label">Énergie</span>
                                <span class="value">${baseline.total_kwh.toFixed(3)} kWh</span>
                            </div>
                            <div class="metric">
                                <span class="label">Coût TTC</span>
                                <span class="value">${baseline.total_cost_ttc.toFixed(2)} €</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="comparison-delta ${trendClass}">
                        <div class="trend-icon">${trendIcon}</div>
                        <div class="delta-values">
                            <div class="delta-item">
                                <span class="label">Δ Énergie</span>
                                <span class="value">${total.delta_kwh >= 0 ? '+' : ''}${total.delta_kwh.toFixed(3)} kWh (${total.delta_pct_kwh >= 0 ? '+' : ''}${total.delta_pct_kwh.toFixed(1)}%)</span>
                            </div>
                            <div class="delta-item">
                                <span class="label">Δ Coût TTC</span>
                                <span class="value">${total.delta_cost_ttc >= 0 ? '+' : ''}${total.delta_cost_ttc.toFixed(2)} € (${total.delta_pct_cost >= 0 ? '+' : ''}${total.delta_pct_cost.toFixed(1)}%)</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="period-summary event">
                        <h4>Période à comparer</h4>
                        <p class="date-range">${this.formatDateRange(event.start, event.end)}</p>
                        <div class="metrics">
                            <div class="metric">
                                <span class="label">Énergie</span>
                                <span class="value">${event.total_kwh.toFixed(3)} kWh</span>
                            </div>
                            <div class="metric">
                                <span class="label">Coût TTC</span>
                                <span class="value">${event.total_cost_ttc.toFixed(2)} €</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render top variations
     */
    renderTopVariations() {
        const topEl = document.getElementById('comparison-top-variations');
        if (!topEl) return;

        const topVariations = this.data.top_variations || [];

        if (topVariations.length === 0) {
            topEl.innerHTML = '<p class="no-data">Aucune variation significative détectée</p>';
            return;
        }

        topEl.innerHTML = `
            <div class="top-variations-section">
                <h3>🔝 Top ${topVariations.length} des plus grandes variations</h3>
                <div class="variations-grid">
                    ${topVariations.map((sensor, index) => this.renderVariationCard(sensor, index + 1)).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render top consumers (highest absolute consumption)
     */
    renderTopConsumers() {
        const topEl = document.getElementById('comparison-top-consumers');
        if (!topEl) {
            // Créer la section si elle n'existe pas
            const resultsEl = document.getElementById('comparison-results');
            if (resultsEl) {
                const topVariationsEl = document.getElementById('comparison-top-variations');
                if (topVariationsEl) {
                    const div = document.createElement('div');
                    div.id = 'comparison-top-consumers';
                    topVariationsEl.insertAdjacentElement('afterend', div);
                }
            }
        }
        
        const topConsumersEl = document.getElementById('comparison-top-consumers');
        if (!topConsumersEl) return;
        
        const topConsumers = this.data.top_consumers || [];
        
        if (topConsumers.length === 0) {
            topConsumersEl.innerHTML = '<p class="no-data">Aucune donnée de consommation</p>';
            return;
        }
        
        topConsumersEl.innerHTML = `
            <div class="top-consumers-section">
                <h3>⚡ Top ${topConsumers.length} des plus gros consommateurs</h3>
                <div class="consumers-grid">
                    ${topConsumers.map((sensor, index) => this.renderConsumerCard(sensor, index + 1)).join('')}
                </div>
            </div>
        `;
        
        // Attacher les listeners pour les boutons focus
        this.attachFocusListeners();
    }

    /**
     * Render a single consumer card
     */
    renderConsumerCard(sensor, rank) {
        const eventCost = sensor.event_cost_ttc;
        const eventEnergy = sensor.event_energy_kwh;
        
        // Icône selon le rang
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
        
        return `
            <div class="consumer-card" data-entity="${sensor.entity_id}">
                <div class="card-header">
                    <span class="rank-badge">${medal}</span>
                </div>
                <div class="card-body">
                    <h4 class="sensor-name">${sensor.display_name}</h4>
                    <div class="consumption-highlight">
                        <div class="consumption-value">
                            <span class="value-large">${this.formatNumber(eventCost, 2)} €</span>
                            <span class="value-subtitle">${this.formatNumber(eventEnergy, 2)} kWh</span>
                        </div>
                    </div>
                    <p class="sensor-description">
                        Ce capteur représente <strong>${this.formatNumber((eventCost / this.data.event_period.total_cost_ttc) * 100, 1)}%</strong> 
                        de la consommation totale.
                    </p>
                    <div class="metrics-comparison">
                        <div class="metric-row">
                            <span class="label">Coût/heure:</span>
                            <span class="value">${this.formatNumber(sensor.event_cost_ttc_per_hour, 4)} €/h</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">Coût/jour:</span>
                            <span class="value">${this.formatNumber(sensor.event_cost_ttc_per_day, 2)} €/j</span>
                        </div>
                    </div>
                    <button class="btn-focus" data-entity="${sensor.entity_id}">
                        🎯 Focus sur ce capteur
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render a single variation card
     */
    renderVariationCard(sensor, rank) {
        const deltaCost = sensor.delta_cost_ttc;
        const deltaEnergy = sensor.delta_energy_kwh;
        const pctCost = sensor.pct_cost_ttc;
        
        const trendIcon = deltaCost > 0 ? '📈' : deltaCost < 0 ? '📉' : '➡️';
        const trendClass = deltaCost > 0 ? 'increase' : deltaCost < 0 ? 'decrease' : 'stable';
        const trendText = deltaCost > 0 ? 'augmenté' : deltaCost < 0 ? 'diminué' : 'stable';

        return `
            <div class="variation-card ${trendClass}" data-entity="${sensor.entity_id}">
                <div class="card-header">
                    <span class="rank">#${rank}</span>
                    <span class="trend-icon">${trendIcon}</span>
                </div>
                <div class="card-body">
                    <h4 class="sensor-name">${sensor.display_name}</h4>
                    <p class="sensor-description">
                        Le capteur <strong>${sensor.display_name}</strong> a <strong>${trendText}</strong> de 
                        <strong>${Math.abs(pctCost).toFixed(1)}%</strong>.
                        Il coûte <strong>${Math.abs(deltaCost).toFixed(2)} € ${deltaCost >= 0 ? 'de plus' : 'de moins'}</strong> 
                        par rapport à la période de référence.
                    </p>
                    <div class="metrics-comparison">
                        <div class="metric-row">
                            <span class="label">Baseline:</span>
                            <span class="value">${sensor.baseline_energy_kwh.toFixed(3)} kWh → ${sensor.baseline_cost_ttc.toFixed(2)} €</span>
                        </div>
                        <div class="metric-row">
                            <span class="label">Event:</span>
                            <span class="value">${sensor.event_energy_kwh.toFixed(3)} kWh → ${sensor.event_cost_ttc.toFixed(2)} €</span>
                        </div>
                        <div class="metric-row delta">
                            <span class="label">Delta:</span>
                            <span class="value">${deltaEnergy >= 0 ? '+' : ''}${deltaEnergy.toFixed(3)} kWh → ${deltaCost >= 0 ? '+' : ''}${deltaCost.toFixed(2)} €</span>
                        </div>
                    </div>
                    <button class="btn-focus" data-entity="${sensor.entity_id}">
                        🎯 Focus sur ce capteur
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render other sensors (scrollable)
     */
    renderOtherSensors() {
        const othersEl = document.getElementById('comparison-other-sensors');
        if (!othersEl) return;

        const otherSensors = this.data.other_sensors || [];

        if (otherSensors.length === 0) {
            othersEl.innerHTML = '';
            return;
        }

        othersEl.innerHTML = `
            <div class="other-sensors-section">
                <h3>📋 Autres capteurs analysés (${otherSensors.length})</h3>
                <div class="sensors-scrollable">
                    ${otherSensors.map((sensor, index) => this.renderCompactSensorRow(sensor)).join('')}
                </div>
            </div>
        `;

        // Attach focus button listeners
        this.attachFocusListeners();
    }

    /**
     * Render a compact sensor row
     */
    renderCompactSensorRow(sensor) {
        const deltaCost = sensor.delta_cost_ttc;
        const trendIcon = deltaCost > 0 ? '📈' : deltaCost < 0 ? '📉' : '➡️';
        const trendClass = deltaCost > 0 ? 'increase' : deltaCost < 0 ? 'decrease' : 'stable';

        return `
            <div class="sensor-row ${trendClass}" data-entity="${sensor.entity_id}">
                <div class="sensor-info">
                    <span class="icon">${trendIcon}</span>
                    <span class="name">${sensor.display_name}</span>
                </div>
                <div class="sensor-metrics">
                    <span class="delta-energy">${sensor.delta_energy_kwh >= 0 ? '+' : ''}${sensor.delta_energy_kwh.toFixed(3)} kWh</span>
                    <span class="delta-cost">${deltaCost >= 0 ? '+' : ''}${deltaCost.toFixed(2)} €</span>
                    <span class="delta-pct">(${sensor.pct_cost_ttc >= 0 ? '+' : ''}${sensor.pct_cost_ttc.toFixed(1)}%)</span>
                </div>
                <button class="btn-focus-mini" data-entity="${sensor.entity_id}">🎯</button>
            </div>
        `;
    }

    /**
     * Attach focus button listeners
     */
    attachFocusListeners() {
        document.querySelectorAll('.btn-focus, .btn-focus-mini').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const entityId = e.target.dataset.entity;
                this.showFocus(entityId);
            });
        });
    }

    /**
     * Show focus panel for a specific sensor
     */
    showFocus(entityId) {
        this.focusEntityId = entityId;

        // Find sensor data
        const allSensors = [
            ...(this.data.top_variations || []),
            ...(this.data.other_sensors || [])
        ];

        const sensor = allSensors.find(s => s.entity_id === entityId);

        if (!sensor) {
            console.error('[COMPARISON] Sensor not found:', entityId);
            return;
        }

        const focusEl = document.getElementById('comparison-focus');
        if (!focusEl) return;

        const deltaCost = sensor.delta_cost_ttc;
        const deltaEnergy = sensor.delta_energy_kwh;
        const pctCost = sensor.pct_cost_ttc;
        const pctEnergy = sensor.pct_energy_kwh;

        const trendIcon = deltaCost > 0 ? '📈' : deltaCost < 0 ? '📉' : '➡️';
        const trendClass = deltaCost > 0 ? 'increase' : deltaCost < 0 ? 'decrease' : 'stable';
        const trendText = deltaCost > 0 ? 'augmenté' : deltaCost < 0 ? 'diminué' : 'resté stable';

        focusEl.innerHTML = `
            <div class="focus-panel ${trendClass}">
                <div class="focus-header">
                    <h3>🎯 Focus: ${sensor.display_name}</h3>
                    <button id="close-focus" class="btn-close">✕</button>
                </div>
                
                <div class="focus-body">
                    <div class="focus-summary">
                        <div class="trend-indicator ${trendClass}">
                            <span class="icon">${trendIcon}</span>
                            <span class="text">Consommation a ${trendText}</span>
                        </div>
                        <p class="focus-description">
                            Le capteur <strong>${sensor.display_name}</strong> a consommé 
                            <strong>${sensor.event_energy_kwh.toFixed(3)} kWh</strong> pendant la période analysée, 
                            pour un coût de <strong>${sensor.event_cost_ttc.toFixed(2)} €</strong>.
                            <br><br>
                            Comparé à la période de référence, la consommation a ${trendText} de 
                            <strong>${Math.abs(deltaEnergy).toFixed(3)} kWh (${Math.abs(pctEnergy).toFixed(1)}%)</strong>, 
                            ce qui représente un coût ${deltaCost >= 0 ? 'supplémentaire' : 'économisé'} de 
                            <strong>${Math.abs(deltaCost).toFixed(2)} €</strong>.
                        </p>
                    </div>

                    <div class="focus-details">
                        <div class="detail-section">
                            <h4>Période de référence</h4>
                            <div class="detail-metrics">
                                <div class="metric">
                                    <span class="label">Énergie totale</span>
                                    <span class="value">${sensor.baseline_energy_kwh.toFixed(3)} kWh</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Coût HT</span>
                                    <span class="value">${sensor.baseline_cost_ht.toFixed(2)} €</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Coût TTC</span>
                                    <span class="value">${sensor.baseline_cost_ttc.toFixed(2)} €</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Par heure</span>
                                    <span class="value">${sensor.baseline_energy_kwh_per_hour.toFixed(3)} kWh/h</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Par jour</span>
                                    <span class="value">${sensor.baseline_energy_kwh_per_day.toFixed(3)} kWh/j</span>
                                </div>
                            </div>
                        </div>

                        <div class="detail-section">
                            <h4>Période analysée</h4>
                            <div class="detail-metrics">
                                <div class="metric">
                                    <span class="label">Énergie totale</span>
                                    <span class="value">${sensor.event_energy_kwh.toFixed(3)} kWh</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Coût HT</span>
                                    <span class="value">${sensor.event_cost_ht.toFixed(2)} €</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Coût TTC</span>
                                    <span class="value">${sensor.event_cost_ttc.toFixed(2)} €</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Par heure</span>
                                    <span class="value">${sensor.event_energy_kwh_per_hour.toFixed(3)} kWh/h</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Par jour</span>
                                    <span class="value">${sensor.event_energy_kwh_per_day.toFixed(3)} kWh/j</span>
                                </div>
                            </div>
                        </div>

                        <div class="detail-section delta-section">
                            <h4>Variations</h4>
                            <div class="detail-metrics">
                                <div class="metric">
                                    <span class="label">Δ Énergie</span>
                                    <span class="value ${trendClass}">${deltaEnergy >= 0 ? '+' : ''}${deltaEnergy.toFixed(3)} kWh (${pctEnergy >= 0 ? '+' : ''}${pctEnergy.toFixed(1)}%)</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Δ Coût TTC</span>
                                    <span class="value ${trendClass}">${deltaCost >= 0 ? '+' : ''}${deltaCost.toFixed(2)} € (${pctCost >= 0 ? '+' : ''}${pctCost.toFixed(1)}%)</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Δ Par heure</span>
                                    <span class="value">${sensor.delta_energy_kwh_per_hour >= 0 ? '+' : ''}${sensor.delta_energy_kwh_per_hour.toFixed(3)} kWh/h</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Δ Par jour</span>
                                    <span class="value">${sensor.delta_energy_kwh_per_day >= 0 ? '+' : ''}${sensor.delta_energy_kwh_per_day.toFixed(3)} kWh/j</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Scroll to focus panel
        focusEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Attach close button listener
        document.getElementById('close-focus')?.addEventListener('click', () => {
            this.hideFocus();
        });
    }

    /**
     * Hide focus panel
     */
    hideFocus() {
        this.focusEntityId = null;
        const focusEl = document.getElementById('comparison-focus');
        if (focusEl) {
            focusEl.innerHTML = '';
        }
    }

    /**
     * Render empty focus panel
     */
    renderFocusPanel() {
        const focusEl = document.getElementById('comparison-focus');
        if (focusEl) {
            focusEl.innerHTML = `
                <div class="focus-placeholder">
                    <p>💡 Cliquez sur "🎯 Focus" pour analyser un capteur en détail</p>
                </div>
            `;
        }
    }

    /**
     * Show/hide loading indicator
     */
    showLoading(show) {
        const loadingEl = document.getElementById('comparison-loading');
        if (loadingEl) loadingEl.style.display = show ? 'block' : 'none';
    }

    /**
     * Show results section
     */
    showResults() {
        const resultsEl = document.getElementById('comparison-results');
        if (resultsEl) resultsEl.style.display = 'block';
    }

    /**
     * Hide results section
     */
    hideResults() {
        const resultsEl = document.getElementById('comparison-results');
        if (resultsEl) resultsEl.style.display = 'none';
    }

    /**
     * Show error message
     */
    showError(message) {
        const errorEl = document.getElementById('comparison-error');
        if (errorEl) {
            errorEl.textContent = `❌ ${message}`;
            errorEl.style.display = 'block';
        }
    }

    /**
     * Hide error message
     */
    hideError() {
        const errorEl = document.getElementById('comparison-error');
        if (errorEl) {
            errorEl.style.display = 'none';
        }
    }
}

export default ComparisonController;
