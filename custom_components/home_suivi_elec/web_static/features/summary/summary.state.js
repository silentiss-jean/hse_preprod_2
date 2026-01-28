"use strict";

/**
 * Gestion de l'état et des calculs pour Summary
 */

/**
 * Normalise les valeurs Wh en kWh
 * @param {number} value - Valeur à normaliser
 * @param {string} unit - Unité (Wh ou kWh)
 * @returns {number} Valeur en kWh
 */
export function normalizeToKwh(value, unit = 'kWh') {
    if (typeof value !== 'number' || !isFinite(value)) return 0;
    return unit === 'Wh' ? value / 1000 : value;
}

/**
 * Extrait la liste des IDs de capteurs sélectionnés
 * @param {Object} selectionData - Données de sélection brutes
 * @returns {Array<string>} Liste des entity_id sélectionnés
 */
export function extractSelectedIds(selectionData) {
    const selectedIds = [];
    
    Object.values(selectionData || {}).forEach(lst => {
        (lst || []).forEach(row => {
            if (row?.enabled && row?.entity_id && !selectedIds.includes(row.entity_id)) {
                selectedIds.push(row.entity_id);
            }
        });
    });
    
    return selectedIds;
}

/**
 * Extrait la liste des IDs "power" (W) des capteurs sélectionnés.
 * Priorité: usage_power, sinon entity_id si la source est typée power.
 *
 * @param {Object} selectionData - Données de sélection brutes
 * @returns {Array<string>} Liste des entity_id (power) sélectionnés
 */
export function extractSelectedPowerIds(selectionData) {
    const powerIds = [];

    Object.values(selectionData || {}).forEach((lst) => {
        (lst || []).forEach((row) => {
            if (!row?.enabled) return;

            const sourceType = String(row?.source_type || "").toLowerCase();
            const eid =
                row?.usage_power ||
                ((row?.is_power === true || sourceType === "power") ? row?.entity_id : null);

            if (eid && !powerIds.includes(eid)) {
                powerIds.push(eid);
            }
        });
    });

    return powerIds;
}

/**
 * Calcule la somme des kWh pour une période donnée
 * @param {string} periodKey - Clé de période (hourly, daily, etc.)
 * @param {Array<string>} entityIds - Liste des entity_id
 * @param {Object} consumptionMap - Mapping des consommations
 * @param {string} externalId - ID du capteur externe à exclure (optionnel)
 * @returns {number} Somme en kWh
 */
export function sumKwhForPeriod(periodKey, entityIds, consumptionMap, externalId = null) {
    let sum = 0;
    
    entityIds.forEach(eid => {
        // Exclure le capteur externe de référence
        if (externalId && eid === externalId) return;
        
        const value = consumptionMap?.[eid]?.[periodKey];
        const kwh = typeof value === 'number' && isFinite(value) 
            ? normalizeToKwh(value) 
            : 0;
        
        sum += Math.max(0, kwh);
    });
    
    return sum;
}

/**
 * Récupère les kWh d'un capteur spécifique pour une période
 * @param {string} periodKey - Clé de période
 * @param {string} entityId - ID du capteur
 * @param {Object} consumptionMap - Mapping des consommations
 * @returns {number} kWh du capteur
 */
export function getKwhForEntity(periodKey, entityId, consumptionMap) {
    const value = consumptionMap?.[entityId]?.[periodKey];
    return typeof value === 'number' && isFinite(value) 
        ? normalizeToKwh(value) 
        : 0;
}

/**
 * Calcule la puissance instantanée interne (hors référence externe)
 * @param {Array<string>} selectedIds - IDs des capteurs sélectionnés
 * @param {Object} instantMap - Map des puissances instantanées
 * @param {string} externalId - ID du capteur externe à exclure
 * @returns {number} Puissance totale en W
 */
export function calculateInternalPower(selectedIds, instantMap, externalId = null) {
    let total = 0;
    
    selectedIds.forEach(eid => {
        if (externalId && eid === externalId) return;
        
        const value = instantMap?.[eid];
        if (typeof value === 'number' && isFinite(value)) {
            total += Math.max(0, value);
        }
    });
    
    return total;
}

/**
 * Calcule la consommation externe (capteur ou manuel)
 * @param {Object} userData - Options utilisateur
 * @param {Object} instantMap - Map des puissances instantanées
 * @param {Object} sensorsData - Données des capteurs
 * @returns {Object} { consommation, puissance, indispo, nom, integration }
 */
