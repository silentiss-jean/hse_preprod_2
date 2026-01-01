"use strict";

import { buildOverviewDashboardYaml } from "./templates/overviewCard.js";

/**
 * Compose le YAML final du dashboard à partir de différents types de cartes.
 * Pour l'instant, ne génère que le dashboard "overview" historique.
 *
 * @param {Object} ctx
 * @param {Array} ctx.sensors      - Liste des capteurs HSE.
 * @param {Array} [ctx.cardTypes]  - Types de cartes à générer (future extension).
 * @param {Object} [ctx.options]   - Options de génération (future extension).
 * @returns {string} YAML complet du dashboard.
 */
export function generateDashboardYaml({ sensors, cardTypes = ["overview"], options = {} }) {
    // Aujourd'hui : on ignore cardTypes/options et on reproduit l'existant.
    // Demain : on utilisera cardTypes pour appeler plusieurs templates.
    return buildOverviewDashboardYaml(sensors || []);
}
