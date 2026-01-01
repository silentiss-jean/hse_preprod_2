// shared/utils/sensorScoring.js
// Module partagé pour le scoring qualité des capteurs

"use strict";

/**
 * Calcule le score de qualité d'un capteur
 * Utilisé par:
 * - configuration.js (sélection automatique)
 * - selectionPanel.js (affichage badges UI)
 * 
 * @param {Object} sensor - Capteur avec unit, state_class, is_premium, etc.
 * @returns {number} Score de 0 à 150+
 */
export function computeSensorScore(sensor) {
    if (!sensor) return 0;
    
    let score = 0;
    const unit = (sensor.unit || sensor.unit_of_measurement || '').toLowerCase();
    
    // Priorité énergie (kWh) > puissance (W)
    if (unit.includes('kwh') || unit.includes('wh')) {
        score += 100;
    } else if (unit.includes('w')) {
        score += 50;
    }
    
    // State class
    if (sensor.state_class === 'total') score += 20;
    else if (sensor.state_class === 'measurement') score += 10;
    
    // Qualité intégration
    if (sensor.is_premium) score += 15;
    if (['platinum', 'gold'].includes(sensor.quality_scale)) score += 10;
    
    // Capteur physique vs virtuel
    if (!sensor.is_virtual) score += 10;
    
    // Disponibilité
    if (sensor.state && sensor.state !== 'unavailable') score += 5;
    
    return score;
}

/**
 * Convertit un score en label lisible
 * @param {number} score 
 * @returns {string}
 */
export function getRecommendationLabel(score) {
    if (score >= 130) return '✅ EXCELLENT';
    if (score >= 100) return '✅ BON';
    if (score >= 70) return '⚠️ ACCEPTABLE';
    if (score >= 50) return '⚠️ MOYEN';
    return '❌ FAIBLE';
}

/**
 * Convertit un score en étoiles
 * @param {number} score 
 * @returns {string}
 */
export function getStars(score) {
    if (score >= 130) return '⭐⭐⭐';
    if (score >= 100) return '⭐⭐⭐';
    if (score >= 70) return '⭐⭐';
    if (score >= 50) return '⭐';
    return '☆';
}

/**
 * Génère le HTML du badge de qualité
 * @param {Object} sensor - Capteur enrichi avec quality_score
 * @returns {string} HTML du badge
 */
export function createQualityBadgeHTML(sensor) {
    if (!sensor || !sensor.quality_score) return '';
    
    const score = sensor.quality_score;
    let badgeClass = 'quality-badge';
    
    if (score >= 130) badgeClass += ' excellent';
    else if (score >= 100) badgeClass += ' good';
    else if (score >= 70) badgeClass += ' acceptable';
    else if (score >= 50) badgeClass += ' medium';
    else badgeClass += ' poor';
    
    const icon = (sensor.unit || '').toLowerCase().includes('kwh') ? '🔋' : '⚡';
    
    return `
        <div class="${badgeClass}">
            ${icon}
            <span class="quality-label">${sensor.quality_recommendation || ''}</span>
            <span class="quality-stars">${sensor.quality_stars || ''}</span>
            <span class="quality-score">${score}/150</span>
        </div>
    `;
}