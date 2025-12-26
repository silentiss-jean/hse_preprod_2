// features/configuration/logic/sensorCategories.js
// Catégorisation et groupement des capteurs

"use strict";
console.log("[sensorCategories] module chargé");
/**
 * Sépare les capteurs physiques des helpers (calculés/agrégés)
 * 
 * @param {Object} sensors - {entity_id: capteur}
 * @returns {Object} { physical, helpers }
 */
export function categorizeSensors(sensors) {
const physical = {};
const helpers = {};

const helperIntegrations = [
'min_max', 'statistics', 'average', 'template',
'utility_meter', 'integration', 'history_stats',
'derivative', 'filter'
];

Object.entries(sensors || {}).forEach(([entityId, sensor]) => {
  if (!sensor) return;

  const integration = (sensor.integration || "").toLowerCase();
  const isHelper =
    helperIntegrations.includes(integration) ||
    sensor.is_helper === true ||
    entityId.includes("_helper_") ||
    entityId.includes("_average_") ||
    entityId.includes("_total_") ||
    entityId.includes("_sum_");

  // Nouveau : rôle logique simple basé sur source_type
  const src = (sensor.source_type || "").toLowerCase();
  let ui_role = null;
  if (src === "power") ui_role = "power";
  else if (src === "energy") ui_role = "energy";

  const base = { ...sensor, is_helper: isHelper, ui_role };

  // Petit log de contrôle sur quelques capteurs
  if (entityId.includes("tapo_") || entityId.includes("atome")) {
    console.log("[cat] sample", entityId, "src =", src, "ui_role =", ui_role);
  }

  if (isHelper) {
    helpers[entityId] = base;
  } else {
    physical[entityId] = base;
  }
});

console.log(
  "[sensorCategories] categorizeSensors appelée sur",
  Object.keys(sensors || {}).length,
  "capteurs"
);
console.log(`[sensorCategories] 📊 ${Object.keys(physical).length} physiques, ${Object.keys(helpers).length} helpers`);
return { physical, helpers };
}


/**
 * Groupe les capteurs par duplicate_group (nom+zone+type)
 * Utilisé pour détecter les doublons multi-intégrations
 * 
 * @param {Object} allCapteurs - {entity_id: capteur}
 * @returns {Map} groups avec >= 2 membres
 */
export function indexByDuplicateGroup(allCapteurs) {
    const groups = new Map();
    
    Object.values(allCapteurs || {}).forEach(c => {
        if (!c || !c.duplicate_group) return;
        
        const sig = c.duplicate_group;
        if (!groups.has(sig)) {
            groups.set(sig, {
                name: c.friendly_name || c.nom || c.device_name || "",
                area: c.zone || c.area || c.area_name || "",
                members: []
            });
        }
        
        const g = groups.get(sig);
        g.members.push({
            entity_id: c.entity_id,
            integration: c.integration || "unknown",
            friendly_name: c.friendly_name || c.nom || c.entity_id
        });
    });
    
    // Filtrer : garder uniquement les groupes avec >= 2 membres
    const filtered = new Map();
    groups.forEach((g, sig) => {
        if (g.members.length >= 2) {
            filtered.set(sig, g);
        }
    });
    
    return filtered;
}

/**
 * LEGACY: Groupe par device_id (ancien système)
 * Conservé pour compatibilité, mais indexByDuplicateGroup est préféré
 * 
 * @param {Array} maps - Liste de maps {integration: [capteurs]}
 * @returns {Map}
 */
export function indexByDeviceId(maps) {
    const groups = new Map();
    
    const touch = (c, integration) => {
        const did = c?.device_id || "";
        if (!did) return;
        
        if (!groups.has(did)) {
            groups.set(did, {
                name: c.device_name || "",
                area: c.area_name || "",
                members: []
            });
        }
        
        const g = groups.get(did);
        g.name = g.name || c.device_name || "";
        g.area = g.area || c.area_name || "";
        g.members.push({
            entity_id: c.entity_id,
            integration,
            friendly_name: c.friendly_name || c.entity_id
        });
    };
    
    for (const map of maps) {
        for (const [integ, lst] of Object.entries(map || {})) {
            (lst || []).forEach(c => c && touch(c, integ));
        }
    }
    
    return groups;
}