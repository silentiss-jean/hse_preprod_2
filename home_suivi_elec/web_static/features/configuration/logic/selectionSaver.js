// features/configuration/logic/selectionSaver.js
// Sauvegarde et validation des sélections (DOM et state)

"use strict";

import { saveSelection, setIgnoredEntity } from '../configuration.api.js';
import { emit } from '../../../shared/eventBus.js';
import { toast } from '../../../shared/uiToast.js';

// Debug global
if (typeof window !== 'undefined') {
  window.__LAST_SELECTION_POSTED__ = window.__LAST_SELECTION_POSTED__ || null;
}

// === Helpers ===

export function buildSelectionsFromState(selectedByIntegration, alternativesByIntegration) {
  const selections = {};

  const push = (capteur, enabled) => {
    if (!capteur?.entity_id) return;
    const integ = capteur.integration || 'unknown';
    selections[integ] ??= [];
    selections[integ].push({
      entity_id: capteur.entity_id,
      enabled: !!enabled,
      // NEW: flag Summary (fallback à false si absent)
      include_in_summary:
        capteur.include_in_summary === undefined
          ? false
          : !!capteur.include_in_summary,
    });
  };

  // selected = enabled:true
  for (const [integ, list] of Object.entries(selectedByIntegration || {})) {
    for (const c of list || []) {
      push(c, true);
    }
  }

  // alternatives = enabled:false (sans écraser ceux déjà en true)
  for (const [integ, list] of Object.entries(alternativesByIntegration || {})) {
    for (const c of list || []) {
      if (!c?.entity_id) continue;
      const arr = selections[integ] || [];
      if (arr.some((x) => x.entity_id === c.entity_id)) continue;
      push(c, false);
    }
  }

  return selections;
}

// Validation frontend par device_id sur la base des selections construites
function validateNoDeviceConflicts(selections, allCapteurs) {
  const byDevice = new Map();

  for (const list of Object.values(selections || {})) {
    for (const row of list || []) {
      if (!row.enabled) continue;
      const eid = row.entity_id;
      const cap = allCapteurs[eid];
      const did = cap?.device_id;
      if (!did) continue;
      if (!byDevice.has(did)) byDevice.set(did, []);
      byDevice.get(did).push(eid);
    }
  }

  const bad = [];
  byDevice.forEach((arr, did) => {
    if (arr.length > 1) bad.push({ device_id: did, entities: arr });
  });
  return bad;
}

/**
 * Sauvegarde basée sur le state canonique (currentOutSel/currentOutAlt)
 */
export async function saveSelectionFromState(
  selectedByIntegration,
  alternativesByIntegration,
  allCapteurs,
  reloadCallback
) {
  const selections = buildSelectionsFromState(
    selectedByIntegration,
    alternativesByIntegration
  );

  const flat = Object.values(selections).flat();
  const enabledCount = flat.filter((s) => s.enabled).length;
  const totalCount = flat.length;

  if (typeof window !== 'undefined') {
    window.__LAST_SELECTION_POSTED__ = JSON.parse(
      JSON.stringify(selections)
    );
  }

  console.log('[SAVE_DEBUG_STATE] Selections (state) =>', {
    enabledCount,
    totalCount,
    selections
  });

  // Validation frontend par device_id (optionnelle, doublon du backend)
  const rawBad = validateNoDeviceConflicts(selections, allCapteurs || {}); // retourne { device_id, entities: [eid...] }
  const bad = rawBad.filter(b => {
    const eids = b.entities || [];
    if (eids.length <= 1) return false;

    const types = eids.map(eid => {
      const cap = (allCapteurs || {})[eid] || {};
      let t = (cap.source_type || cap.type || '').toLowerCase();
      // Normalisation energy
      if (['energydirect', 'energy_direct', 'energy- direct'].includes(t)) {
        t = 'energy';
      }
      // Normalisation power au cas où
      if (['power', 'puissance'].includes(t)) {
        t = 'power';
      }

      return t;
    });

    const typeSet = new Set(types);

    // Cas autorisé: exactement 2 entités, 1 power + 1 energy
    if (eids.length === 2 && typeSet.size === 2 && typeSet.has('power') && typeSet.has('energy')) {
      return false;
    }

    // Tous les autres cas restent bloquants
    console.log("STATE DEBUG DEVICE", b.device_id, {
      eids,
      types,
      typeSet: Array.from(typeSet),
    });
    return true;
  });

  if (bad.length) {
    alert(
      '❌ Conflit: plusieurs mesures pour le même appareil:\n' +
        bad.map((b) => `- ${b.device_id}: ${b.entities.join(', ')}`).join('\n')
    );
    toast.warning('Conflit sur un même appareil (validation frontend)');
    console.warn('[SAVE_DEBUG_STATE] Conflits frontend byDevice détectés:', bad);
    return;
  }

  try {
    console.log('[SAVE_DEBUG_STATE] Appel saveSelection (state)...', selections);
    const json = await saveSelection(selections);
    console.log('[SAVE_DEBUG_STATE] Réponse saveSelection (state):', json);

    if (json && json.success === false) {
      const srvDev = json.device_conflicts || [];
      const srvDup = json.conflicts || [];

      let msg = '❌ Erreur de sauvegarde.\n';
      if (srvDev.length) {
        msg +=
          'Conflits même appareil:\n' +
          srvDev
            .map(
              (d) =>
                `- ${d.device_id}: ${d.entities
                  .map((x) => x.entity_id)
                  .join(', ')}`
            )
            .join('\n') +
          '\n';
      }

      if (srvDup.length) {
        msg +=
          'Doublons:\n' +
          srvDup
            .map(
              (c) =>
                `- ${c.friendly_name} (${c.entity_id}) [${c.integration}] - zone: ${c.area}`
            )
            .join('\n');
      }

      alert(msg);
      toast.warning('Conflits détectés (validation backend)');
      console.error('[SAVE_DEBUG_STATE] Backend a refusé la sélection:', json);
      return;
    }

    emit("selection:saved", { selections, need_restart: json?.need_restart === true });

    if (typeof reloadCallback === 'function') {
      await reloadCallback();
    }
  } catch (err) {
    console.error('[selectionSaver] saveSelectionFromState — exception', err);
    alert('❌ Erreur de sauvegarde');
    toast.error('Erreur de sauvegarde');
  }
}

