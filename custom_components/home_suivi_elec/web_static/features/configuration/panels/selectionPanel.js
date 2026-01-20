// selectionPanel.js
"use strict";

import { emit } from "../../../shared/eventBus.js";
import { createQualityBadgeHTML } from "../../../shared/utils/sensorScoring.js";
import { createRoleBadgeHTML } from "../../../shared/utils/sensorRoles.js";
//import { apiSetCostHa } from "../configuration.api.js";

/**
 * Construit une ligne capteur avec checkbox
 */
function createSensorRow(opts) {
  const { capteur, isSelected, refEntityId, handlers } = opts;
  const entityId = capteur.entity_id;

  // 🔍 Debug: voir exactement ce que contient capteur
  console.log("[HSE selectionPanel] capteur row =", entityId, capteur);

  const row = document.createElement("div");
  row.className = "sensor-row";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "capteur-checkbox";
  checkbox.dataset.entity = entityId;
  checkbox.checked = !!isSelected;
  checkbox.addEventListener("change", (e) => {
    const checked = e.target.checked;
    if (handlers && typeof handlers.checkbox === "function") {
      handlers.checkbox(entityId, checked);
      emit("hse:selection-changed", { entity_id: entityId, checked });
    }
  });

  const label = document.createElement("div");
  label.className = "hse-sensor-label";

  const name = document.createElement("div");
  name.className = "hse-sensor-name";
  name.textContent = capteur.friendly_name || entityId;
  if (entityId === refEntityId) {
    name.textContent += " ⭐";
  }

  const roleHTML = createRoleBadgeHTML(capteur);
  if (roleHTML) {
    const span = document.createElement("span");
    span.innerHTML = roleHTML;
    name.appendChild(span);
  }

  // 🔹 Badge Coût à côté du badge rôle (Énergie)
  const hasCostEntity =
    capteur.cost_ha_enabled === true ||
    (typeof capteur.cost_ha_entity_id === "string" &&
      capteur.cost_ha_entity_id.length > 0);

  if (hasCostEntity) {
    const costBadge = document.createElement("span");
    costBadge.textContent = "Coût";
    costBadge.className = "hse-cost-badge";
    name.appendChild(costBadge);
  }

  const meta = document.createElement("div");
  meta.className = "hse-sensor-meta";

  const integSpan = document.createElement("span");
  integSpan.textContent = capteur.integration || "—";

  const qualityWrapper = document.createElement("span");
  qualityWrapper.innerHTML = createQualityBadgeHTML(capteur) || "";

  // NEW: toggle include_in_summary
  let currentSummary = !!capteur.include_in_summary;

  const summaryToggle = document.createElement("button");
  summaryToggle.type = "button";
  summaryToggle.className = "hse-summary-toggle";

  const updateSummaryVisual = () => {
    summaryToggle.textContent = currentSummary ? "Summary: oui" : "Summary: non";
    summaryToggle.classList.toggle("is-on", currentSummary);
  };
  updateSummaryVisual();

  summaryToggle.onclick = () => {
    const next = !currentSummary;
    currentSummary = next;
    updateSummaryVisual();
    if (handlers && typeof handlers.toggleSummary === "function") {
      handlers.toggleSummary(entityId, next);
    }
  };

  meta.appendChild(integSpan);
  meta.appendChild(qualityWrapper);
  meta.appendChild(summaryToggle);

  label.appendChild(name);
  label.appendChild(meta);

  row.appendChild(checkbox);
  row.appendChild(label);

  return row;
}

/**
 * Crée un header pliable pour une intégration
 */
function createIntegrationHeader(opts) {
  const {
    columnName,
    integrationKey,
    count,
    folded,
    setFold,
    bodyEl,
    handlers,
  } = opts;

  const header = document.createElement("div");
  header.className = "integration-header";

  const title = document.createElement("span");
  title.textContent = `${folded ? "▶" : "▼"} ${integrationKey} (${count})`;

  const right = document.createElement("div");
  right.className = "integration-right";

  const badge = document.createElement("span");
  badge.textContent = count;
  badge.className = "integration-count-badge";

  // Boutons bulk Summary
  const summaryAllOn = document.createElement("button");
  summaryAllOn.type = "button";
  summaryAllOn.textContent = "Summary: tout oui";
  summaryAllOn.className = "hse-summary-bulk is-on";
  summaryAllOn.onclick = (e) => {
    e.stopPropagation();
    if (handlers && typeof handlers.setSummaryForIntegration === "function") {
      handlers.setSummaryForIntegration(integrationKey, true);
    }
  };

  const summaryAllOff = document.createElement("button");
  summaryAllOff.type = "button";
  summaryAllOff.textContent = "tout non";
  summaryAllOff.className = "hse-summary-bulk is-off";
  summaryAllOff.onclick = (e) => {
    e.stopPropagation();
    if (handlers && typeof handlers.setSummaryForIntegration === "function") {
      handlers.setSummaryForIntegration(integrationKey, false);
    }
  };

  right.appendChild(badge);
  right.appendChild(summaryAllOn);
  right.appendChild(summaryAllOff);

  header.appendChild(title);
  header.appendChild(right);

  header.addEventListener("click", () => {
    const currentlyFolded = !!bodyEl.hidden;
    const newFold = !currentlyFolded;
    bodyEl.hidden = newFold;
    title.textContent = `${newFold ? "▶" : "▼"} ${integrationKey} (${count})`;
    if (setFold) {
      setFold(columnName, integrationKey, newFold);
    }
  });

  return header;
}

