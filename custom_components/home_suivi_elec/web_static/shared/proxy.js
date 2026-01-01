// shared/proxy.js
"use strict";

import { ENDPOINTS } from './constants.js';

/**
 * Appelle une API via le proxy backend
 * @param {string} endpoint - L'endpoint à appeler (ex: "/api/home_suivi_elec/get_sensors")
 * @param {string} method - Méthode HTTP (GET, POST, etc.)
 * @param {object} payload - Données à envoyer (pour POST)
 * @returns {Promise} - Réponse JSON
 */
export async function fetchViaProxy(endpoint, method = "GET", payload = null) {
    const resp = await fetch(ENDPOINTS.PROXY, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint, method, payload })
    });

    if (!resp.ok) {
        throw new Error(`Proxy error: ${resp.status}`);
    }

    return await resp.json();
}

/**
 * Helpers pour endpoints courants
 */

/**
 * Récupère la configuration
 * @returns {Promise<Object>}
 */
export async function fetchConfig() {
    return fetchViaProxy(ENDPOINTS.CONFIG, "GET");
}

/**
 * Lance une détection automatique
 * @returns {Promise<Object>}
 */
export async function fetchDetection() {
    return fetchViaProxy(ENDPOINTS.DETECTION, "GET");
}

/**
 * Récupère les doublons détectés
 * @returns {Promise<Object>}
 */
export async function fetchDuplicates() {
    return fetchViaProxy(ENDPOINTS.DUPLICATES, "GET");
}

/**
 * Récupère les diagnostics
 * @returns {Promise<Object>}
 */
export async function fetchDiagnostics() {
    return fetchViaProxy(ENDPOINTS.DIAGNOSTICS, "GET");
}

/**
 * Sauvegarde la configuration
 * @param {Object} config - Configuration à sauvegarder
 * @returns {Promise<Object>}
 */
export async function saveConfig(config) {
    return fetchViaProxy(ENDPOINTS.CONFIG, "POST", config);
}

/**
 * Lance une migration
 * @param {Object} params - Paramètres de migration
 * @returns {Promise<Object>}
 */
export async function startMigration(params) {
    return fetchViaProxy(ENDPOINTS.MIGRATION, "POST", params);
}
