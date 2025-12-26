"use strict";

/**
 * API partagée pour récupérer les capteurs
 * ✅ Avec authentification obligatoire
 */

import { fetchAuthJSON } from '../../core/auth.js';  // ← fetchAuthJSON au lieu de fetchAuth

/**
 * Récupère la liste des capteurs
 * @returns {Promise<Object>} Données des capteurs
 */
export async function getSensorsData() {
  try {
    return await fetchAuthJSON('/api/home_suivi_elec/get_sensors');
  } catch (error) {
    console.error('[sensorsApi] Erreur getSensorsData:', error);
    throw error;
  }
}

/**
 * Récupère les options utilisateur
 * @returns {Promise<Object>} Options utilisateur
 */
export async function getUserOptions() {
  try {
    return await fetchAuthJSON('/api/home_suivi_elec/get_user_options');
  } catch (error) {
    console.error('[sensorsApi] Erreur getUserOptions:', error);
    throw error;
  }
}
