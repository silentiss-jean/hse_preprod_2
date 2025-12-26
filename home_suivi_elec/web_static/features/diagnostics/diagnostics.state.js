'use strict';

/**
 * Gestion de l'état global du module diagnostics
 */

// Cache des données
const dataCache = {
  sensors: null,
  integrations: null,
  health: null,
  lastUpdate: null
};

// État de l'UI
let activeSubTab = 'capteurs';
let autoRefreshTimer = null;
let healthMetricsHistory = [];

/**
 * Récupère le sous-onglet actif
 */
export function getActiveSubTab() {
  return activeSubTab;
}

/**
 * Définit le sous-onglet actif
 */
export function setActiveSubTab(tab) {
  activeSubTab = tab;
}

/**
 * Récupère les données en cache
 */
export function getCachedData(key) {
  return dataCache[key];
}

/**
 * Met en cache des données
 */
export function setCachedData(key, value) {
  dataCache[key] = value;
  dataCache.lastUpdate = Date.now();
}

/**
 * Vide le cache
 */
export function clearCache() {
  dataCache.sensors = null;
  dataCache.integrations = null;
  dataCache.health = null;
  dataCache.lastUpdate = null;
  console.log('[diagnostics.state] Cache vidé');
}

/**
 * Récupère l'historique des métriques de santé
 */
export function getHealthHistory() {
  return healthMetricsHistory;
}

/**
 * Ajoute une entrée à l'historique de santé
 */
export function addHealthMetric(metric) {
  healthMetricsHistory.push({
    timestamp: Date.now(),
    ...metric
  });
  
  // Limiter à 100 entrées
  if (healthMetricsHistory.length > 100) {
    healthMetricsHistory = healthMetricsHistory.slice(-100);
  }
}

/**
 * Récupère le timer d'auto-refresh
 */
export function getAutoRefreshTimer() {
  return autoRefreshTimer;
}

/**
 * Définit le timer d'auto-refresh
 */
export function setAutoRefreshTimer(timer) {
  autoRefreshTimer = timer;
}

/**
 * Nettoie toutes les ressources
 */
export function cleanup() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  clearCache();
  healthMetricsHistory = [];
  console.log('[diagnostics.state] Cleanup effectué');
}
