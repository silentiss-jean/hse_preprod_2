'use strict';

/**
 * Logique de groupement des capteurs (corrigé)
 * - Filtre strict énergie/puissance (sensor.*, device_class power/energy ou unité W/kW/Wh/kWh)
 * - Dédup par entity_id
 * - Marquage des doublons via duplicate_group (is_duplicate, duplicate_tag)
 * - Regroupement par intégration
 * - Stats fiables (total/selected/available/reference) calculées sur la base filtrée
 * - Filtre de groupes par recherche et état
 */

// Helpers filtre/uniq
const ENERGY_UNITS = new Set(['W', 'kW', 'Wh', 'kWh']);
const ENERGY_CLASSES = new Set(['power', 'energy']);

function isEnergySensor(s) {
  if (!s || !s.entity_id || !String(s.entity_id).startsWith('sensor.')) return false;
  const unit = s.unit || s.unit_of_measurement;
  return ENERGY_CLASSES.has(s.device_class) || (unit && ENERGY_UNITS.has(unit));
}

function uniqByEntityId(iterable) {
  const out = [];
  const seen = new Set();
  for (const s of iterable || []) {
    const id = s?.entity_id;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(s);
  }
  return out;
}

/**
 * Groupe les capteurs par intégration et marque les doublons
 * @param {Object} sensorsData - Map {entity_id: sensor}
 * @returns {Object} {groups: Array, stats: Object}
 */
export function groupSensorsByDuplicateGroup(sensorsData = {}) {
  // 1) Filtrer + dédupliquer + ignorer entrées étranges
  const base = uniqByEntityId(
    Object.values(sensorsData).filter(isEnergySensor)
  );

  // 2) Pré-calcul des doublons (duplicate_group partagé par ≥ 2)
  const dupCount = new Map();
  for (const s of base) {
    const g = s.duplicate_group;
    if (!g) continue;
    dupCount.set(g, (dupCount.get(g) || 0) + 1);
  }
  const sensors = base.map(s => {
    const g = s.duplicate_group;
    const isDup = g && dupCount.get(g) > 1;
    return { ...s, is_duplicate: !!isDup, duplicate_tag: isDup ? g : null };
  });

  // 3) Groupement par intégration
  const groupsMap = {};
  for (const s of sensors) {
    const integ = s.integration || 'inconnu';
    const key = `int:${integ}`;
    if (!groupsMap[key]) {
      groupsMap[key] = {
        key,
        name: `Intégration: ${integ}`,
        type: 'integration',
        sensors: []
      };
    }
    groupsMap[key].sensors.push(s);
  }

  // 4) Stats sur base filtrée
  let total = 0, selected = 0, available = 0, reference = 0;
  for (const s of sensors) {
    total++;
    if (s.is_reference) reference++;
    else if (s.selected) selected++;
    else available++;
  }

  return {
    groups: Object.values(groupsMap),
    stats: { total, selected, available, reference }
  };
}

/**
 * Filtre les groupes selon critères
 * @param {Array} groups - Groupes de capteurs
 * @param {Object} filters - {search: string, state: 'all'|'selected'|'available'|'reference'}
 * @returns {Array} Groupes filtrés
 */
export function filterGroups(groups = [], filters = {}) {
  const search = (filters.search || '').toLowerCase();
  const want = filters.state || 'all';

  if (!search && want === 'all') return groups;

  return groups.map(group => {
    const filteredSensors = (group.sensors || []).filter(sensor => {
      // Recherche (entity_id, friendly_name, intégration, duplicate_tag, nom de groupe)
      if (search) {
        const matches =
          sensor.entity_id?.toLowerCase().includes(search) ||
          sensor.friendly_name?.toLowerCase().includes(search) ||
          (sensor.integration?.toLowerCase?.().includes(search)) ||
          (sensor.duplicate_tag?.toLowerCase?.().includes(search)) ||
          (group.name?.toLowerCase?.().includes(search));
        if (!matches) return false;
      }

      // État
      if (want === 'selected' && !sensor.selected) return false;
      if (want === 'reference' && !sensor.is_reference) return false;
      if (want === 'available' && (sensor.selected || sensor.is_reference)) return false;

      return true;
    });

    return filteredSensors.length ? { ...group, sensors: filteredSensors } : null;
  }).filter(Boolean);
}
