"use strict";

/**
 * Normalise la réponse API en structure groupée par intégration
 * @param {Array|Object} sensorsRaw - Données brutes de l'API
 * @returns {Object} - {integration: [sensors...]}
 */
export function normalizeSensors(sensorsRaw) {
    if (!sensorsRaw) return {};

    // Si tableau, grouper par intégration
    if (Array.isArray(sensorsRaw)) {
        return sensorsRaw.reduce((acc, sensor) => {
            const integration = sensor.integration || "unknown";
            acc[integration] = acc[integration] || [];
            acc[integration].push(sensor);
            return acc;
        }, {});
    }

    // Si déjà objet groupé, retourner tel quel
    if (typeof sensorsRaw === "object") return sensorsRaw;
    
    return {};
}

/**
 * Compte le total de capteurs dans un objet groupé
 * @param {Object} grouped - Capteurs groupés par intégration
 * @returns {number}
 */
export function countTotalFromGrouped(grouped) {
    return Object.values(grouped).reduce(
        (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0), 
        0
    );
}
