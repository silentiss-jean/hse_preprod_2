"use strict";

/**
 * Module Summary - Version avec cache + UX moderne
 */

import { httpClient } from "../../shared/api/httpClient.js";
import { loadAllSummaryData, getCostsOverview } from "./summary.api.js";
import {
  extractSelectedIds,
  calculateInternalPower,
  calculateExternalConsumption,
  selectTopLiveConsumers,
} from "./summary.state.js";
import {
  updateSensorStats,
  updateInstantPower,
  updateContractInfo,
  toggleDataVisibility,
  renderLiveTopConsumers,
  renderCostsGlobalPanel,
  renderCostsPerEntityTable,
} from "./summary.view.js";
import { LoadingManager, showCacheBadge } from "./logic/summary.loader.js";
import { formatKwh, formatEuro } from "../../shared/utils/formatters.js";

// État local
let isLoadingSummary = false;
const loader = new LoadingManager();

/**
 * Appelle le backend pour calculer les métriques
 */
async function calculateMetrics(entityIds, periods, pricingConfig, externalId = null) {
  const result = await httpClient.post(
    "/api/home_suivi_elec/config/calculate_summary",
    {
      entity_ids: entityIds,
      periods,
      pricing_config: pricingConfig,
      external_id: externalId,
    }
  );

  if (!result || result.error) {
    throw new Error(result?.message || "Erreur calcul backend");
  }

  return result.data;
}

/**
 * Génère le HTML d'un tableau de métriques
 */
function renderMetricsTable(tableId, metricsData, tableType = "internal") {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) {
    console.warn(`[summary] Table #${tableId} introuvable`);
    return;
  }

  tbody.innerHTML = "";

  const periods = ["hourly", "daily", "weekly", "monthly", "yearly"];
  const labels = ["Heure", "Jour", "Semaine", "Mois", "Année"];

  periods.forEach((key, idx) => {
    const data = metricsData[key];
    if (!data) return;

    const row = document.createElement("tr");
    row.className = `summary-row summary-row-${tableType}`;

    // Badge cache si applicable
    const cacheBadge = data.from_cache
      ? showCacheBadge(true, data.cached_age || 0)
      : "";

    row.innerHTML = `
      <td class="summary-period">${labels[idx]} ${cacheBadge}</td>
      <td class="summary-energy">${formatKwh(data.energy_kwh)}</td>
      <td class="summary-cost-ht">${formatEuro(data.cost_ht ?? data.total_ht ?? 0)}</td>
      <td class="summary-cost-ttc">${formatEuro(data.cost_ttc ?? data.total_ttc ?? 0)}</td>
      <td class="summary-total-ht">${formatEuro(data.total_ht)}</td>
      <td class="summary-total-ttc summary-total-highlight">${formatEuro(data.total_ttc)}</td>
    `;
    tbody.appendChild(row);
  });
}

/**
 * Charge et affiche le résumé complet
 */
export async function loadSummary() {
  const homeTab = document.getElementById("home");
  if (!homeTab || !homeTab.classList.contains("active")) {
    console.log("[summary] Onglet home non actif, chargement annulé");
    return;
  }

  if (isLoadingSummary) {
    console.log("[summary] Chargement déjà en cours");
    return;
  }

  isLoadingSummary = true;
  console.log("[summary] 🚀 Début chargement (avec cache + loader)");

  try {
    // 🎨 Afficher le loader
    loader.show();
    loader.updateProgress(10, "Chargement de la configuration...");

    // ✅ Charger toutes les données
    const data = await loadAllSummaryData();
    loader.updateProgress(30, "Données chargées", "Analyse des capteurs...");

    if (!data) {
      loader.showError("Aucune donnée disponible");
      return;
    }

    const selectedIds = extractSelectedIds(data.selection);
    console.log(`[summary] ${selectedIds.length} capteurs sélectionnés`);

    loader.updateProgress(40, "Calcul des statistiques instantanées...");

    // ✅ Stats en haut (temps réel)
    const externalId =
      data.options?.use_external && data.options.mode === "sensor"
        ? data.options.external_capteur
        : null;

    updateSensorStats(data.sensors, selectedIds);

    const internalPower = calculateInternalPower(selectedIds, data.instant, externalId);
    const externalData = calculateExternalConsumption(data.options, data.instant, data.sensors);
    updateInstantPower(internalPower, externalData, data.options);
    updateContractInfo(data.options);

    // 🔍 Top consommateurs live
    const homeContainer = document.getElementById("summaryCard");
    try {
      const topData = selectTopLiveConsumers(data.instant, data.sensors);
      renderLiveTopConsumers(homeContainer, topData);
    } catch (e) {
      console.warn("[summary] Impossible de calculer le top consommateurs:", e);
    }

    loader.updateProgress(50, "Calcul des métriques par période...");

    // ✅ Masquer/afficher sections externes
    const hasExternal = !!externalId;
    const externalTitle = document.getElementById("externalSummaryTitle");
    const externalTable = document.getElementById("summaryExternalSensors");
    const deltaTitle = document.getElementById("deltaSummaryTitle");
    const deltaTable = document.getElementById("summaryDeltaSensors");

    [externalTitle, externalTable, deltaTitle, deltaTable].forEach((el) => {
      if (el) el.style.display = hasExternal ? "" : "none";
    });

    // Config pricing
    const pricingConfig = {
      type_contrat: data.options?.type_contrat || data.options?.type_contrat || "fixe",
      prix_ht: parseFloat(data.options?.prix_ht || data.options?.prixht || 0.2516),
      prix_ttc: parseFloat(data.options?.prix_ttc || data.options?.prixttc || 0.276),
      abonnement_ht: parseFloat(data.options?.abonnement_ht || data.options?.abonnement_ht || 12.44),
      abonnement_ttc: parseFloat(data.options?.abonnement_ttc || data.options?.abonnement_ttc || 13.48),
      hp: data.options?.hp || {},
      hc: data.options?.hc || {},
    };

    const periods = ["hourly", "daily", "weekly", "monthly", "yearly"];

    loader.updateProgress(60, "Appel au moteur de calcul...", "Utilisation du cache si disponible");

    console.log("[summary] 💰 Appel backend calculate_summary...");
    const metricsResult = await calculateMetrics(selectedIds, periods, pricingConfig, externalId);

    loader.updateProgress(80, "Rendu des tableaux...");

    console.log("[summary] ✅ Métriques reçues:", metricsResult);

    // Remplir les tableaux
    renderMetricsTable("summaryInternalSensors", metricsResult.internal, "internal");

    if (hasExternal) {
      renderMetricsTable("summaryExternalSensors", metricsResult.external, "external");
      renderMetricsTable("summaryDeltaSensors", metricsResult.delta, "delta");
    }

    // 📊 Coûts globaux + par capteur (APRÈS les tableaux de métriques)
    loader.updateProgress(85, "Calcul des coûts...");

    try {
      const costsData = await getCostsOverview();

      if (costsData && costsData.data && costsData.data.global && costsData.data.per_entity) {
        renderCostsGlobalPanel(homeContainer, costsData.data.global);
        renderCostsPerEntityTable(homeContainer, costsData.data.per_entity);
        console.log(`[summary] ✅ Coûts affichés: ${costsData.data.total_entities} capteurs`);
      }
    } catch (e) {
      console.warn("[summary] Impossible de charger les coûts:", e);
    }

    loader.updateProgress(95, "Finalisation...");

    toggleDataVisibility(true);

    loader.updateProgress(100, "✅ Chargement terminé !");
    setTimeout(() => loader.hide(), 500);

    console.log("[summary] ✅ Chargement terminé");
  } catch (error) {
    console.error("[summary] ❌ Erreur:", error);
    loader.showError(`Erreur: ${error.message}`);
    toggleDataVisibility(false);
  } finally {
    isLoadingSummary = false;
  }
}

