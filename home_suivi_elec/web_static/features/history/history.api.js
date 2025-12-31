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
     * Fetch available sensors for history analysis
     * @returns {Promise<Array>} List of HSE energy sensors
     */
    async fetchSelectedSensors() {
        try {
            // ✅ Utilise fetch() natif car HttpClient ajoute un préfixe incorrect
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

    /**
     * Fetch history costs comparison
     * @param {Object} params - Comparison parameters
     * @param {string} params.baseline_start - Baseline period start (ISO 8601)
     * @param {string} params.baseline_end - Baseline period end (ISO 8601)
     * @param {string} params.event_start - Event period start (ISO 8601)
     * @param {string} params.event_end - Event period end (ISO 8601)
     * @param {string} [params.focus_entity_id] - Optional focus sensor
     * @param {string} [params.group_by='hour'] - Grouping: hour/day/week
     * @returns {Promise<Object>} Costs comparison data
     */
    /**
     * Fetch history costs comparison
     */
    async fetchHistoryCosts(params) {
        try {
            const response = await fetch('/api/home_suivi_elec/history_costs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(params),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (!json?.data) {
                throw new Error('No data in response');
            }

            console.log('[HISTORY-API] Costs fetched successfully');
            return json.data;
        } catch (error) {
            console.error('[HISTORY-API] fetchHistoryCosts failed:', error);
            throw error;
        }
    }

    /**
     * Fetch detailed analysis comparison
     * (si tu n’as pas d’endpoint dédié, on réutilise history_costs)
     */
    async analyzeComparison(params) {
        try {
            const response = await fetch('/api/home_suivi_elec/history_costs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(params),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const json = await response.json();

            if (!json?.data) {
                throw new Error('No data in response');
            }

            console.log('[HISTORY-API] Analysis completed');
            return json.data;
        } catch (error) {
            console.error('[HISTORY-API] analyzeComparison failed:', error);
            throw error;
        }
    }
}

export default HistoryAPI;
