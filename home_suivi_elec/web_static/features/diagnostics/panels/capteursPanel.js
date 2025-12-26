'use strict';

// panels/capteursPanel.js
/**
 * Panel d'affichage des capteurs groupés - Version finale v2
 * CHANGEMENTS CRITIQUES :
 * - SUPPRESSION TOTALE du bouton "Garder le meilleur" et sa fonction
 * - Groupes REPLIÉS par défaut → scroll efficace
 * - Wrapper .hse-diagnostics-sensors-list pour le scroll
 * - Mini-résumé (sélectionnés/total) dans header
 */

import { getSensorsData } from '../diagnostics.api.js';
import { setCachedData, getCachedData } from '../diagnostics.state.js';
import { groupSensorsByDuplicateGroup, filterGroups } from '../logic/sensorGrouping.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';
import { getUserOptions } from '../../configuration/configuration.api.js';

console.info('[capteursPanel] Module chargé - Version v2');

let currentFilters = {
  search: '',
  state: 'all'
};

// ---- Helpers filtre énergie/puissance ----
const ENERGY_UNITS = new Set(['W', 'kW', 'Wh', 'kWh']);
const ENERGY_CLASSES = new Set(['power', 'energy']);

function isEnergySensor(s) {
  if (!s || typeof s !== 'object') return false;
  if (!s.entity_id || !String(s.entity_id).startsWith('sensor.')) return false;
  const unit = s.unit || s.unit_of_measurement;
  return ENERGY_CLASSES.has(s.device_class) || (unit && ENERGY_UNITS.has(unit));
}

// ---- Tri capteurs (Référence → Sélectionné → Disponible → score ↓ → entity_id) ----
function sortSensors(a, b) {
  const rank = (s) => (s.is_reference ? 0 : s.selected ? 1 : 2);
  const r = rank(a) - rank(b);
  if (r !== 0) return r;
  const sa = Number.isFinite(a.reliability_score) ? a.reliability_score : -1;
  const sb = Number.isFinite(b.reliability_score) ? b.reliability_score : -1;
  if (sb !== sa) return sb - sa;
  return String(a.entity_id).localeCompare(String(b.entity_id));
}

/**
 * Point d'entrée principal
 */
export async function loadCapteursPanel(container) {
  try {
    console.log('[capteursPanel] Chargement v2...');

    // Loader
    container.innerHTML = '';
    container.appendChild(
      createElement('div', { class: 'loading-state' }, [
        createElement('div', { class: 'spinner' }),
        createElement('p', {}, ['Chargement des capteurs...'])
      ])
    );

    // Récupérer données API
    const apiData = await getSensorsData();
    if (!apiData) throw new Error('Aucune donnée reçue');
    const userOptions = await getUserOptions();

    // Traiter (filtrer+dédupliquer) et mettre en cache
    const sensorsMap = processSensorsData(apiData, userOptions);
    setCachedData('sensors', sensorsMap);

    // Stats consolidées depuis la map filtrée
    const all = Object.values(sensorsMap);
    const stats = {
      total: all.length,
      reference: all.filter(s => s.is_reference).length,
      selected: all.filter(s => s.selected && !s.is_reference).length,
      available: all.filter(s => !s.selected && !s.is_reference).length
    };

    if (stats.total === 0) {
      container.innerHTML = '';
      container.appendChild(
        Card.create(
          'Aucun capteur',
          createElement('p', {}, ['Vérifiez votre configuration'])
        )
      );
      return;
    }

    // Grouper (logique dans sensorGrouping.js)
    const { groups } = groupSensorsByDuplicateGroup(sensorsMap);

    // Tri optionnel des groupes (nom → taille desc)
    const groupsSorted = [...groups].sort((a, b) => {
      const n = String(a.name).localeCompare(String(b.name));
      if (n !== 0) return n;
      return (b.sensors?.length || 0) - (a.sensors?.length || 0);
    });

    // Render
    renderCapteursInterface(container, groupsSorted, stats);
    showToast(`${stats.total} capteurs en ${groupsSorted.length} groupes`, 'success');

  } catch (error) {
    console.error('[capteursPanel] Erreur:', error);
    container.innerHTML = '';
    container.appendChild(
      Card.create(
        'Erreur',
        createElement('div', {}, [
          createElement('p', {}, [error.message]),
          createElement('p', {}, ['Endpoint: /api/home_suivi_elec/get_sensors'])
        ])
      )
    );
    showToast(`Erreur: ${error.message}`, 'error');
  }
}

