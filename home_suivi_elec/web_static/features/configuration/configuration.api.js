// configuration.api.js
"use strict";

import { fetchAuthJSON } from "../../core/auth.js";  // ✅ Utiliser version partagée
import { getUserOptions as getSharedUserOptions } from "../../shared/api/sensorsApi.js";
import { fetchConfig } from "../../shared/proxy.js";

// ❌ SUPPRIMER tout le bloc fetchJSON() local (lignes 4-14)

export async function getSensors() {
  return await fetchAuthJSON("/api/home_suivi_elec/get_sensors");
}

export async function getUserOptions() {
  return getSharedUserOptions();
}

export async function saveSelection(selections) {
  return await fetchAuthJSON("/api/home_suivi_elec/save_selection", {
    method: "POST",
    body: JSON.stringify(selections)
  });
}

export async function saveUserOptions(data) {
  return await fetchAuthJSON("/api/home_suivi_elec/save_user_options", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function setIgnoredEntity(entity_id, ignore) {
  return await fetchAuthJSON("/api/home_suivi_elec/set_ignored_entity", {
    method: "POST",
    body: JSON.stringify({ entity_id, ignore: !!ignore })
  });
}

export async function chooseBestForDevice(device_id) {
  return await fetchAuthJSON("/api/home_suivi_elec/choose_best_for_device", {
    method: "POST",
    body: JSON.stringify({ device_id })
  });
}

export async function getCostSensorsStatus() {
  return await fetchAuthJSON("/api/home_suivi_elec/config/cost_sensors_status");
}

export async function generateCostSensors() {
  return await fetchAuthJSON("/api/home_suivi_elec/config/generate_cost_sensors", {
    method: "POST",
    body: JSON.stringify({})
  });
}

//export async function apiSetCostHa(entityId, enabled) {
//  const res = await fetchConfig("set_cost_ha", {
//    method: "POST",
//    body: JSON.stringify({
//      entity_id: entityId,
//      enabled: !!enabled,
//    }),
//  });

  // format backend: { error: false, data: { enabled, cost_entity_id } }
//  if (res.error) {
//    throw new Error(res.error || "Erreur set_cost_ha");
//  }
//  return res.data;
//}