"use strict";

/**
 * API pour le module Generation
 * Encapsule les appels REST vers le backend
 */

/**
 * Récupère la liste des sensors HSE pour la génération Lovelace.
 * Source backend : /api/home_suivi_elec/lovelace_sensors
 * @returns {Promise<Array>} Liste de capteurs enrichis
 */
export async function getLovelaceSensors() {
    const response = await fetch('/api/home_suivi_elec/lovelace_sensors');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
}