export function calculateExternalConsumption(userData, instantMap, sensorsData) {
    const use_external = !!userData.use_external;
    const mode = userData.mode || 'sensor';
    
    if (!use_external) {
        return {
            consommation: 0,
            puissance: '- W',
            indispo: false,
            nom: '-',
            integration: '-'
        };
    }
    
    // Mode manuel
    if (mode === 'manual') {
        const manualValue = userData.consommation_externe || 0;
        return {
            consommation: manualValue,
            puissance: manualValue.toFixed(1) + ' W',
            indispo: false,
            nom: 'Valeur manuelle',
            integration: 'Manuel'
        };
    }
    
    // Mode capteur
    const externalId = userData.external_capteur;
    if (!externalId) {
        return {
            consommation: 0,
            puissance: '- W',
            indispo: true,
            nom: 'Non configuré',
            integration: '-'
        };
    }
    
    // Trouver les infos du capteur
    const allSensors = [
        ...Object.values(sensorsData.selected || {}).flat(),
        ...Object.values(sensorsData.alternatives || {}).flat()
    ];
    
    const sensor = allSensors.find(c => c.entity_id === externalId);
    const nom = sensor?.friendly_name ?? externalId;
    const integration = sensor?.integration ?? 'integration';
    
    // Récupérer la puissance instantanée
    const value = instantMap?.[externalId];
    
    if (typeof value === 'number' && isFinite(value)) {
        return {
            consommation: Math.max(0, value),
            puissance: value.toFixed(1) + ' W',
            indispo: false,
            nom,
            integration
        };
    }
    
    return {
        consommation: 0,
        puissance: '- W',
        indispo: true,
        nom,
        integration
    };
}

// summary.state.js (AJOUT)
export async function loadSummaryData() {
  try {
    const data = await getSummaryData();
    
    // ✅ STOCKER LE CAPTEUR DE RÉFÉRENCE
    if (data && data.reference_sensor) {
      state.referenceSensor = data.reference_sensor;
    } else {
      state.referenceSensor = null;
    }

    state.capteurs_summary = data.capteurs_summary || {};
    state.totaux = data.totaux || {};
    state.lastUpdate = Date.now();

    emit('summary:loaded', state);
    return state;
  } catch (error) {
    console.error('[summary.state] Erreur chargement:', error);
    throw error;
  }
}

/**
 * Sélecteur "Top consommateurs" live.
 * Prend les données live de puissance + métadonnées capteurs et renvoie
 * deux listes : 100–500 W et > 500 W, déjà triées et limitées à 10.
 *
 * @param {Object} instantMap - map { entity_id: power_W }
 * @param {Object} sensorsData - { selected: {integ: [capteurs...]}, alternatives: {...} }
 * @returns {{ lowRange: Array, highRange: Array }}
 */
export function selectTopLiveConsumers(instantMap, sensorsData) {
  const lowRange = [];
  const highRange = [];

  if (!instantMap || !sensorsData) {
    return { lowRange, highRange };
  }

  // Construire un index capteur par entity_id pour accéder aux méta
  const byId = {};

  Object.values(sensorsData.selected || {}).forEach((lst) => {
    (lst || []).forEach((c) => {
      if (!c || !c.entity_id) return;
      byId[c.entity_id] = c;
    });
  });

  Object.values(sensorsData.alternatives || {}).forEach((lst) => {
    (lst || []).forEach((c) => {
      if (!c || !c.entity_id) return;
      if (!byId[c.entity_id]) byId[c.entity_id] = c;
    });
  });

  for (const [eid, rawPower] of Object.entries(instantMap)) {
    const capteur = byId[eid];
    if (!capteur) continue;

    // TEMPORAIRE : on considère tout capteur sélectionné comme inclus
    // Filtre Summary: include_in_summary === true
    if (!capteur.include_in_summary) continue;

    const p = Number(rawPower);
    if (!Number.isFinite(p)) continue;

    const item = {
      entity_id: eid,
      name: capteur.friendly_name || capteur.nom || eid,
      power_w: Math.round(p),
      category: capteur.category || capteur.hse_category || null,
      integration: capteur.integration || "unknown",
    };

    if (p >= 100 && p <= 500) {
      lowRange.push(item);
    } else if (p > 500) {
      highRange.push(item);
    }
  }

  const sortDesc = (a, b) => b.power_w - a.power_w;

  lowRange.sort(sortDesc);
  highRange.sort(sortDesc);

  return {
    lowRange: lowRange.slice(0, 10),
    highRange: highRange.slice(0, 10),
  };
}
