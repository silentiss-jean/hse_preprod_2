"use strict";

/**
 * Gestion du cache et de l'état pour Detection
 */

let cachedData = null;
let lastRefreshTime = null;

/**
 * Récupère les données en cache
 */
export function getCachedDetection() {
    return cachedData;
}

/**
 * Met en cache les données de détection
 */
export function setCachedDetection(data) {
    cachedData = data;
    lastRefreshTime = new Date();
}

/**
 * Vide le cache
 */
export function clearCache() {
    cachedData = null;
    lastRefreshTime = null;
}

/**
 * Récupère le timestamp du dernier refresh
 */
export function getLastRefreshTime() {
    return lastRefreshTime;
}
