// shared/utils/formatters.js
"use strict";

/**
 * Formate une puissance en W ou kW
 */
export function formatPower(watts) {
    if (watts === null || watts === undefined) return 'N/A';

    const value = parseFloat(watts);
    if (isNaN(value)) return 'N/A';

    if (value >= 1000) {
        return `${(value / 1000).toFixed(2)} kW`;
    }
    return `${value.toFixed(0)} W`;
}

/**
 * Formate une énergie en Wh ou kWh
 */
export function formatEnergy(wattHours) {
    if (wattHours === null || wattHours === undefined) return 'N/A';

    const value = parseFloat(wattHours);
    if (isNaN(value)) return 'N/A';

    if (value >= 1000) {
        return `${(value / 1000).toFixed(2)} kWh`;
    }
    return `${value.toFixed(0)} Wh`;
}

/**
 * Formate une date
 */
export function formatDate(date, format = 'datetime') {
    if (!date) return 'N/A';

    const d = new Date(date);
    if (isNaN(d.getTime())) return 'N/A';

    const options = {
        'date': { year: 'numeric', month: '2-digit', day: '2-digit' },
        'time': { hour: '2-digit', minute: '2-digit', second: '2-digit' },
        'datetime': { 
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        }
    };

    return d.toLocaleString('fr-FR', options[format]);
}

/**
 * Formate un pourcentage
 */
export function formatPercent(value, decimals = 1) {
    if (value === null || value === undefined) return 'N/A';

    const num = parseFloat(value);
    if (isNaN(num)) return 'N/A';

    return `${num.toFixed(decimals)}%`;
}

/**
 * Formate une durée en secondes
 */
export function formatDuration(seconds) {
    if (!seconds || seconds < 0) return 'N/A';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
}
/**
 * Formate une énergie en kWh (tableaux Summary)
 */
export function formatKwh(value, decimals = 3) {
  if (value === null || value === undefined) return "0.000";
  const num = parseFloat(value);
  if (isNaN(num)) return "0.000";
  return num.toFixed(decimals);
}

/**
 * Formate un montant en € (HT / TTC)
 */
export function formatEuro(value, decimals = 2) {
  if (value === null || value === undefined) return "0.00";
  const num = parseFloat(value);
  if (isNaN(num)) return "0.00";
  return num.toFixed(decimals);
}
