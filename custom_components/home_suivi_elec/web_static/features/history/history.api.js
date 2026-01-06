/**
 * @file history.api.js
 * @description API client for History Analysis endpoints
 */

import { HttpClient } from '../../shared/api/httpClient.js';

class HistoryAPI {
    constructor() {
        this.client = new HttpClient('/api/home_suivi_elec');
        console.log('[HISTORY-API] Initialized with HttpClient');
    }

    /**
     * GET current costs (Vue "Aujourd'hui")
     * @returns {Promise<Object>} Current costs data with top_10 and other_sensors
     */
    async fetchCurrentCosts() {
        try {
            const response = await fetch('/api/home_suivi_elec/history/current_costs', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (json.error || !json.data) {
                throw new Error(json.message || 'No data in response');
            }

            console.log(`[HISTORY-API] Current costs: ${json.data.sensor_count} capteurs, total=${json.data.total_cost_ttc}€`);
            return json.data;
        } catch (error) {
            console.error('[HISTORY-API] fetchCurrentCosts failed:', error);
            throw error;
        }
    }

    /**
     * POST cost analysis (Comparaisons entre périodes)
     * @param {Object} params - Analysis parameters
     * @param {string} params.baseline_start - Baseline period start (ISO 8601)
     * @param {string} params.baseline_end - Baseline period end (ISO 8601)
     * @param {string} params.event_start - Event period start (ISO 8601)
     * @param {string} params.event_end - Event period end (ISO 8601)
     * @param {Object} [params.pricing] - Pricing configuration
     * @param {number} [params.top_limit=10] - Number of top variations to return
     * @param {string} [params.sort_by='cost_ttc'] - Sort by: 'cost_ttc' or 'energy_kwh'
     * @returns {Promise<Object>} Cost analysis with top_variations and other_sensors
     */
    async analyzeCostComparison(params) {
        try {
            const response = await fetch('/api/home_suivi_elec/history/cost_analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(params)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (json.error || !json.data) {
                throw new Error(json.message || 'No data in response');
            }

            console.log('[HISTORY-API] Cost analysis completed:', json.data.total_comparison);
            return json.data;
        } catch (error) {
            console.error('[HISTORY-API] analyzeCostComparison failed:', error);
            throw error;
        }
    }

    /**
     * Fetch available sensors for history analysis (legacy - keep for compatibility)
     * @returns {Promise<Array>} List of HSE energy sensors
     */
    async fetchSelectedSensors() {
        try {
            const response = await fetch('/api/home_suivi_elec/sensors');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (!json.data || !json.data.sensors) {
                throw new Error('No sensors in response');
            }

            console.log(`[HISTORY-API] Fetched ${json.data.sensors.length} sensors`);
            return json.data.sensors;
        } catch (error) {
            console.error('[HISTORY-API] fetchSelectedSensors failed:', error);
            return [];
        }
    }
}

export default HistoryAPI;
