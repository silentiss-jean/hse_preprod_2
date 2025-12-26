// shared/components/Badge.js
"use strict";

import { QUALITY_LEVELS } from '../constants.js';

export class Badge {
    /**
     * Crée un badge générique
     * @param {string} text - Texte du badge
     * @param {string} type - Type (success, error, warning, info)
     */
    static create(text, type = 'info') {
        const badge = document.createElement('span');
        badge.className = `badge badge-${type}`;
        badge.textContent = text;
        return badge;
    }

    /**
     * Crée un badge de qualité avec étoiles
     * @param {number} score - Score qualité (0-100)
     */
    static quality(score) {
        const level = this.getQualityLevel(score);
        const badge = document.createElement('span');
        badge.className = 'badge-quality';
        badge.style.backgroundColor = level.color;
        badge.style.color = '#fff';
        badge.style.padding = '4px 8px';
        badge.style.borderRadius = '4px';
        badge.style.fontSize = '12px';
        badge.style.fontWeight = 'bold';

        const stars = '⭐'.repeat(Math.ceil(score / 25));
        badge.innerHTML = `${stars} ${level.label}`;

        return badge;
    }

    /**
     * Détermine le niveau de qualité
     */
    static getQualityLevel(score) {
        for (let [key, level] of Object.entries(QUALITY_LEVELS)) {
            if (score >= level.score) {
                return level;
            }
        }
        return QUALITY_LEVELS.MAUVAIS;
    }
}
