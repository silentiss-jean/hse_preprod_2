/**
 * Formatters spécifiques au module History
 * Réutilise les formatters partagés + ajouts spécifiques
 */
import { formatEuro, formatKwh, formatPercent } from '../../../shared/utils/formatters.js';

/**
 * Formate une durée en secondes en texte lisible
 */
export function formatDurationHuman(seconds) {
    const hours = Math.floor(seconds / 3600);
    const days = Math.floor(hours / 24);
    
    if (days >= 1) {
        const remainingHours = hours % 24;
        return remainingHours > 0 ? `${days}j ${remainingHours}h` : `${days}j`;
    }
    
    if (hours >= 1) {
        const minutes = Math.floor((seconds % 3600) / 60);
        return minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h`;
    }
    
    const minutes = Math.floor(seconds / 60);
    return `${minutes}min`;
}

/**
 * Formate une date en format court (DD/MM/YYYY HH:mm)
 */
export function formatDateShort(date) {
    if (!date) return '-';
    const d = new Date(date);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

/**
 * Formate un delta avec signe + couleur
 */
export function formatDeltaWithSign(value, formatter, options = {}) {
    const { inverted = false } = options;
    
    if (value === 0 || value === null || value === undefined) {
        return { text: formatter(0), color: 'neutral' };
    }
    
    const sign = value > 0 ? '+' : '';
    const color = inverted 
        ? (value > 0 ? 'danger' : 'success')
        : (value > 0 ? 'success' : 'danger');
    
    return {
        text: `${sign}${formatter(value)}`,
        color,
    };
}

/**
 * Retourne une classe CSS selon la variance (pour badges)
 */
export function getVarianceClass(pct) {
    const abs = Math.abs(pct);
    if (abs < 5) return 'neutral';
    if (abs < 20) return 'warning';
    return 'danger';
}

export { formatEuro, formatKwh, formatPercent };
