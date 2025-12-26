"use strict";

/**
 * Couche View pour Summary
 * Gère le rendu et la mise à jour du DOM
 */

import { renderSummaryTables } from "./logic/tableRenderer.js";

/**
 * Utilitaire pour définir le texte d'un élément
 */
function setText(el, text) {
  if (el) el.textContent = text;
}

/**
 * Retourne la première valeur non null/undefined parmi des chemins possibles.
 */
function pick(obj, keys, fallback = null) {
  for (const k of keys) {
    const v = obj?.[k];
    if (v !== undefined && v !== null) return v;
  }
  return fallback;
}

/**
 * Normalise type_contrat vers valeurs canon:
 * - "prix_unique"
 * - "heures_creuses"
 * Accepte legacy: "fixe", "hp-hc"
 */
function normalizeTypeContrat(v) {
  const s = (v ?? "").toString().trim().toLowerCase();
  if (s === "heures_creuses" || s === "hp-hc" || s === "hphc" || s === "heurescreuses") {
    return "heures_creuses";
  }
  if (s === "prix_unique" || s === "fixe" || s === "prixunique") {
    return "prix_unique";
  }
  return s || "prix_unique";
}

/**
 * Met à jour les statistiques de capteurs
 */
export function updateSensorStats(sensorsData, selectedIds) {
  const totalSensors =
    Object.values(sensorsData.selected || {}).flat().length +
    Object.values(sensorsData.alternatives || {}).flat().length;

  setText(document.getElementById("totalCapteurs"), totalSensors);
  setText(
    document.getElementById("actifsCapteurs"),
    `${selectedIds.length} / ${totalSensors} capteurs sélectionnés`
  );
}

/**
 * Met à jour les puissances instantanées
 */
export function updateInstantPower(internalPower, externalData, userData) {
  // Snake_case canonique + fallback legacy
  const use_external = !!pick(userData, ["use_external", "useExternal"], false);

  setText(
    document.getElementById("instantaneInterne"),
    internalPower > 0 ? internalPower.toFixed(1) + " W" : "- W"
  );

  if (use_external && externalData) {
    setText(document.getElementById("externeCompact"), externalData.puissance);

    const externalTitle = document.getElementById("externalTitle");
    if (externalTitle) {
      const warning = externalData.indispo ? " ⚠️ INDISPONIBLE" : "";
      externalTitle.innerHTML =
        `Capteur externe de référence : ${externalData.integration} : ` +
        `${externalData.nom} (${externalData.puissance})${warning}`;
    }

    const delta = externalData.consommation - internalPower;
    const deltaText =
      externalData.consommation !== 0 || internalPower !== 0
        ? delta.toFixed(1) + " W"
        : "- W";
    setText(document.getElementById("deltaPuissance"), deltaText);
  } else {
    setText(document.getElementById("externeCompact"), "- W");

    const externalTitle = document.getElementById("externalTitle");
    if (externalTitle) {
      externalTitle.textContent = "Capteur externe de référence : désactivé";
    }

    setText(document.getElementById("deltaPuissance"), "- W");
  }

  // Timestamp
  const refreshSpan = document.getElementById("dernierRefresh");
  if (refreshSpan) {
    refreshSpan.textContent = new Date().toLocaleString();
  }
}

/**
 * Met à jour les informations de contrat et tarifs
 * userData = config user / options renvoyées par backend
 */