/**
 * Traite les données brutes de l'API → map filtrée/dédupliquée
 */
function processSensorsData(apiData, userOptions = {}) {
  const sensorsMap = {};
  const useExternal = !!userOptions.use_external;
  const mode = userOptions.mode || 'sensor';
  let rejectedNotObject = 0, rejectedNoSensorPrefix = 0, rejectedNotEnergy = 0;

  const upsert = (sensor, { selected = false, is_reference = false } = {}) => {
    if (!sensor || typeof sensor !== 'object') { rejectedNotObject++; return; }
    if (!sensor.entity_id || !String(sensor.entity_id).startsWith('sensor.')) { rejectedNoSensorPrefix++; return; }
    const unit = sensor.unit || sensor.unit_of_measurement;
    const ok = ENERGY_CLASSES.has(sensor.device_class) || (unit && ENERGY_UNITS.has(unit));
    if (!ok) { rejectedNotEnergy++; return; }

    const id = sensor.entity_id;
    const prev = sensorsMap[id] || {};
    sensorsMap[id] = {
      ...prev,
      ...sensor,
      selected: is_reference ? true : (prev.selected || selected),
      is_reference: prev.is_reference || is_reference
    };
  };

  // selected: { integration: [sensors] }
  Object.values(apiData.selected || {}).forEach(arr => (arr || []).forEach(
    s => upsert(s, { selected: true })
  ));

  // alternatives: { integration: [sensors] }
  Object.values(apiData.alternatives || {}).forEach(arr => (arr || []).forEach(
    s => upsert(s)
  ));

  // reference_sensor: supporter plusieurs formats courants
  if (useExternal && mode === 'sensor') {
    const ref = apiData.reference_sensor;
    if (Array.isArray(ref)) {
      ref.forEach(s => upsert(s, { is_reference: true }));
    } else if (ref && typeof ref === 'object') {
      if (ref.entity_id) upsert(ref, { is_reference: true });
      Object.entries(ref).forEach(([k, v]) => {
        if (k && String(k).startsWith('sensor.') && v && typeof v === 'object') {
          upsert({ ...v, entity_id: k }, { is_reference: true });
        }
      });
    }
  }

  console.debug('[capteursPanel] Rejets filtre:', {
    nonObjet: rejectedNotObject,
    nonSensorPrefix: rejectedNoSensorPrefix,
    nonEnergyClassOrUnit: rejectedNotEnergy
  });

  return sensorsMap;
}

/**
 * Rendu de l'interface - AVEC WRAPPER SCROLLABLE
 */
function renderCapteursInterface(container, groups, stats) {
  container.innerHTML = '';

  // Stats
  const statsDiv = createElement('div', { class: 'capteurs-stats' }, [
    Badge.create(`TOTAL: ${stats.total}`, 'info'),
    Badge.create(`RÉFÉRENCE: ${stats.reference}`, 'warning'),
    Badge.create(`SÉLECTIONNÉS: ${stats.selected}`, 'success'),
    Badge.create(`DISPONIBLES: ${stats.available}`, 'info')
  ]);

  // Recherche
  const searchInput = createElement('input', {
    type: 'text',
    placeholder: 'Rechercher...',
    id: 'sensor-search'
  });
  searchInput.addEventListener('input', (e) => {
    currentFilters.search = e.target.value.toLowerCase();
    applyFilters();
  });

  const filtersDiv = createElement('div', { class: 'filters' }, [searchInput]);

  // Groupes dans un conteneur
  const groupsDiv = createElement('div', {
    class: 'sensors-groups',
    id: 'sensors-groups-container'
  }, groups.map(g => renderGroup(g)));

  // ⭐ WRAPPER SCROLLABLE - classe .hse-diagnostics-sensors-list
  const scrollableWrapper = createElement('div', {
    class: 'hse-diagnostics-sensors-list'
  }, [groupsDiv]);

  // Assemblage
  const content = createElement('div', {}, [statsDiv, filtersDiv, scrollableWrapper]);
  const mainCard = Card.create('Capteurs groupés', content);
  container.appendChild(mainCard);

  // Bouton refresh
  const refreshBtn = Button.create(
    'Actualiser',
    () => loadCapteursPanel(container),
    'secondary'
  );
  container.appendChild(refreshBtn);
}