/**
 * Vide le cache manuellement
 */
async function clearCache() {
  try {
    const result = await httpClient.post("/api/home_suivi_elec/cache/clear", {});
    if (result.success) {
      alert(`✅ ${result.message}`);
      console.log("[cache] Vidé:", result.cleared_entries, "entrées");
    } else {
      alert(`❌ Erreur: ${result.error || "échec clear cache"}`);
    }
  } catch (error) {
    console.error("[cache] Erreur clear:", error);
    alert("❌ Erreur lors du vidage du cache");
  }
}

async function toggleCacheStats() {
  const panel = document.getElementById("cacheStatsPanel");
  const content = document.getElementById("cacheStatsContent");

  // Sécurité: certains layouts n'affichent pas ce panneau
  if (!panel || !content) {
    console.warn("[cache] cacheStatsPanel/cacheStatsContent introuvable");
    return;
  }

  if (panel.style.display === "block") {
    panel.style.display = "none";
    return;
  }

  try {
    content.textContent = "Chargement...";
    panel.style.display = "block";

    const result = await httpClient.get("/api/home_suivi_elec/cache_stats");
    console.log("[cache] JSON reçu =", result);

    if (result && result.error === false && result.data && result.data.stats) {
      const stats = result.data.stats;
      content.innerHTML = `
        <div class="hse-cache-stats-grid">
          <div><strong>Total entrées:</strong> ${stats.total_entries}</div>
          <div><strong>Fraîches (&lt;1min):</strong> ${stats.entries_by_age.fresh}</div>
          <div><strong>Valides (1-5min):</strong> ${stats.entries_by_age.valid}</div>
          <div><strong>Anciennes (&gt;5min):</strong> ${stats.entries_by_age.stale}</div>
          <div><strong>Mémoire:</strong> ${stats.memory_kb.toFixed(1)} KB</div>
        </div>
      `;
    } else {
      console.error("[cache] Structure inattendue pour cache_stats:", result);
      content.textContent = "Erreur chargement stats";
    }
  } catch (error) {
    console.error("[cache] Erreur stats:", error);
    content.textContent = "Erreur réseau";
  }
}

/**
 * Initialisation des event listeners
 * ⚠️ UNE SEULE FONCTION, PAS DE DOUBLON
 */
export function initSummaryEvents() {
  // Bouton refresh
  const refreshBtn = document.getElementById("refreshHome");
  if (refreshBtn && !refreshBtn.hasAttribute("data-bound")) {
    refreshBtn.addEventListener("click", async () => {
      console.log("[summary] 🔄 Actualisation manuelle...");
      await loadSummary();
    });
    refreshBtn.setAttribute("data-bound", "true");
  }

  // ✨ Bouton vider cache
  const clearCacheBtn = document.getElementById("clearCache");
  if (clearCacheBtn && !clearCacheBtn.hasAttribute("data-bound")) {
    clearCacheBtn.addEventListener("click", async () => {
      if (confirm("Vider le cache ? Les prochains calculs seront plus lents.")) {
        await clearCache();
        await loadSummary(); // Recharger
      }
    });
    clearCacheBtn.setAttribute("data-bound", "true");
  }

  // ✨ Bouton stats cache
  const statsBtn = document.getElementById("showCacheStats");
  if (statsBtn && !statsBtn.hasAttribute("data-bound")) {
    statsBtn.addEventListener("click", toggleCacheStats);
    statsBtn.setAttribute("data-bound", "true");
  }

  console.log("[summary] ✅ Event listeners initialisés");
}

// Auto-init
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSummaryEvents);
} else {
  initSummaryEvents();
}