export function updateContractInfo(userData) {
  // Canonique snake_case, fallback legacy camelCase listées dans l'audit
  const rawType = pick(userData, ["type_contrat", "typeContrat"], "prix_unique");
  const type_contrat = normalizeTypeContrat(rawType);

  const abonnement_ht = pick(userData, ["abonnement_ht", "abonnementHT"], null);
  const abonnement_ttc = pick(userData, ["abonnement_ttc", "abonnementTTC"], null);

  const prix_ht = pick(userData, ["prix_ht", "prixHT", "prixht"], null);
  const prix_ttc = pick(userData, ["prix_ttc", "prixTTC", "prixttc"], null);

  const prix_ht_hp = pick(userData, ["prix_ht_hp", "prixHTHP", "prixhthp"], null);
  const prix_ttc_hp = pick(userData, ["prix_ttc_hp", "prixTTCHP", "prixttchp"], null);
  const prix_ht_hc = pick(userData, ["prix_ht_hc", "prixHTHC", "prixhthc"], null);
  const prix_ttc_hc = pick(userData, ["prix_ttc_hc", "prixTTCHC", "prixttchc"], null);

  const hc_start = pick(userData, ["hc_start", "hcstart"], null);
  const hc_end = pick(userData, ["hc_end", "hcend"], null);

  setText(
    document.getElementById("typeContratSummary"),
    type_contrat === "heures_creuses" ? "HP/HC" : "Fixe"
  );

  setText(
    document.getElementById("abonnementHTSummary"),
    abonnement_ht != null ? Number(abonnement_ht).toFixed(2) : "-"
  );

  setText(
    document.getElementById("abonnementTTCSummary"),
    abonnement_ttc != null ? Number(abonnement_ttc).toFixed(2) : "-"
  );

  const blocFixe = document.getElementById("blocFixe");
  const blocHpHc = document.getElementById("blocHpHc");

  if (type_contrat === "prix_unique") {
    if (blocFixe) blocFixe.style.display = "block";
    if (blocHpHc) blocHpHc.style.display = "none";

    setText(
      document.getElementById("prixFixeHT"),
      prix_ht != null ? Number(prix_ht).toFixed(4) : "-"
    );
    setText(
      document.getElementById("prixFixeTTC"),
      prix_ttc != null ? Number(prix_ttc).toFixed(4) : "-"
    );
  } else if (type_contrat === "heures_creuses") {
    if (blocFixe) blocFixe.style.display = "none";
    if (blocHpHc) blocHpHc.style.display = "block";

    setText(
      document.getElementById("tarifHPHTSummary"),
      prix_ht_hp != null ? Number(prix_ht_hp).toFixed(4) : "-"
    );
    setText(
      document.getElementById("tarifHPTTCSummary"),
      prix_ttc_hp != null ? Number(prix_ttc_hp).toFixed(4) : "-"
    );
    setText(
      document.getElementById("tarifHCHTSummary"),
      prix_ht_hc != null ? Number(prix_ht_hc).toFixed(4) : "-"
    );
    setText(
      document.getElementById("tarifHCTTCSummary"),
      prix_ttc_hc != null ? Number(prix_ttc_hc).toFixed(4) : "-"
    );

    // Attention: ids "heuresHPDebut/Fin" semblent en fait HC start/end, garder tel quel si c'est ton HTML
    setText(
      document.getElementById("heuresHPDebutSummary"),
      hc_start != null ? String(hc_start) : "-"
    );
    setText(
      document.getElementById("heuresHPFinSummary"),
      hc_end != null ? String(hc_end) : "-"
    );
  } else {
    if (blocFixe) blocFixe.style.display = "none";
    if (blocHpHc) blocHpHc.style.display = "none";
  }
}

/**
 * Rendu du panneau "Top consommateurs (live)".
 * @param {HTMLElement} container
 * @param {{lowRange:Array, highRange:Array}} topData
 */
export function renderLiveTopConsumers(container, topData) {
  if (!container || !topData) return;

  // Nettoyer l'ancien bloc pour éviter les doublons
  const existing = container.querySelector(".hse-top-consumers");
  if (existing) {
    existing.remove();
  }

  const hasData =
    (topData.lowRange && topData.lowRange.length) ||
    (topData.highRange && topData.highRange.length);

  if (!hasData) {
    return; // rien à afficher
  }

  const panel = document.createElement("div");
  panel.className = "hse-top-consumers";

  const header = document.createElement("div");
  header.className = "hse-top-consumers-header";
  const title = document.createElement("h3");
  title.textContent = "Top consommateurs (live)";
  const subtitle = document.createElement("p");
  subtitle.textContent =
    "Capteurs inclus dans Summary, triés par puissance instantanée.";
  header.appendChild(title);
  header.appendChild(subtitle);
  panel.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "hse-top-consumers-grid";

  const colLow = document.createElement("div");
  colLow.className = "hse-top-consumers-column";
  const colHigh = document.createElement("div");
  colHigh.className = "hse-top-consumers-column";

  colLow.appendChild(makeTopColumnHeader("100–500 W"));
  colHigh.appendChild(makeTopColumnHeader("> 500 W"));

  (topData.lowRange || []).forEach((sensor) => {
    colLow.appendChild(makeTopSensorRow(sensor, "medium"));
  });

  (topData.highRange || []).forEach((sensor) => {
    colHigh.appendChild(makeTopSensorRow(sensor, "high"));
  });

  // Scroll interne si plus de 3 lignes
  if ((topData.lowRange || []).length > 3) {
    colLow.classList.add("hse-top-consumers-scrollable");
  }
  if ((topData.highRange || []).length > 3) {
    colHigh.classList.add("hse-top-consumers-scrollable");
  }

  grid.appendChild(colLow);
  grid.appendChild(colHigh);
  panel.appendChild(grid);

  // Insérer AVANT les tableaux de puissance cumulée (#summaryData)
  const tablesWrapper = container.querySelector("#summaryData");
  if (tablesWrapper && tablesWrapper.parentNode === container) {
    container.insertBefore(panel, tablesWrapper);
  } else {
    // fallback si la structure change
    container.appendChild(panel);
  }
}