/**
 * Rend une colonne (sélectionnés ou alternatives) groupée par intégration
 */
function renderIntegrationColumn(opts) {
  const {
    parentEl,
    title,
    dataByIntegration,
    columnName,
    refEntityId,
    handlers,
    getFold,
    setFold,
    isSelectedColumn,
  } = opts || {};
  if (!parentEl) return;

  const col = document.createElement("div");
  col.className = `capteur-column ${columnName}`;

  const h = document.createElement("h3");
  h.textContent = title;
  col.appendChild(h);

  const integrations = Object.keys(dataByIntegration || {}).sort();

  if (integrations.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hse-selection-empty";
    empty.textContent = isSelectedColumn
      ? "Aucun capteur sélectionné"
      : "Aucune alternative disponible";
    col.appendChild(empty);
    parentEl.appendChild(col);
    return;
  }

  integrations.forEach((integrationKey) => {
    const rawSensors = dataByIntegration[integrationKey] || [];
    const sensors = rawSensors.filter(
      (capteur) => capteur.entity_id !== refEntityId
    );
    console.log(
      "[HSE selectionPanel] integration =",
      integrationKey,
      "refEntityId =",
      refEntityId,
      "raw =",
      rawSensors.length,
      "after filter =",
      sensors.length
    );

    const folded =
      typeof getFold === "function" ? !!getFold(columnName, integrationKey) : false;

    const section = document.createElement("div");
    section.className = "integration-section";

    const body = document.createElement("div");
    body.hidden = folded;

    const header = createIntegrationHeader({
      columnName,
      integrationKey,
      count: sensors.length,
      folded,
      setFold,
      bodyEl: body,
      handlers,
    });

    section.appendChild(header);

    const actions = document.createElement("div");
    actions.className = "integration-actions";

    const btnAll = document.createElement("button");
    btnAll.type = "button";
    btnAll.textContent = "Tout sélectionner";
    btnAll.className = "hse-btn-mini";
    btnAll.onclick = () => {
      if (handlers && typeof handlers.selectAll === "function") {
        handlers.selectAll(integrationKey);
      }
    };

    const btnNone = document.createElement("button");
    btnNone.type = "button";
    btnNone.textContent = "Tout désélectionner";
    btnNone.className = "hse-btn-mini";
    btnNone.onclick = () => {
      if (handlers && typeof handlers.deselectAll === "function") {
        handlers.deselectAll(integrationKey);
      }
    };

    actions.appendChild(btnAll);
    actions.appendChild(btnNone);
    section.appendChild(actions);

    sensors.forEach((capteur) => {
      const row = createSensorRow({
        capteur,
        isSelected: !!isSelectedColumn,
        refEntityId,
        handlers,
      });
      body.appendChild(row);
    });

    section.appendChild(body);
    col.appendChild(section);
  });

  parentEl.appendChild(col);
}

/**
 * Entrée principale appelée par configuration.js
 */
export function renderSelectionColumns(parentEl, cfg) {
  const {
    selected = {},
    alternatives = {},
    refEntityId,
    handlers,
    getFold,
    setFold,
  } = cfg || {};
  if (!parentEl) return;

  console.log("[HSE selectionPanel] refEntityId =", refEntityId);
  console.log(
    "[HSE selectionPanel] alternatives.template raw =",
    (alternatives?.template || []).length
  );

  // On nettoie le conteneur, mais on ne touche plus à son display global
  parentEl.innerHTML = "";

  // Wrapper dédié pour les 2 colonnes de sélection
  const wrapper = document.createElement("div");
  wrapper.className = "hse-selection-columns";

  // Colonne "Capteurs sélectionnés"
  renderIntegrationColumn({
    parentEl: wrapper,
    title: "Capteurs sélectionnés",
    dataByIntegration: selected,
    columnName: "selected",
    refEntityId,
    handlers,
    getFold,
    setFold,
    isSelectedColumn: true,
  });

  // Colonne "Alternatives / Doublons"
  renderIntegrationColumn({
    parentEl: wrapper,
    title: "Alternatives / Doublons",
    dataByIntegration: alternatives,
    columnName: "alternatives",
    refEntityId,
    handlers,
    getFold,
    setFold,
    isSelectedColumn: false,
  });

  // On insère le bloc au-dessus du reste du contenu (dont les 3 colonnes de doublons)
  parentEl.appendChild(wrapper);
}
