"use strict";

// Adapte cet import si ton httpClient est ailleurs
import { httpClient } from "../../shared/api/httpClient.js";

const BASE_URL = "/api/home_suivi_elec";

/**
 * Récupère les groupes existants depuis le backend.
 * GET /api/home_suivi_elec/get_groups
 */
export async function getGroups() {
    const res = await httpClient.get(`${BASE_URL}/get_groups`);
    // Format attendu: { error: false, data: { groups: {...}, ... } }
    if (res.error) {
        throw new Error(res.message || "Erreur get_groups");
    }
    return res.data?.groups || {};
}

/**
 * Lance le regroupement automatique côté backend.
 * POST /api/home_suivi_elec/config/auto_group
 *
 * @param {Object|null} keywordMapping - mapping optionnel { mot: "Nom de groupe" }
 */
export async function autoGroup(keywordMapping = null) {
    const payload = {};
    if (keywordMapping && typeof keywordMapping === "object") {
        payload.keyword_mapping = keywordMapping;
    }

    const res = await httpClient.post(
        `${BASE_URL}/config/auto_group`,
        payload
    );

    if (res.error) {
        throw new Error(res.message || "Erreur auto_group");
    }

    // Le backend renvoie les groupes fusionnés
    return res.data?.groups || {};
}

/**
 * Sauvegarde la configuration actuelle des groupes.
 * POST /api/home_suivi_elec/config/save_groups
 */
export async function saveGroups(groups) {
    const res = await httpClient.post(
        `${BASE_URL}/config/save_groups`,
        { groups }
    );

    if (res.error) {
        throw new Error(res.message || "Erreur save_groups");
    }

    return res.data;
}

/**
 * GET /api/home_suivi_elec/get_group_sets
 */
export async function getGroupSets() {
  const res = await httpClient.get(`${BASE_URL}/get_group_sets`);
  if (res.error) throw new Error(res.message || "Erreur get_group_sets");
  return res.data?.group_sets || { sets: {}, version: 1 };
}

/**
 * POST /api/home_suivi_elec/config/savegroupsets
 * payload attendu: { group_sets: { sets: {...}, version: 1 } }
 */
export async function saveGroupSets(groupSets) {
  const res = await httpClient.post(`${BASE_URL}/config/savegroupsets`, {
    group_sets: groupSets,
  });
  if (res.error) throw new Error(res.message || "Erreur savegroupsets");
  return res.data;
}

/**
 * POST /api/home_suivi_elec/config/refresh_group_totals
 * payload attendu: { scope: "rooms"|"types" }
 */
export async function refreshGroupTotals(scope) {
  const res = await httpClient.post(`${BASE_URL}/config/refresh_group_totals`, {
    scope,
  });
  if (res.error) throw new Error(res.message || "Erreur refresh_group_totals");
  return res.data;
}
