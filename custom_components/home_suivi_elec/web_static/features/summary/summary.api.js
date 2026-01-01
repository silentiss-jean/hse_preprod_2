"use strict";

/**
 * Couche API pour Summary
 * Utilise les fonctions partagées quand disponibles
 */

import { fetchAuthJSON } from '../../core/auth.js';
import { getSensorsData } from '../../shared/api/sensorsApi.js';
import { getUserOptions } from '../configuration/configuration.api.js';
// ✅ Ré-exporter pour que les autres modules de summary puissent les utiliser
export { getSensorsData, getUserOptions };

/**
 * Récupère la sélection des capteurs actifs
 */
export async function getSelectionData() {
  try {
    return await fetchAuthJSON('/api/home_suivi_elec/get_selection');
  } catch (error) {
    console.warn('[summary.api] Sélection non disponible:', error);
    return {};
  }
}

/**
 * Récupère la puissance instantanée de tous les capteurs
 */
export async function getInstantPower() {
  try {
    return await fetchAuthJSON('/api/home_suivi_elec/get_instant_puissance');
  } catch (error) {
    console.warn('[summary.api] Puissance instantanée non disponible:', error);
    return {};
  }
}

/**
 * Récupère le mapping des consommations par période
 */
export async function getSensorMapping() {
  try {
    const result = await fetchAuthJSON('/api/home_suivi_elec/sensor_mapping');
    
    if (result && result.data && result.data.mapping) {
      console.log('[summary.api] ✅ Mapping extrait:', Object.keys(result.data.mapping).length, 'capteurs');
      return result.data.mapping;  // Retourne directement le mapping, pas le wrapper
    }
    
    console.warn('[summary.api] ⚠️ Mapping vide ou mal formé:', result);
    return {};
  } catch (error) {
    console.warn('[summary.api] Mapping des consommations non disponible:', error);
    return {};
  }
}


/**
 * Charge toutes les données nécessaires en parallèle
 */
export async function loadAllSummaryData() {
  const [
    sensorsData,
    selectionData,
    userOptions,
    instantPower,
    sensorMapping
  ] = await Promise.all([
    getSensorsData(),      // ← Depuis shared/api/sensorsApi.js
    getSelectionData(),    // ← Fonction locale
    getUserOptions(),      // ← Depuis shared/api/sensorsApi.js
    getInstantPower(),     // ← Fonction locale
    getSensorMapping()     // ← Fonction locale
  ]);
  
  return {
    sensors: sensorsData,
    selection: selectionData,
    options: userOptions,
    instant: instantPower,
    consumption: sensorMapping
  };
}

/**
 * Charge toutes les données metriques
 */
export async function getSummaryMetrics(payload) {
  try {
    return await fetchAuthJSON(
      "/api/home_suivi_elec/summary_metrics",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  } catch (error) {
    console.warn("[summary.api] summary_metrics non disponible:", error);
    return null;
  }
}

/**
 * Récupère les coûts globaux et par capteur
 */
export async function getCostsOverview() {
  try {
    return await fetchAuthJSON('/api/home_suivi_elec/costs_overview');
  } catch (error) {
    console.warn('[summary.api] Costs overview non disponible:', error);
    return null;
  }
}
