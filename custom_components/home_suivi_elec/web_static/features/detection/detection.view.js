"use strict";

/**
 * Vues pour le module Detection
 */

// Ré-exporter les vues communes
export { renderLoader, renderError } from '../../shared/views/commonViews.js';

import { Card } from '../../shared/components/Card.js';
import { createElement } from '../../shared/utils/dom.js';

/**
 * Génère le layout HTML complet de Detection
 * @returns {string} HTML
 */
export function renderDetectionLayout() {
    return `
        <div class="detection-layout">
            <div class="detection-header">
                <h2>🔍 Détection des capteurs</h2>
            </div>
            
            <div class="detection-stats card">
                <p><strong>Total capteurs détectés :</strong> <span id="total">-</span></p>
                <p><strong>Dernière mise à jour :</strong> <span id="lastRefresh">-</span></p>
                <button id="refreshDetection" class="primary" type="button">🔄 Rafraîchir</button>
            </div>
            
            <div id="content-detection"></div>
        </div>
    `;
}

/**
 * Affiche un message si aucun capteur sélectionné
 */
export function renderEmptyState(container) {
    if (!container) {
        console.error('[detection.view] renderEmptyState: container requis');
        return;
    }
    
    container.innerHTML = '';
    
    const emptyP = createElement('p', { style: 'color: #666;' });
    emptyP.textContent = "Aucun capteur sélectionné. Configurez vos capteurs dans l'onglet Configuration.";

    const emptyCard = Card.create('Capteurs détectés', emptyP, '🔍');
    container.appendChild(emptyCard);
}

/**
 * Met à jour les compteurs dans l'UI
 */
export function updateCounters(total) {
    const totalElem = document.getElementById('total');
    const refreshElem = document.getElementById('lastRefresh');

    if (totalElem) {
        totalElem.textContent = total;
    }

    if (refreshElem) {
        refreshElem.textContent = new Date().toLocaleTimeString('fr-FR');
    }
}
