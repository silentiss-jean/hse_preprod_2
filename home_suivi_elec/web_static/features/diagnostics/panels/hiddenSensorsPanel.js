'use strict';

/**
 * Panel Capteurs Cachés - Diagnostics avancés
 * Analyse les capteurs désactivés, manquants ou problématiques
 */

import { createElement } from '../../../shared/utils/dom.js';
import { Card } from '../../../shared/components/Card.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { showToast } from '../../../shared/uiToast.js';

console.info('[hiddenSensorsPanel] Module chargé');

/**
 * Active un capteur désactivé via l'API HSE
 */
async function enableSensorAction(entity_id) {
  try {
    const response = await fetch('/api/home_suivi_elec/config/enable_sensor', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({entity_id})
    });
    
    const result = await response.json();
    
    if (result.error === false) {
      showToast(`✅ ${entity_id} activé ! Rechargement dans 2s...`, 'success');
      setTimeout(() => location.reload(), 2000);
    } else {
      showToast(`❌ ${result.error || 'Erreur inconnue'}`, 'error');
    }
  } catch (error) {
    console.error('[enableSensorAction] Erreur:', error);
    showToast(`❌ Erreur réseau: ${error.message}`, 'error');
  }
}


/**
 * Point d'entrée principal
 */
export async function loadHiddenSensorsPanel(container) {
  try {
    console.log('[hiddenSensorsPanel] Chargement...');
    
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Analyse des capteurs cachés...')
    ]));

    const data = await fetchHiddenSensors();
    renderHiddenSensorsInterface(container, data);

    showToast('Analyse des capteurs cachés terminée', 'success');

  } catch (error) {
    console.error('[hiddenSensorsPanel] Erreur:', error);
    container.innerHTML = '';
    container.appendChild(Card.create('Erreur', 
      createElement('p', { class: 'error-message' }, [
        `Impossible de charger les capteurs cachés: ${error.message}`
      ])
    ));
  }
}

/**
 * Récupère les capteurs cachés depuis l'API
 */
async function fetchHiddenSensors() {
  const response = await fetch('/api/home_suivi_elec/hidden_sensors');
  const result = await response.json();

  if (!result.success) {
    throw new Error(result.error || 'Erreur API');
  }

  return result;
}

/**
 * Rendu de l'interface
 */
function renderHiddenSensorsInterface(container, data) {
  container.innerHTML = '';

  const summaryCard = renderSummaryCard(data.summary);
  const inactiveIntegrationsCard = renderInactiveIntegrations(data.hidden_sensors.inactive_integrations);
  const disabledByUserCard = renderDisabledSensors(data.hidden_sensors.disabled_by_user, 'Désactivés par vous');
  const missingAttributesCard = renderMissingAttributes(data.hidden_sensors);
  const unavailableCard = renderUnavailableSensors(data.hidden_sensors.unavailable);
  const disabledByIntegrationCard = renderDisabledSensors(data.hidden_sensors.disabled_by_integration, 'Désactivés par intégration');
  const grid = createElement('div', { class: 'hidden-sensors-grid' }, [
    summaryCard,
    inactiveIntegrationsCard,
    disabledByUserCard,
    disabledByIntegrationCard,
    missingAttributesCard,
    unavailableCard,
  ]);



  container.appendChild(grid);
}

/**
 * Carte résumé
 */
function renderSummaryCard(summary) {
  const totalBadge = Badge.create(`${summary.total_hidden} capteurs cachés`, 
    summary.total_hidden > 0 ? 'warning' : 'success'
  );

  const stats = createElement('div', { class: 'summary-stats' }, [
    createElement('div', { class: 'stat-item' }, [
      createElement('span', { class: 'stat-value' }, [String(summary.disabled_by_user_count)]),
      createElement('span', { class: 'stat-label' }, ['Désactivés par vous'])
    ]),
    createElement('div', { class: 'stat-item' }, [
      createElement('span', { class: 'stat-value' }, [String(summary.disabled_by_integration_count)]),
      createElement('span', { class: 'stat-label' }, ['Désactivés par intégration'])
    ]),
    createElement('div', { class: 'stat-item' }, [
      createElement('span', { class: 'stat-value' }, [String(summary.missing_attributes_count)]),
      createElement('span', { class: 'stat-label' }, ['Attributs manquants'])
    ]),
    createElement('div', { class: 'stat-item' }, [
      createElement('span', { class: 'stat-value' }, [String(summary.unavailable_count)]),
      createElement('span', { class: 'stat-label' }, ['Indisponibles'])
    ]),
  ]);

  const content = createElement('div', {}, [
    createElement('h3', {}, ['📊 Résumé']),
    totalBadge,
    stats,
  ]);

  return Card.create('', content);
}

/**
 * Intégrations inactives (installées mais sans capteurs actifs)
 */