/**
 * Rendu d'un groupe - SANS bouton "Garder le meilleur", REPLIÉ par défaut
 */
function renderGroup(group) {
  const groupDiv = createElement('div', {
    class: 'sensor-group',
    'data-group': group.key
  });

  // Calcul mini-résumé : nombre de capteurs sélectionnés / total
  const selectedCount = (group.sensors || []).filter(s => s.selected || s.is_reference).length;
  const totalCount = (group.sensors || []).length;

  const summarySpan = createElement('span', { class: 'group-summary' }, [
    createElement('span', { class: 'selected-highlight' }, [String(selectedCount)]),
    '/',
    String(totalCount)
  ]);

  // ✅ Header SANS le bouton "Garder le meilleur"
  const header = createElement('div', { class: 'group-header' }, [
    createElement('span', { class: 'expand-icon' }, ['▶']),
    createElement('span', { class: 'group-icon' }, ['📦']),
    createElement('span', { class: 'group-name' }, [group.name]),
    summarySpan,
    createElement('span', { class: 'group-count' }, [String(group.sensors.length)])
  ]);

  header.addEventListener('click', (ev) => {
    toggleGroup(group.key);
  });

  // ✅ REPLIÉ PAR DÉFAUT (display: none)
  const content = createElement('div', {
    class: 'group-content',
    style: 'display: none;'
  }, [...group.sensors].sort(sortSensors).map(s => renderSensor(s)));

  groupDiv.appendChild(header);
  groupDiv.appendChild(content);

  return groupDiv;
}

/**
 * Rendu d'un capteur
 */
function renderSensor(sensor) {
  // Badge état principal
  let stateVariant, stateLabel;
  if (sensor.is_reference) { stateVariant = 'warning'; stateLabel = 'Référence'; }
  else if (sensor.selected) { stateVariant = 'success'; stateLabel = 'Sélectionné'; }
  else { stateVariant = 'info'; stateLabel = 'Disponible'; }

  const badges = [Badge.create(stateLabel, stateVariant)];

  // Badge doublon
  if (sensor.is_duplicate) {
    badges.push(Badge.create('Dup', 'warning'));
  }

  const value = (sensor.value !== null && sensor.value !== undefined)
    ? `${sensor.value} ${sensor.unit || sensor.unit_of_measurement || ''}`.trim()
    : 'N/A';

  const meta = [
    sensor.friendly_name || 'Sans nom',
    sensor.integration ? `Intégration: ${sensor.integration}` : null,
    sensor.duplicate_group && sensor.is_duplicate ? `Groupe dup: ${sensor.duplicate_group}` : null,
    Number.isFinite(sensor.reliability_score) ? `Score: ${sensor.reliability_score}` : null
  ].filter(Boolean).join(' • ');

  return createElement('div', { class: 'sensor-row' }, [
    createElement('div', { class: 'sensor-info' }, [
      createElement('strong', {}, [sensor.entity_id]),
      createElement('br'),
      createElement('small', {}, [`${meta} • Valeur: ${value}`])
    ]),
    createElement('div', { class: 'sensor-badges' }, badges)
  ]);
}

/**
 * Toggle groupe
 */
function toggleGroup(groupKey) {
  const group = document.querySelector(`[data-group="${groupKey}"]`);
  if (!group) return;

  const content = group.querySelector('.group-content');
  const icon = group.querySelector('.expand-icon');

  if (content.style.display === 'none') {
    content.style.display = 'block';
    icon.textContent = '▼';
  } else {
    content.style.display = 'none';
    icon.textContent = '▶';
  }
}

/**
 * Applique les filtres
 */
function applyFilters() {
  const sensorsMap = getCachedData('sensors');
  if (!sensorsMap) return;

  const { groups } = groupSensorsByDuplicateGroup(sensorsMap);
  const filtered = filterGroups(groups, currentFilters);

  const groupsContainer = document.getElementById('sensors-groups-container');
  if (groupsContainer) {
    groupsContainer.innerHTML = '';
    filtered.forEach(g => groupsContainer.appendChild(renderGroup(g)));
  }
}