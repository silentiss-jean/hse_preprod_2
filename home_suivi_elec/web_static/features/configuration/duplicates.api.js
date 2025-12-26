// duplicates.api.js — API pour actions doublons
"use strict";

/**
 * Ignore ou réintègre une entité côté backend.
 * @param {string} entity_id
 * @param {boolean} ignore
 * @returns {Promise<any>}
 */
export async function apiSetIgnored(entity_id, ignore) {
  const resp = await fetch("/api/home_suivi_elec/set_ignored_entity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_id, ignore: !!ignore })
  });
  if (!resp.ok) throw new Error("set_ignored_entity failed");
  return await resp.json();
}

/**
 * Demande au backend de choisir la “meilleure” mesure pour un device_id donné.
 * Le backend retourne l’entité retenue et celles à ignorer.
 * @param {string} device_id
 * @returns {Promise<{best:string, ignored:string[]}>}
 */
export async function apiChooseBestForDevice(device_id) {
  const resp = await fetch("/api/home_suivi_elec/choose_best_for_device", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id })
  });
  if (!resp.ok) throw new Error("choose_best_for_device failed");
  return await resp.json();
}
