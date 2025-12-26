// features/configuration/logic/sensorEnrichment.js
// Enrichissement des capteurs avec scores de qualité

"use strict";

import { computeSensorScore, getRecommendationLabel, getStars } from '../../../shared/utils/sensorScoring.js';

/**
 * Enrichit tous les capteurs avec leurs scores de qualité
 * Appelle l'API backend /get_sensor_quality_scores
 * 
 * @param {Object} allCapteurs - Map {entity_id: capteur}
 * @returns {Promise<Object>} allCapteurs enrichis
 */
export async function enrichWithQualityScores(allCapteurs) {
    try {
        const response = await fetch('/api/home_suivi_elec/get_sensor_quality_scores');
        if (!response.ok) {
            console.warn('[sensorEnrichment] API quality_scores non disponible');
            return allCapteurs;
        }
        
        const data = await response.json();
        if (!data.success || !data.sensors) return allCapteurs;
        
        // Créer un map pour accès rapide
        const scoresMap = {};
        data.sensors.forEach(s => {
            const score = computeSensorScore(s);
            scoresMap[s.entity_id] = {
                score,
                unit: s.unit,
                recommendation: getRecommendationLabel(score),
                stars: getStars(score)
            };
        });
        
        // Enrichir allCapteurs
        Object.keys(allCapteurs).forEach((entityId) => {
            const capteur = allCapteurs[entityId];
            if (!capteur) return;

            // 1) Rôle logique simple basé sur source_type
            const src = (capteur.source_type || "").toLowerCase();
            let ui_role = null;
            if (src.startsWith("power")) ui_role = "power";
            else if (src.startsWith("energy")) ui_role = "energy";
            capteur.ui_role = ui_role;

            // 2) Scores de qualité existants
            if (scoresMap[entityId]) {
                capteur.quality_score = scoresMap[entityId].score;
                capteur.quality_recommendation = scoresMap[entityId].recommendation;
                capteur.quality_stars = scoresMap[entityId].stars;
            }
        });

        // Log de contrôle sur quelques capteurs
        console.log(
            "[sensorEnrichment] sample roles",
            Object.keys(allCapteurs)
                .slice(0, 5)
                .map((id) => ({
                id,
                src: (allCapteurs[id].source_type || "").toLowerCase(),
                ui_role: allCapteurs[id].ui_role,
                }))
        );

        
        console.log('[sensorEnrichment] ✅ Scores de qualité chargés');
        return allCapteurs;
        
    } catch (error) {
        console.error('[sensorEnrichment] Erreur enrichissement scores:', error);
        return allCapteurs;
    }
}

/**
 * Récupère la map des puissances instantanées
 * @returns {Promise<Object>}
 */
export async function getInstantPowerMap() {
    try {
        const resp = await fetch("/api/home_suivi_elec/get_instant_puissance");
        if (!resp.ok) return {};
        return await resp.json();
    } catch {
        return {};
    }
}