function makeTopColumnHeader(label) {
  const el = document.createElement("div");
  el.className = "hse-top-consumers-col-header";
  el.textContent = label;
  return el;
}

/**
 * Une ligne capteur pour le top consommateurs.
 * level = "medium" | "high" pour la couleur de pastille.
 */
function makeTopSensorRow(sensor, level) {
  const row = document.createElement("div");
  row.className = `hse-top-consumers-row level-${level}`;

  const left = document.createElement("div");
  left.className = "hse-top-consumers-left";

  // Ligne unique : Nom · Intégration (avec ellipsis via CSS)
  const line = document.createElement("div");
  line.className = "hse-top-consumers-line";
  line.textContent = sensor.name || "";

  if (sensor.integration) {
    line.textContent += ` · ${sensor.integration}`;
  }

  left.appendChild(line);

  const power = document.createElement("div");
  power.className = "hse-top-consumers-power";
  power.textContent = `${sensor.power_w} W`;

  row.appendChild(left);
  row.appendChild(power);

  return row;
}

/**
 * Affiche ou masque les tableaux de données
 */
export function toggleDataVisibility(show) {
  const summaryData = document.getElementById("summaryData");
  if (summaryData) {
    summaryData.style.display = show ? "block" : "none";
  }
}

/**
 * Rendu des 3 tableaux de consommation
 * @param {Object} internalKwh - Map des kWh internes { day: X, week: Y, ... }
 * @param {Object} externalKwh - Map des kWh externes
 * @param {Object} deltaKwh - Map des deltas
 * @param {Object} userData - Options utilisateur
 */
export function renderTables(internalKwh, externalKwh, deltaKwh, userData) {
  const container = document.getElementById("summaryData");
  if (!container) {
    console.warn("[summary.view] Container summaryData introuvable");
    return;
  }

  const tablesHTML = renderSummaryTables(
    internalKwh,
    externalKwh,
    deltaKwh,
    userData
  );
  container.innerHTML = tablesHTML;
  container.style.display = "block";
}

/**
 * Rendu global de la vue Summary (bannière + sections)
 */
export function renderSummaryView(container, summaryData) {
  if (!container) return;
  container.innerHTML = "";

  const { reference_sensor } = summaryData || {};

  // BLOC CAPTEUR DE RÉFÉRENCE
  if (reference_sensor && reference_sensor.entity_id) {
    const refBanner = document.createElement("div");
    refBanner.className = "hse-reference-banner";
    refBanner.style.cssText =
      "background:#e3f2fd; border-left:4px solid #2196f3; padding:12px; margin-bottom:16px; border-radius:4px;";
    refBanner.innerHTML = `
      <strong style="color:#1976d2;">⭐ Capteur de référence :</strong> 
      <span style="font-weight:500;">${
        reference_sensor.friendly_name || reference_sensor.entity_id
      }</span>
      <span style="color:#666; font-size:12px; margin-left:8px;">${
        reference_sensor.integration || "N/A"
      }</span>
    `;
    container.appendChild(refBanner);
  }

  // WARNING SI PAS DE RÉFÉRENCE (on n'interrompt plus le rendu)
  if (!reference_sensor || !reference_sensor.entity_id) {
    const warn = document.createElement("div");
    warn.style.cssText =
      "background:#fff3cd; border-left:4px solid #ffb300; padding:12px; margin-bottom:16px; border-radius:4px; color:#856404;";
    warn.textContent =
      "⚠️ Aucun capteur de référence défini. Les calculs de consommation sont inactifs.";
    container.appendChild(warn);
  }
}
