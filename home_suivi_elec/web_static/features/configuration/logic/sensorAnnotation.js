// features/configuration/logic/sensorAnnotation.js
// Annotation et filtrage des capteurs

"use strict";

import { indexByDuplicateGroup } from './sensorCategories.js';

/**
 * Annote les capteurs avec les infos de duplicate_group
 * Remplace l'ancien annotateSameDevice qui utilisait device_id
 * 
 * @param {Object} selectedMap - {integration: [capteurs]}
 * @param {Object} alternativesMap - {integration: [capteurs]}
 */
export function annotateSameDevice(selectedMap, alternativesMap) {
    // Construire allCapteurs depuis les deux maps
    const allCapteurs = {};
    for (const map of [selectedMap, alternativesMap]) {
        Object.values(map || {}).flat().forEach(c => {
            if (c && c.entity_id) allCapteurs[c.entity_id] = c;
        });
    }
    
    // Utiliser indexByDuplicateGroup au lieu de indexByDeviceId
    // Cela groupe par (nom + zone + TYPE) au lieu de device_id seul
    const groups = indexByDuplicateGroup(allCapteurs);
    
    const flagList = (lst) => (lst || []).forEach(c => {
        if (!c) return;
        const sig = c.duplicate_group || "";
        if (!sig) return;
        
        const g = groups.get(sig);
        if (g && g.members.length >= 2) {
            c.ui_same_device_count = g.members.length;
            c.ui_device_label = `${g.name || "Appareil"}${g.area ? " — " + g.area : ""}`;
        } else {
            c.ui_same_device_count = 0;
            c.ui_device_label = `${c.device_name || "Appareil"}${c.area_name ? " — " + c.area_name : ""}`;
        }
    });
    
    for (const [, lst] of Object.entries(selectedMap || {})) flagList(lst);
    for (const [, lst] of Object.entries(alternativesMap || {})) flagList(lst);
}

/**
 * Filtre les capteurs ignorés
 * 
 * @param {Object} selectedMap 
 * @param {Object} alternativesMap 
 * @param {Set} ignoredSet - Set des entity_id ignorés
 * @returns {Object} { outSel, outAlt }
 */
export function applyIgnoredFilter(selectedMap, alternativesMap, ignoredSet) {
    const filt = (lst) => (lst || []).filter(c => !ignoredSet.has(c.entity_id));
    
    const outSel = {};
    const outAlt = {};
    
    for (const [k, v] of Object.entries(selectedMap || {})) {
        outSel[k] = filt(v);
    }
    for (const [k, v] of Object.entries(alternativesMap || {})) {
        outAlt[k] = filt(v);
    }
    
    return { outSel, outAlt };
}

/**
 * Clone profond d'un objet
 * @param {*} obj 
 * @returns {*}
 */
export function deepClone(obj) {
    try {
        return JSON.parse(JSON.stringify(obj));
    } catch {
        return obj;
    }
}