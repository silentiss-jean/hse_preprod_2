"use strict";

import { fetchAuthJSON } from '../../core/auth.js';
import { getSensorsData } from '../../shared/api/sensorsApi.js';

const API_BASE = '/api/home_suivi_elec';

// Ré-export pour rétrocompatibilité
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

/**
 * Récupère les groupes diagnostiques (parents/enfants/orphelins)
 * @returns {Promise<Object>} Données de groupement
 */
export async function getDiagnosticGroups() {
  try {
    const data = await fetchAuthJSON(`${API_BASE}/diagnostic_groups`);

    if (!data?.success) {
      throw new Error(data?.error || 'Données de groupes indisponibles');
    }

    return {
      parents: data.parents || [],
      children_by_parent: data.children_by_parent || {},
      orphans: data.orphans || [],
      stats: data.stats || { parents: 0, children: 0, orphans: 0 }
    };
  } catch (error) {
    console.error('[diagnostics.api] Erreur getDiagnosticGroups:', error);
    throw error;
  }
}

/**
 * Récupère les détails enrichis des capteurs
 * @returns {Promise<Object>}
 */
export async function getSensorsEnrichedData() {
  try {
    console.log('[diagnostics.api] Appel getSensorsEnrichedData');
    
    const response = await fetch('/api/home_suivi_elec/sensors');
    
    if (!response.ok) {
      throw new Error(`Erreur HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    const data = result.data;
    
    console.log('[diagnostics.api] Données brutes sensors:', data);
    
    // Transformer en format enrichi
    const enrichedData = { alternatives: {} };
    
    if (data.sensors && Array.isArray(data.sensors)) {
      // Grouper par intégration
      const sensorsByIntegration = {};
      
      data.sensors.forEach(sensor => {
        const integration = sensor.integration || 'unknown';
        if (!sensorsByIntegration[integration]) {
          sensorsByIntegration[integration] = [];
        }
        sensorsByIntegration[integration].push(sensor);
      });
      
      // Enrichir chaque capteur
      Object.entries(sensorsByIntegration).forEach(([integration, sensors]) => {
        enrichedData.alternatives[integration] = sensors.map(sensor => ({
          ...sensor,
          integration: integration,
          state_type: determineStateType(sensor),
          last_update_relative: getRelativeTime(sensor.last_changed || sensor.last_updated),
          is_hse_live: sensor.entity_id.includes('hse_live_'),
          source_entity_id: sensor.entity_id.includes('hse_live_') 
            ? sensor.entity_id.replace('hse_live_', '').replace('sensor.', '')
            : null
        }));
      });
    }
    
    console.log('[diagnostics.api] Données enrichies:', enrichedData);
    return enrichedData;
    
  } catch (error) {
    console.error('[diagnostics.api] Erreur getSensorsEnrichedData:', error);
    throw error;
  }
}

/**
 * Détermine le type d'état d'un capteur
 */
function determineStateType(sensor) {
  if (sensor.attributes?.restored === true) {
    return 'restored';
  }
  
  if (sensor.state === 'unavailable') {
    return 'unavailable';
  }
  
  if (sensor.state === 'unknown') {
    return 'unknown';
  }
  
  if (sensor.attributes?.entity_id && sensor.attributes.entity_id.includes('disabled')) {
    return 'disabled';
  }
  
  // Si le capteur a une valeur numérique ou un état valide
  if (sensor.state && sensor.state !== 'unavailable' && sensor.state !== 'unknown') {
    return 'available';
  }
  
  return 'unknown';
}

/**
 * Calcule le temps relatif depuis une date
 */
function getRelativeTime(dateString) {
  if (!dateString) return 'Jamais';
  
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return `Il y a ${diffSec}s`;
    if (diffMin < 60) return `Il y a ${diffMin} min`;
    if (diffHour < 24) return `Il y a ${diffHour}h`;
    return `Il y a ${diffDay}j`;
    
  } catch (error) {
    return 'Inconnu';
  }
}

/**
 * Récupère les diagnostics profonds (inclut integration.running)
 * @returns {Promise<Object>} Données de diagnostics complets
 */
export async function getDeepDiagnostics() {
  try {
    const raw = await fetchAuthJSON(`${API_BASE}/deep_diagnostics`);

    if (!raw || typeof raw !== 'object') {
      throw new Error('Réponse invalide de deep_diagnostics');
    }

    // 1) gestion enveloppe d'erreur
    if (raw.error === true) {
      throw new Error(raw.message || 'Erreur API deep_diagnostics');
    }

    // 2) déballage éventuel
    const payload = raw.data || raw;

    // 3) validation structure (snake_case)
    if (!payload.health_score || !payload.integration) {
      throw new Error('Structure inattendue: health_score/integration manquant');
    }

    return payload;
  } catch (error) {
    console.error('[diagnostics.api] Erreur getDeepDiagnostics:', error);
    throw error;
  }
}

/**
 * Crée automatiquement les parents manquants pour les cycles orphelins
 * @param {Array} orphans - Liste des entity_id orphelins
 * @returns {Promise<Object>} Résultat de la création
 */
export async function createMissingParents(orphans) {
  try {
    const response = await fetch(`${API_BASE}/create_missing_parents`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ orphans })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.message || 'Échec création parents');
    }

    return result;
  } catch (error) {
    console.error('[diagnostics.api] Erreur createMissingParents:', error);
    throw error;
  }
}
