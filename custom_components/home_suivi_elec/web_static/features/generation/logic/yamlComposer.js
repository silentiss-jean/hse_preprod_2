"use strict";

import { buildOverviewDashboardYaml } from "./templates/overviewCard.js";
import { build_power_flow_card_plus_yaml } from "./templates/power_flow_card_plus.js";

/**
 * Compose le YAML final du dashboard à partir de différents types de cartes.
 *
 * @param {Object} ctx
 * @param {Array} ctx.sensors      - Liste des capteurs HSE.
 * @param {Array} [ctx.cardTypes]  - Types de cartes à générer.
 * @param {Object} [ctx.options]   - Options de génération.
 * @returns {string} YAML complet.
 */
export function generateDashboardYaml({ sensors, cardTypes = ["overview"], options = {} }) {
    const card_type = Array.isArray(cardTypes) && cardTypes.length > 0 ? cardTypes[0] : "overview";

    if (card_type === "power_flow_card_plus") {
        return build_power_flow_card_plus_yaml(options || {});
    }

    return buildOverviewDashboardYaml(sensors || []);
}