/**
 * Ancienne API basée sur le DOM (encore utilisée par d'autres panneaux éventuels).
 * On la garde pour compat, mais la config principale passe par saveSelectionFromState.
 */
export async function saveSelectionToBackend(contentEl, allCapteurs, reloadCallback) {
  if (!contentEl) return;

  const selections = {};

  contentEl.querySelectorAll('input.capteur-checkbox').forEach((cb) => {
    const integ = cb.dataset.integration || 'unknown';
    const eid = cb.dataset.entity;
    if (!eid) return;
    selections[integ] ??= [];
    selections[integ].push({ entity_id: eid, enabled: cb.checked });
  });

  const flat = Object.values(selections).flat();
  const enabledCount = flat.filter((s) => s.enabled).length;
  const totalCount = flat.length;

  if (typeof window !== 'undefined') {
    window.__LAST_SELECTION_POSTED__ = JSON.parse(
      JSON.stringify(selections)
    );
  }

  console.log('[SAVE_DEBUG] Selections (DOM) =>', {
    enabledCount,
    totalCount,
    selections
  });

  const bad = validateNoDeviceConflicts(selections, allCapteurs || {});
  if (bad.length) {
    alert(
      '❌ Conflit: plusieurs mesures pour le même appareil:\n' +
        bad
          .map((b) => `- ${b.device_id}: ${b.entities.join(', ')}`)
          .join('\n')
    );
    toast.warning('Conflit sur un même appareil (validation frontend)');
    console.warn('[SAVE_DEBUG] Conflits frontend byDevice détectés:', bad);
    return;
  }

  try {
    console.log('[SAVE_DEBUG] Appel saveSelection (DOM)...', selections);
    const json = await saveSelection(selections);
    console.log('[SAVE_DEBUG] Réponse de saveSelection (DOM):', json);

    if (json && json.success === false) {
      const srvDev = json.device_conflicts || [];
      const srvDup = json.conflicts || [];

      let msg = '❌ Erreur de sauvegarde.\n';
      if (srvDev.length) {
        msg +=
          'Conflits même appareil:\n' +
          srvDev
            .map(
              (d) =>
                `- ${d.device_id}: ${d.entities
                  .map((x) => x.entity_id)
                  .join(', ')}`
            )
            .join('\n') +
          '\n';
      }

      if (srvDup.length) {
        msg +=
          'Doublons:\n' +
          srvDup
            .map(
              (c) =>
                `- ${c.friendly_name} (${c.entity_id}) [${c.integration}] - zone: ${c.area}`
            )
            .join('\n');
      }

      alert(msg);
      toast.warning('Conflits détectés (validation backend)');
      console.error('[SAVE_DEBUG] Backend a refusé (DOM):', json);
      return;
    }

    emit("selection:saved", { selections, need_restart: json?.need_restart === true });

    if (typeof reloadCallback === 'function') {
      await reloadCallback();
    }
  } catch (err) {
    console.error('[selectionSaver] saveSelectionToBackend — exception', err);
    alert('❌ Erreur de sauvegarde');
    toast.error('Erreur de sauvegarde');
  }
}

/**
 * Gestionnaire de checkbox multi-intégration utilisé par certains panels.
 */
export async function handleCheckboxChange(
  entityId,
  checked,
  allCapteurs,
  contentEl,
  saveCallback
) {
  // 1. Validation anti-doublons AVANT toute action
  if (checked) {
    const sensor = allCapteurs[entityId];
    if (sensor && sensor.is_multi_platform) {
      const signature = sensor.physical_signature;
      const sensorType = sensor.type;

      const conflicts = Object.values(allCapteurs).filter(
        (c) =>
          c.physical_signature === signature &&
          c.type === sensorType &&
          c.entity_id !== entityId &&
          c.integration !== sensor.integration
      );

      const activeConflicts = conflicts.filter((c) => {
        const conflictCheckbox = contentEl.querySelector(
          `input.capteur-checkbox[data-entity="${c.entity_id}"]`
        );
        return conflictCheckbox?.checked;
      });

      if (activeConflicts.length > 0) {
        const conflict = activeConflicts[0];
        toast.error(
          `⚠️ Conflit détecté : ${
            conflict.friendly_name || conflict.entity_id
          } (${conflict.integration}) est déjà activé. Ignorez-le d'abord.`
        );

        setTimeout(() => {
          const checkbox = contentEl.querySelector(
            `input.capteur-checkbox[data-entity="${entityId}"]`
          );
          if (checkbox) checkbox.checked = false;
        }, 0);

        return;
      }

      for (const conflict of conflicts) {
        await setIgnoredEntity(conflict.entity_id, true);
      }

      if (conflicts.length > 0) {
        toast.success(
          `✅ ${conflicts.length} capteur(s) en conflit ignoré(s) automatiquement`
        );
      }
    }
  }

  if (typeof saveCallback === 'function') {
    await saveCallback();
  }

  toast.info('Sélection enregistrée');
}
