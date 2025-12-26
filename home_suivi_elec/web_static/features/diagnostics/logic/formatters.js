'use strict';

/**
 * Formateurs spécifiques au module diagnostics
 */

/**
 * Formate une durée en secondes
 * @param {number} seconds - Durée en secondes
 * @returns {string} Durée formatée
 */
export function formatUptimeDuration(seconds) {
  if (!seconds) return 'N/A';
  
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  
  if (days > 0) {
    return `${days}j ${hours}h`;
  }
  return `${hours}h`;
}


/**
 * Formate une taille en octets
 * @param {number} bytes - Taille en octets
 * @returns {string} Taille formatée
 */
export function formatBytes(bytes) {
  if (!bytes) return 'N/A';
  
  const units = ['B', 'KB', 'MB', 'GB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${units[i]}`;
}

/**
 * Formate un timestamp en "il y a X"
 * @param {string|number} timestamp - Timestamp
 * @returns {string} Temps relatif
 */
export function formatTimeSince(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;

  if (diffMs < 60000) return 'Il y a < 1 min';
  if (diffMs < 3600000) return `Il y a ${Math.floor(diffMs / 60000)} min`;
  if (diffMs < 86400000) return `Il y a ${Math.floor(diffMs / 3600000)}h`;
  return `Il y a ${Math.floor(diffMs / 86400000)}j`;
}
