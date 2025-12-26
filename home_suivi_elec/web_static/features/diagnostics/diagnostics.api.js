"use strict";

import { fetchAuthJSON } from '../../core/auth.js';
import { getSensorsData } from '../../shared/api/sensorsApi.js';  // API partagée capteurs

const API_BASE = '/api/home_suivi_elec';

// Ré-export pour rétrocompatibilité (si d'autres modules importent depuis ici)
export { getSensorsData };

/**
 * Récupère l'état de santé du backend
 * @returns {Promise<Object>} Données de santé
 */
export async function getBackendHealth() {
  try {
    const data = await fetchAuthJSON(`${API_BASE}/get_backend_health`);

    if (!data?.success) {
      throw new Error(data?.error || 'Données santé indisponibles');
    }

    return data.health;
  } catch (error) {
    console.error('[diagnostics.api] Erreur getBackendHealth:', error);
    throw error;
  }
}
