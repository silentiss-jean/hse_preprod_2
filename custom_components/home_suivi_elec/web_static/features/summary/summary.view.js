"use strict";

/**
 * Couche View pour Summary
 * Gère le rendu et la mise à jour du DOM
 */

import { renderSummaryTables } from "./logic/tableRenderer.js";
import { showCacheBadge } from "./logic/summary.loader.js";

function setText(el, text) {
  if (el) el.textContent = text;
}

function pick(obj, keys, fallback = null) {
  for (const k of keys) {
    const v = obj?.[k];
    if (v !== undefined && v !== null) return v;
  }
  return fallback;
}

function normalizeTypeContrat(v) {
  const s = (v ?? "").toString().trim().toLowerCase();
  if (
    s === "heures_creuses" ||
    s === "hp-hc" ||
    s === "hphc" ||
    s === "heurescreuses"
  ) {
    return "heures_creuses";
  }
  if (s === "prix_unique" || s === "fixe" || s === "prixunique") {
    return "prix_unique";
  }
  return s || "prix_unique";
}

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

export function updateInstantPower(internalPower, externalData, userData) {
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

  const refreshSpan = document.getElementById("dernierRefresh");
  if (refreshSpan) {
    refreshSpan.textContent = new Date().toLocaleString();
  }
}

