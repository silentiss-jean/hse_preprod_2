"use strict";

/**
 * Template YAML pour le dashboard "overview" actuel.
 * C'est l'extraction directe de ton ancien buildLovelaceYAML().
 */

/**
 * Construit le YAML complet du dashboard overview.
 * @param {Array} sensors - Liste des capteurs HSE sélectionnés.
 * @returns {string} YAML du dashboard Lovelace.
 */
export function buildOverviewDashboardYaml(sensors) {
    return `# ⚡ Home Suivi Élec - Dashboard Auto-généré
# Généré le ${new Date().toLocaleString('fr-FR')}
# ${sensors.length} sensors inclus


title: ⚡ Home Suivi Élec
views:
  - title: Vue d'ensemble
    path: overview
    icon: mdi:home-analytics
    cards:
      - type: entities
        title: 📊 Top ${sensors.length} consommateurs
        show_header_toggle: false
        entities:
${sensors.map(s => `          - entity: ${s.entity_id}`).join('\n')}


      - type: history-graph
        title: 📈 Consommation 7 derniers jours
        hours_to_show: 168
        entities:
${sensors.slice(0, Math.min(5, sensors.length)).map(s => `          - ${s.entity_id}`).join('\n')}
`;
}