function renderInactiveIntegrations(integrations) {
  if (!integrations || integrations.length === 0) {
    return Card.create('🔌 Intégrations Inactives', 
      createElement('p', { class: 'no-issues' }, ['✅ Toutes vos intégrations ont des capteurs actifs'])
    );
  }

  const list = createElement('div', { class: 'integrations-list' }, 
    integrations.map(integ => {
      const item = createElement('div', { class: 'integration-item warning' }, [
        createElement('div', { class: 'integration-info' }, [
          createElement('strong', {}, [`⚠️ ${integ.integration}`]),
          createElement('p', {}, [integ.reason]),
          createElement('small', {}, [
            `${integ.total_sensors} capteur(s) total, ${integ.hidden_sensors} caché(s)`
          ])
        ]),
        Button.create('Activer les capteurs', 
          () => openHAEntityRegistry(integ.integration), 
          'secondary'
        )
      ]);

      return item;
    })
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, ['🔌 Intégrations Inactives']),
    createElement('p', { class: 'section-description' }, [
      'Ces intégrations sont installées mais tous leurs capteurs sont désactivés.'
    ]),
    list,
  ]);

  return Card.create('', content);
}

/**
 * Capteurs désactivés
 */
function renderDisabledSensors(sensors, title) {
  if (!sensors || sensors.length === 0) {
    return Card.create(title, 
      createElement('p', { class: 'no-issues' }, ['Aucun capteur désactivé'])
    );
  }

  const list = createElement('div', { class: 'sensors-list' }, 
    sensors.map(sensor => renderSensorItem(sensor, true))
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, [title]),
    createElement('p', { class: 'section-description' }, [
      `${sensors.length} capteur(s) désactivé(s). Activez-les si nécessaire.`
    ]),
    list,
  ]);

  return Card.create('', content);
}

/**
 * Capteurs avec attributs manquants (problème Tuya etc.)
 */
function renderMissingAttributes(hiddenSensors) {
  const missing = [
    ...hiddenSensors.missing_unit,
    ...hiddenSensors.missing_device_class
  ];

  if (missing.length === 0) {
    return Card.create('🏷️ Attributs Manquants', 
      createElement('p', { class: 'no-issues' }, ['✅ Tous les capteurs ont les attributs nécessaires'])
    );
  }

  const list = createElement('div', { class: 'sensors-list' }, 
    missing.map(sensor => renderSensorItem(sensor, false))
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, ['🏷️ Attributs Manquants']),
    createElement('p', { class: 'section-description warning' }, [
      `⚠️ ${missing.length} capteur(s) avec attributs incomplets. Cela peut empêcher HSE de les détecter.`
    ]),
    list,
  ]);

  return Card.create('', content);
}

/**
 * Capteurs indisponibles
 */
function renderUnavailableSensors(sensors) {
  if (!sensors || sensors.length === 0) {
    return Card.create('❌ Capteurs Indisponibles', 
      createElement('p', { class: 'no-issues' }, ['✅ Tous les capteurs sont disponibles'])
    );
  }

  const list = createElement('div', { class: 'sensors-list' }, 
    sensors.map(sensor => renderSensorItem(sensor, false))
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, ['❌ Capteurs Indisponibles']),
    createElement('p', { class: 'section-description' }, [
      `${sensors.length} capteur(s) en état "unavailable". Vérifiez la connexion des appareils.`
    ]),
    list,
  ]);

  return Card.create('', content);
}

/**
 * Rendu d'un item capteur
 */
function renderSensorItem(sensor, showEnableButton) {
  const badge = Badge.create(sensor.integration, 'info');

  const actions = [];
  if (showEnableButton) {
    // ✅ CHANGEMENT : Utiliser enableSensorAction
    actions.push(
      Button.create('Activer', () => enableSensorAction(sensor.entity_id), 'primary')
    );
  }
  actions.push(
    Button.create('Voir détails', () => openHAEntity(sensor.entity_id), 'secondary')
  );

  const item = createElement('div', { class: 'sensor-item' }, [
    createElement('div', { class: 'sensor-info' }, [
      createElement('strong', {}, [sensor.friendly_name]),
      createElement('code', {}, [sensor.entity_id]),
      createElement('p', { class: 'sensor-reason' }, [sensor.reason]),
      createElement('div', { class: 'sensor-meta' }, [
        badge,
        createElement('span', {}, [`device_class: ${sensor.device_class || 'missing'}`]),
        createElement('span', {}, [`unit: ${sensor.unit || 'missing'}`]),
      ])
    ]),
    createElement('div', { class: 'sensor-actions' }, actions)
  ]);

  return item;
}


/**
 * Ouvrir l'entité dans HA
 */
function openHAEntity(entity_id) {
  window.open(`/config/entities/entity/${entity_id}`, '_blank');
}

/**
 * Ouvrir le registry HA (filtré sur intégration si possible)
 */
function openHAEntityRegistry(filter) {
  const url = filter.startsWith('sensor.') 
    ? `/config/entities/entity/${filter}`
    : `/config/entities`;
  window.open(url, '_blank');
}
