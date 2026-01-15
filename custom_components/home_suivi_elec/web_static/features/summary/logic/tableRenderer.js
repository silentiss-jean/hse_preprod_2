"use strict";

/**
 * tableRenderer.js
 * Génère les 3 tableaux HTML de résumé de consommation :
 * - Capteurs sélectionnés (interne)
 * - Capteur externe de référence
 * - Delta (externe - interne)
 */

import { PERIODS, calculatePeriodCost } from "./priceCalculator.js";
import { showCacheBadge } from "./summary.loader.js";

/**
 * Génère le HTML complet d'un tableau de résumé
 * @param {string} tableId - ID du tableau (summarySelectedSensors, summaryExternalSensors, summaryDeltaSensors)
 * @param {string} title - Titre du tableau
 * @param {Function} kwhMap - Fonction retournant les kWh pour une clé de période (ex: 'day', 'week', etc.)
 * @param {Object} userData - Options utilisateur (abonnement, tarifs, type contrat)
 * @param {Function|null} metaMap - (optionnel) Fonction retournant les meta pour une clé (from_cache, cached_age)
 * @returns {string} HTML du tableau complet
 */
function buildTableHTML(tableId, title, kwhMap, userData, metaMap = null) {
  let rowsHTML = "";

  PERIODS.forEach((period, idx) => {
    const kwh = kwhMap(period.key) || 0;
    const { coutHT, coutTTC, totalHT, totalTTC } = calculatePeriodCost(
      kwh,
      userData,
      idx
    );

    const meta = metaMap ? metaMap(period.key) || {} : {};
    const fromCache = !!meta.from_cache;
    const cachedAge = meta.cached_age || 0;

    rowsHTML += `
      <tr>
        <td>${period.label}</td>
        <td>
          ${kwh.toFixed(2)}
          ${showCacheBadge(fromCache, cachedAge)}
        </td>
        <td>${coutHT.toFixed(2)}</td>
        <td>${coutTTC.toFixed(2)}</td>
        <td>${totalHT.toFixed(2)}</td>
        <td>${totalTTC.toFixed(2)}</td>
      </tr>
    `;
  });

  return `
    <h3 class="hse-summary-table-title">${title}</h3>
    <div class="integrations-table-container">
      <table id="${tableId}" class="integrations-table">
        <thead>
          <tr>
            <th>Période</th>
            <th>kWh</th>
            <th>Coût consommation HT (€)</th>
            <th>Coût consommation TTC (€)</th>
            <th>Total HT (€)</th>
            <th>Total TTC (€)</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHTML}
        </tbody>
      </table>
    </div>
  `;
}

/**
 * Génère le HTML des 3 tableaux de résumé
 * @param {Object} internalKwh - Map des kWh internes { day: X, week: Y, ... }
 * @param {Object} externalKwh - Map des kWh externes
 * @param {Object} deltaKwh - Map des deltas
 * @param {Object} userData - Options utilisateur
 * @param {Object|null} internalMeta - (optionnel) meta internes { day: {from_cache, cached_age}, ... }
 * @param {Object|null} externalMeta - (optionnel) meta externes
 * @param {Object|null} deltaMeta - (optionnel) meta delta
 * @returns {string} HTML complet des 3 tableaux
 */
export function renderSummaryTables(
  internalKwh,
  externalKwh,
  deltaKwh,
  userData,
  internalMeta = null,
  externalMeta = null,
  deltaMeta = null
) {
  const getInternal = (key) => internalKwh[key] || 0;
  const getExternal = (key) => externalKwh[key] || 0;
  const getDelta = (key) => deltaKwh[key] || 0;

  const getInternalMeta = (key) =>
    internalMeta && internalMeta[key] ? internalMeta[key] : {};
  const getExternalMeta = (key) =>
    externalMeta && externalMeta[key] ? externalMeta[key] : {};
  const getDeltaMeta = (key) =>
    deltaMeta && deltaMeta[key] ? deltaMeta[key] : {};

  const table1 = buildTableHTML(
    "summarySelectedSensors",
    "Capteurs détectés – Puissance cumulée",
    getInternal,
    userData,
    internalMeta ? getInternalMeta : null
  );

  const table2 = buildTableHTML(
    "summaryExternalSensors",
    "Capteur externe de référence",
    getExternal,
    userData,
    externalMeta ? getExternalMeta : null
  );

  const table3 = buildTableHTML(
    "summaryDeltaSensors",
    "Delta (externe - interne)",
    getDelta,
    userData,
    deltaMeta ? getDeltaMeta : null
  );

  return `
    <div id="tablesDetail" class="hse-summary-tables-detail">
      ${table1}
      ${table2}
      ${table3}
      <p id="summaryMessage" class="hse-summary-message">
        Les totaux incluent l'abonnement mensuel proratisé sur chaque période.
      </p>
    </div>
  `;
}

/**
 * LEGACY : Fonction de compatibilité pour ne pas casser l'existant
 * Génère les lignes d'UN seul tableau (ancienne signature)
 * @param {HTMLElement} tbody
 * @param {Function} kwhMap
 * @param {Object} userData
 * @param {Function|null} metaMap - (optionnel) retourne {from_cache, cached_age} pour une clé
 */
export function renderTable(tbody, kwhMap, userData, metaMap = null) {
  if (!tbody) {
    console.warn("[tableRenderer] tbody non fourni");
    return;
  }

  tbody.innerHTML = "";

  PERIODS.forEach((period, idx) => {
    const kwh = kwhMap(period.key) || 0;
    const { coutHT, coutTTC, totalHT, totalTTC } = calculatePeriodCost(
      kwh,
      userData,
      idx
    );

    const meta = metaMap ? metaMap(period.key) || {} : {};
    const fromCache = !!meta.from_cache;
    const cachedAge = meta.cached_age || 0;

    const row = `
      <tr>
        <td>${period.label}</td>
        <td>
          ${kwh.toFixed(2)}
          ${showCacheBadge(fromCache, cachedAge)}
        </td>
        <td>${coutHT.toFixed(2)}</td>
        <td>${coutTTC.toFixed(2)}</td>
        <td>${totalHT.toFixed(2)}</td>
        <td>${totalTTC.toFixed(2)}</td>
      </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", row);
  });
}
