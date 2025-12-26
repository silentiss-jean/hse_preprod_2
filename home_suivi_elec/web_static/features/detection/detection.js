"use strict";

/**
 * Orchestrateur principal du module Detection
 */

import { getSensorsDetection } from './detection.api.js';
import { setCachedDetection } from './detection.state.js';
import { 
    renderDetectionLayout,
    renderLoader, 
    renderError, 
    renderEmptyState, 
    updateCounters 
} from './detection.view.js';
import { normalizeSensors } from './logic/dataTransformer.js';
import { buildReferenceCard, buildIntegrationAccordion, buildAlternativesAccordion } from './logic/cardBuilder.js';
import { Toast } from '../../shared/components/Toast.js';
import { Button } from '../../shared/components/Button.js';

/**
 * Point d'entrée principal - Charge et affiche la détection des capteurs
 */
export async function loadDetection() {
    const container = document.getElementById('detection');
    if (!container) {
        console.error('[detection] Container #detection introuvable');
        return;
    }

    try {
        // 1. Générer le layout HTML complet
        container.innerHTML = renderDetectionLayout();

        // 2. Récupérer le container de contenu
        const content = document.getElementById('content-detection');
        if (!content) {
            throw new Error('Container content-detection introuvable');
        }

        // 3. Afficher spinner
        renderLoader(content, 'Chargement des capteurs...');

        // 4. Charger données API
        const data = await getSensorsDetection();
        setCachedDetection(data);

        // 5. Traiter les données
        const selected = normalizeSensors(data.selected || {});
        const alternatives = normalizeSensors(data.alternatives || {});
        const reference = data.reference_sensor || {};

        // 6. Render
        content.innerHTML = '';
        let total = 0;

        // Afficher référence
        if (reference && Object.keys(reference).length > 0) {
            const refCard = buildReferenceCard(reference);
            content.appendChild(refCard);
        }

        // Afficher capteurs sélectionnés
        if (Object.keys(selected).length > 0) {
            Object.entries(selected).forEach(([integration, sensors]) => {
                if (Array.isArray(sensors) && sensors.length > 0) {
                    const accordion = buildIntegrationAccordion(integration, sensors, true);
                    content.appendChild(accordion);
                    total += sensors.length;
                }
            });
        } else {
            renderEmptyState(content);
        }

        // Afficher alternatives
        if (Object.keys(alternatives).length > 0) {
            const altAccordion = buildAlternativesAccordion(alternatives);
            content.appendChild(altAccordion);
        }

        // Mettre à jour compteurs
        updateCounters(total);

        // Bind bouton refresh
        const refreshBtn = document.getElementById('refreshDetection');
        if (refreshBtn && !refreshBtn.hasAttribute('data-bound')) {
            refreshBtn.addEventListener('click', async () => {
                await loadDetection();
            });
            refreshBtn.setAttribute('data-bound', 'true');
        }

        // Toast succès
        Toast.success(`${total} capteur(s) chargé(s)`);

    } catch (error) {
        console.error('[detection] Erreur:', error);
        const content = document.getElementById('content-detection');
        if (content) {
            renderError(content, error);
        } else {
            renderError(container, error);
        }
    }
}