export function updateContractInfo(userData) {
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

export function renderLiveTopConsumers(container, topData) {
  if (!container || !topData) return;

  const existing = container.querySelector(".hse-top-consumers");
  if (existing) existing.remove();

  const hasData =
    (topData.lowRange && topData.lowRange.length) ||
    (topData.highRange && topData.highRange.length);
  if (!hasData) return;

  const panel = document.createElement("div");
  panel.className = "hse-top-consumers hse-surface-card";

  const header = document.createElement("div");
  header.className = "hse-top-consumers-header";
  const title = document.createElement("h3");
  title.classList.add("hse-title-gradient");
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

  colLow.appendChild(makeTopColumnHeader("Appareils (100–500 W)"));
  colHigh.appendChild(makeTopColumnHeader("Appareils (> 500 W)"));

  (topData.lowRange || []).forEach((sensor) => {
    colLow.appendChild(makeTopSensorRow(sensor, "medium"));
  });
  (topData.highRange || []).forEach((sensor) => {
    colHigh.appendChild(makeTopSensorRow(sensor, "high"));
  });

  if ((topData.lowRange || []).length > 3) {
    colLow.classList.add("hse-top-consumers-scrollable");
  }
  if ((topData.highRange || []).length > 3) {
    colHigh.classList.add("hse-top-consumers-scrollable");
  }

  grid.appendChild(colLow);
  grid.appendChild(colHigh);
  panel.appendChild(grid);

  const tablesWrapper = container.querySelector("#summaryData");
  if (tablesWrapper && tablesWrapper.parentNode === container) {
    container.insertBefore(panel, tablesWrapper);
  } else {
    container.appendChild(panel);
  }
}

function makeTopColumnHeader(label) {
  const el = document.createElement("div");
  el.className = "hse-top-consumers-col-header";
  el.textContent = label;
  return el;
}

function makeTopSensorRow(sensor, level) {
  const row = document.createElement("div");
  row.className = `hse-top-consumers-row level-${level}`;

  const left = document.createElement("div");
  left.className = "hse-top-consumers-left";

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

export function toggleDataVisibility(show) {
  const summaryData = document.getElementById("summaryData");
  if (summaryData) {
    summaryData.hidden = !show;
  }
}

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
  container.hidden = false;

  // Comportement prod: Externe + Delta seulement si capteur de référence activé
  const use_external = !!pick(userData, ["use_external", "useExternal"], false);
  const showExternalDelta = use_external;

  const externalTitle = document.getElementById("externalSummaryTitle");
  const externalTable = document.getElementById("summaryExternalSensors");
  const deltaTitle = document.getElementById("deltaSummaryTitle");
  const deltaTable = document.getElementById("summaryDeltaSensors");

  if (externalTitle) externalTitle.hidden = !showExternalDelta;
  if (externalTable) externalTable.hidden = !showExternalDelta;
  if (deltaTitle) deltaTitle.hidden = !showExternalDelta;
  if (deltaTable) deltaTable.hidden = !showExternalDelta;
}

export function renderSummaryView(container, summaryData) {
  if (!container) return;
  container.innerHTML = "";

  const { reference_sensor } = summaryData || {};
  const hasRef = !!(reference_sensor && reference_sensor.entity_id);

  if (hasRef) {
    const refBanner = document.createElement("div");
    refBanner.className = "hse-banner hse-banner-info";

    refBanner.innerHTML = `
      <div class="hse-banner-title">⭐ Capteur de référence :</div>
      <div class="hse-banner-body">
        <span class="hse-banner-strong">${reference_sensor.friendly_name || reference_sensor.entity_id}</span>
        <span class="hse-banner-meta">${reference_sensor.integration || "N/A"}</span>
      </div>
    `;

    container.appendChild(refBanner);
  } else {
    const warn = document.createElement("div");
    warn.className = "hse-banner hse-banner-warn";
    warn.textContent =
      "⚠️ Aucun capteur de référence défini. Les calculs de consommation sont inactifs.";
    container.appendChild(warn);
  }
}

export function renderCostsGlobalPanel(container, globalData) {
  if (!container || !globalData) return;

  const existing = container.querySelector(".hse-costs-global-panel");
  if (existing) existing.remove();

  const panel = document.createElement("div");
  panel.className = "hse-costs-global-panel hse-surface-card";

  const header = document.createElement("div");
  header.className = "hse-costs-header";
  const title = document.createElement("h3");
  title.classList.add("hse-title-gradient");
  title.textContent = "Coûts globaux";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Consommation + Abonnement (tous capteurs sélectionnés)";
  header.appendChild(title);
  header.appendChild(subtitle);
  panel.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "hse-costs-grid";

  const periods = [
    { key: "day", label: "Jour", icon: "📅" },
    { key: "week", label: "Semaine", icon: "📆" },
    { key: "month", label: "Mois", icon: "📊" },
    { key: "year", label: "Année", icon: "📈" },
  ];

  periods.forEach(({ key, label, icon }) => {
    const data = globalData[key];
    if (!data) return;

    const card = document.createElement("div");
    card.className = "hse-costs-card hse-surface-card";

    const cacheBadge = showCacheBadge(
      !!data.from_cache,
      Number(data.cached_age || 0)
    );

    card.innerHTML = `
      <div class="hse-costs-card-header">
        <span class="hse-costs-icon">${icon}</span>
        <span class="hse-costs-period">${label}</span>
        ${cacheBadge}
      </div>
      <div class="hse-costs-card-body">
        <div class="hse-costs-row">
          <span class="hse-costs-label">Énergie</span>
          <span class="hse-costs-value">${data.energy_kwh.toFixed(2)} kWh</span>
        </div>
        <div class="hse-costs-row">
          <span class="hse-costs-label">Conso TTC</span>
          <span class="hse-costs-value">${data.cost_ttc.toFixed(2)} €</span>
        </div>
        <div class="hse-costs-row">
          <span class="hse-costs-label">Abonnement TTC</span>
          <span class="hse-costs-value">${data.subscription_ttc.toFixed(2)} €</span>
        </div>
        <div class="hse-costs-row hse-costs-total">
          <span class="hse-costs-label">Total TTC</span>
          <span class="hse-costs-value hse-costs-highlight">${data.total_ttc.toFixed(2)} €</span>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  panel.appendChild(grid);
  container.appendChild(panel);
}

export function renderCostsPerEntityTable(container, entities) {
  if (!container || !entities || !entities.length) return;

  const existing = container.querySelector(".hse-costs-per-entity");
  if (existing) existing.remove();

  const panel = document.createElement("div");
  panel.className = "hse-costs-per-entity hse-surface-card";

  const header = document.createElement("div");
  header.className = "hse-costs-header";
  const title = document.createElement("h3");
  title.classList.add("hse-title-gradient");
  title.textContent = "Coûts par capteur";
  const subtitle = document.createElement("p");
  subtitle.textContent = `${entities.length} capteurs · Triés par coût journalier décroissant`;
  header.appendChild(title);
  header.appendChild(subtitle);
  panel.appendChild(header);

  const searchBar = document.createElement("div");
  searchBar.className = "hse-costs-search";
  searchBar.innerHTML = `
    <input
      type="text"
      id="costsSearchInput"
      placeholder="🔍 Rechercher un capteur..."
      class="hse-costs-search-input"
    />
  `;
  panel.appendChild(searchBar);

  const tableWrapper = document.createElement("div");
  tableWrapper.className = "hse-costs-table-wrapper";

  const table = document.createElement("table");
  table.className = "hse-costs-table";
  table.id = "costsPerEntityTable";

  table.innerHTML = `
    <thead>
      <tr>
        <th class="hse-costs-th">Capteur</th>
        <th class="hse-costs-th hse-costs-th-number">Jour (€)</th>
        <th class="hse-costs-th hse-costs-th-number">Semaine (€)</th>
        <th class="hse-costs-th hse-costs-th-number">Mois (€)</th>
        <th class="hse-costs-th hse-costs-th-number">Année (€)</th>
      </tr>
    </thead>
    <tbody id="costsPerEntityTableBody"></tbody>
  `;

  const tbody = table.querySelector("#costsPerEntityTableBody");

  entities.forEach((entity) => {
    const row = document.createElement("tr");
    row.className = "hse-costs-tr";
    row.setAttribute("data-entity-id", entity.entity_id);
    row.setAttribute("data-display-name", entity.display_name.toLowerCase());

    row.innerHTML = `
      <td class="hse-costs-td">
        <div class="hse-costs-entity-name">${entity.display_name}</div>
        <div class="hse-costs-entity-meta">${entity.integration} · ${entity.entity_id}</div>
      </td>
      <td class="hse-costs-td hse-costs-td-number">${entity.day_cost_ttc.toFixed(2)}</td>
      <td class="hse-costs-td hse-costs-td-number">${entity.week_cost_ttc.toFixed(2)}</td>
      <td class="hse-costs-td hse-costs-td-number">${entity.month_cost_ttc.toFixed(2)}</td>
      <td class="hse-costs-td hse-costs-td-number">${entity.year_cost_ttc.toFixed(2)}</td>
    `;

    tbody.appendChild(row);
  });

  tableWrapper.appendChild(table);
  panel.appendChild(tableWrapper);
  container.appendChild(panel);

  const searchInput = document.getElementById("costsSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      const rows = tbody.querySelectorAll(".hse-costs-tr");

      rows.forEach((row) => {
        const name = row.getAttribute("data-display-name") || "";
        const entityId = row.getAttribute("data-entity-id") || "";

        if (name.includes(query) || entityId.includes(query)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
  }
}
