'use strict';

/**
 * Extraction et traitement des intégrations
 */

const INTEGRATION_ICONS = {
  'shelly': '🔌',
  'modbus': '🔧',
  'mqtt': '📡',
  'tasmota': '💡',
  'esphome': '🏠',
  'homeassistant': '🏡',
  'utility_meter': '⚡',
  'template': '📝',
  'sensor': '📊',
  'tuya': '🔮',
  'powercalc': '🔋',
  'min_max': '📈'
};

/**
 * Extrait les intégrations depuis les données API
 * @param {Object} apiData - Données brutes de l'API
 * @returns {Object} Map des intégrations
 */
export function extractIntegrations(apiData) {
  const integrations = {};

  // Traiter selected
  if (apiData.selected) {
    Object.entries(apiData.selected).forEach(([integration, sensors]) => {
      if (!integrations[integration]) {
        integrations[integration] = {
          displayName: formatIntegrationName(integration),
          icon: getIntegrationIcon(integration),
          selected: [],
          available: [],
          total: 0,
          state: 'active'
        };
      }
      integrations[integration].selected = sensors;
      integrations[integration].total += sensors.length;
    });
  }

  // Traiter alternatives
  if (apiData.alternatives) {
    Object.entries(apiData.alternatives).forEach(([integration, sensors]) => {
      if (!integrations[integration]) {
        integrations[integration] = {
          displayName: formatIntegrationName(integration),
          icon: getIntegrationIcon(integration),
          selected: [],
          available: [],
          total: 0,
          state: 'active'
        };
      }
      integrations[integration].available = sensors;
      integrations[integration].total += sensors.length;
    });
  }

  return integrations;
}

/**
 * Formate le nom d'une intégration
 * @param {string} integration - Nom brut
 * @returns {string} Nom formaté
 */
function formatIntegrationName(integration) {
  return integration
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Retourne l'icône d'une intégration
 * @param {string} integration - Nom de l'intégration
 * @returns {string} Emoji icône
 */
export function getIntegrationIcon(integration) {
  return INTEGRATION_ICONS[integration?.toLowerCase()] || '🔌';
}

/**
 * Calcule les statistiques globales
 * @param {Object} integrations - Map des intégrations
 * @returns {Object} Statistiques
 */
export function getIntegrationsStats(integrations) {
  let totalSelected = 0;
  let totalAvailable = 0;
  let totalSensors = 0;

  Object.values(integrations).forEach(integration => {
    totalSelected += integration.selected.length;
    totalAvailable += integration.available.length;
    totalSensors += integration.total;
  });

  return {
    count: Object.keys(integrations).length,
    totalSelected,
    totalAvailable,
    totalSensors
  };
}
