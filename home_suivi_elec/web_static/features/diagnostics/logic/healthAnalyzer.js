'use strict';

/**
 * Analyse de la santé du backend
 */

const HEALTH_CONFIG = {
  REFRESH_INTERVAL: 30000, // 30s
  ERROR_RATE_THRESHOLD: 5,
  LATENCY_THRESHOLD: 1000, // 1s
  UPTIME_CRITICAL: 95,     // %
  MEMORY_WARNING: 70,      // %
  MEMORY_CRITICAL: 90      // %
};

/**
 * Analyse les données de santé et génère des alertes
 * @param {Object} health - Données de santé
 * @returns {Array} Liste d'alertes
 */
export function getHealthAlerts(health) {
  const alerts = [];

  // Uptime critique
  if (health.uptime_percent && health.uptime_percent < HEALTH_CONFIG.UPTIME_CRITICAL) {
    alerts.push({
      level: 'error',
      message: `⚠️ Uptime faible: ${health.uptime_percent}%`
    });
  }

  // Taux d'erreurs élevé
  if (health.errors_per_hour && health.errors_per_hour > HEALTH_CONFIG.ERROR_RATE_THRESHOLD) {
    alerts.push({
      level: 'warning',
      message: `⚠️ Erreurs: ${health.errors_per_hour}/h`
    });
  }

  // Latence élevée
  if (health.avg_latency && health.avg_latency > HEALTH_CONFIG.LATENCY_THRESHOLD) {
    alerts.push({
      level: 'warning',
      message: `⚠️ Latence: ${health.avg_latency}ms`
    });
  }

  // Mémoire critique
  if (health.memory_percent) {
    if (health.memory_percent > HEALTH_CONFIG.MEMORY_CRITICAL) {
      alerts.push({
        level: 'error',
        message: `🔴 Mémoire critique: ${health.memory_percent}%`
      });
    } else if (health.memory_percent > HEALTH_CONFIG.MEMORY_WARNING) {
      alerts.push({
        level: 'warning',
        message: `⚠️ Mémoire élevée: ${health.memory_percent}%`
      });
    }
  }

  return alerts;
}

/**
 * Détermine la variante (couleur) selon l'uptime
 */
export function getUptimeVariant(percent) {
  if (!percent) return 'info';
  if (percent >= 99) return 'success';
  if (percent >= HEALTH_CONFIG.UPTIME_CRITICAL) return 'warning';
  return 'error';
}

/**
 * Détermine la variante selon le taux d'erreurs
 */
export function getErrorVariant(errors) {
  if (!errors) return 'success';
  if (errors < HEALTH_CONFIG.ERROR_RATE_THRESHOLD) return 'success';
  if (errors < HEALTH_CONFIG.ERROR_RATE_THRESHOLD * 2) return 'warning';
  return 'error';
}

/**
 * Détermine la variante selon la latence
 */
export function getLatencyVariant(latency) {
  if (!latency) return 'info';
  if (latency < 500) return 'success';
  if (latency < HEALTH_CONFIG.LATENCY_THRESHOLD) return 'warning';
  return 'error';
}

/**
 * Détermine la variante selon l'utilisation mémoire
 */
export function getMemoryVariant(percent) {
  if (!percent) return 'info';
  if (percent < HEALTH_CONFIG.MEMORY_WARNING) return 'success';
  if (percent < HEALTH_CONFIG.MEMORY_CRITICAL) return 'warning';
  return 'error';
}

export { HEALTH_CONFIG };
