"use strict";

/**
 * Panel Regroupement de capteurs (Customisation)
 *
 * Structure manipulée :
 * {
 *   groupKey: {
 *     name: string,
 *     mode: "auto" | "manual" | "mixed",
 *     energy: string[],
 *     power: string[]
 *   },
 *   ...
 * }
 */

import { createElement } from "../../../shared/utils/dom.js";
import { Button } from "../../../shared/components/Button.js";
import { Toast } from "../../../shared/components/Toast.js";

import {
  getGroupsState,
  setGroupsState,
  renameGroupInState,
  setGroupModeInState,
} from "../customisation.state.js";

import {
  getGroups,
  autoGroup,
  saveGroups,
} from "../customisation.api.js";

// État local UI
const collapsedByGroup = new Map();
const collapsedFamilies = new Map();
let globalFilter = "";
let sortAsc = true;

// Références globales pour les selects de la barre d'action de masse
let bulkScopeSelect = null;
let bulkTargetSelect = null;

// Utils ----------------------------------------------------------------------

function keyForFamilyCollapse(groupKey, kind, familyKey) {
  return `${groupKey}:${kind}:${familyKey}`;
}

/**
 * Extrait la "base" d'une entity_id pour regrouper parent/enfants.
 */
function familyBase(entityId, kind) {
  if (!entityId) return "";
  let base = entityId.trim();

  if (kind === "energy") {
    base = base.replace(/_today_energy$/i, "");
    base = base.replace(/_energy$/i, "");
    base = base.replace(/_energy_(hourly|daily|weekly|monthly|yearly)$/i, "");
  } else {
    base = base.replace(/_power_energy_(hourly|daily|weekly|monthly|yearly)$/i, "");
    base = base.replace(/_power_energy$/i, "");
    base = base.replace(/_power$/i, "");
  }
  return base;
}

/**
 * Choisit le parent "id court" dans une famille.
 */
function pickParent(kind, items) {
  if (!items || items.length === 0) return null;
  if (kind === "energy") {
    const today = items.find((id) => /_today_energy$/i.test(id));
    if (today) return today;
    const plain = items.find((id) => /_energy$/i.test(id));
    if (plain) return plain;
  } else {
    const plainPower = items.find((id) => /_power$/i.test(id));
    if (plainPower) return plainPower;
    const powerEnergy = items.find((id) => /_power_energy$/i.test(id));
    if (powerEnergy) return powerEnergy;
  }
  return [...items].sort((a, b) => a.length - b.length || a.localeCompare(b))[0];
}

/**
 * Construit les familles parent -> enfants.
 */
function buildFamilies(list, kind) {
  const byBase = new Map();
  (list || []).forEach((eid) => {
    const base = familyBase(eid, kind);
    if (!byBase.has(base)) byBase.set(base, []);
    byBase.get(base).push(eid);
  });

  const families = [];
  byBase.forEach((items, base) => {
    const parent = pickParent(kind, items);
    const children = items.filter((x) => x !== parent);
    families.push({
      key: base || parent || (items[0] || ""),
      parent,
      children: children.sort((a, b) => a.localeCompare(b)),
      all: items.sort((a, b) => a.localeCompare(b)),
    });
  });

  families.sort((a, b) => {
    const ka = a.key || a.parent || "";
    const kb = b.key || b.parent || "";
    return sortAsc ? ka.localeCompare(kb) : kb.localeCompare(ka);
  });

  return families;
}

/**
 * Applique le déplacement d'UN capteur.
 */
function performSensorMove(groups, fromKey, toKey, entityId, kind) {
  const groupsCopy = JSON.parse(JSON.stringify(groups || {}));

  const from = groupsCopy[fromKey];
  if (!from) return groups;

  const fromList = kind === "energy" ? from.energy : from.power;
  if (!Array.isArray(fromList)) return groups;

  const idx = fromList.indexOf(entityId);
  if (idx === -1) return groups;

  fromList.splice(idx, 1);

  let target = groupsCopy[toKey];
  if (!target) {
    target = {
      name: toKey,
      mode: "manual",
      energy: [],
      power: [],
    };
    groupsCopy[toKey] = target;
  }

  const targetList = kind === "energy" ? target.energy : target.power;
  if (!targetList.includes(entityId)) {
    targetList.push(entityId);
  }

  return groupsCopy;
}

/**
 * Applique la copie d'UN capteur (n'enlève pas du groupe source).
 */
function performSensorCopy(groups, fromKey, toKey, entityId, kind) {
  const groupsCopy = JSON.parse(JSON.stringify(groups || {}));

  const from = groupsCopy[fromKey];
  if (!from) return groups;

  const fromList = kind === "energy" ? from.energy : from.power;
  if (!Array.isArray(fromList)) return groups;

  // Sécurité: ne copier que si le capteur existe bien dans le groupe source
  if (!fromList.includes(entityId)) return groups;

  let target = groupsCopy[toKey];
  if (!target) {
    target = {
      name: toKey,
      mode: "manual",
      energy: [],
      power: [],
    };
    groupsCopy[toKey] = target;
  }

  const targetList = kind === "energy" ? target.energy : target.power;
  if (!targetList.includes(entityId)) {
    targetList.push(entityId);
  }

  return groupsCopy;
}

/**
 * Applique le déplacement de PLUSIEURS capteurs (bulk move).
 */
function performBulkMove(groups, fromKey, toKey, entityIds, kind) {
  let result = groups;
  entityIds.forEach((eid) => {
    result = performSensorMove(result, fromKey, toKey, eid, kind);
  });
  return result;
}

/**
 * Applique la copie de PLUSIEURS capteurs (bulk copy).
 */
function performBulkCopy(groups, fromKey, toKey, entityIds, kind) {
  let result = groups;
  entityIds.forEach((eid) => {
    result = performSensorCopy(result, fromKey, toKey, eid, kind);
  });
  return result;
}

/**
 * Déplace TOUS les capteurs contenant un keyword vers une pièce cible.
 * scope: "all" | groupKey (pour limiter à une seule pièce)
 */
function performKeywordBulkMove(groups, keyword, targetKey, scope) {
  if (!keyword || !targetKey) return groups;

  const q = keyword.toLowerCase();
  let result = JSON.parse(JSON.stringify(groups || {}));

  const keys = scope === "all" ? Object.keys(result) : [scope];

  keys.forEach((gKey) => {
    const grp = result[gKey];
    if (!grp) return;

    // Energy
    const energyMatches = (grp.energy || []).filter((eid) =>
      eid.toLowerCase().includes(q)
    );
    energyMatches.forEach((eid) => {
      result = performSensorMove(result, gKey, targetKey, eid, "energy");
    });

    // Power
    const powerMatches = (grp.power || []).filter((eid) =>
      eid.toLowerCase().includes(q)
    );
    powerMatches.forEach((eid) => {
      result = performSensorMove(result, gKey, targetKey, eid, "power");
    });
  });

  return result;
}

/**
 * Copie TOUS les capteurs contenant un keyword vers un groupe cible.
 * scope: "all" | groupKey (pour limiter à un seul groupe)
 */
function performKeywordBulkCopy(groups, keyword, targetKey, scope) {
  if (!keyword || !targetKey) return groups;

  const q = keyword.toLowerCase();
  let result = JSON.parse(JSON.stringify(groups || {}));

  const keys = scope === "all" ? Object.keys(result) : [scope];

  keys.forEach((gKey) => {
    const grp = result[gKey];
    if (!grp) return;

    // Energy
    const energyMatches = (grp.energy || []).filter((eid) =>
      eid.toLowerCase().includes(q)
    );
    energyMatches.forEach((eid) => {
      result = performSensorCopy(result, gKey, targetKey, eid, "energy");
    });

    // Power
    const powerMatches = (grp.power || []).filter((eid) =>
      eid.toLowerCase().includes(q)
    );
    powerMatches.forEach((eid) => {
      result = performSensorCopy(result, gKey, targetKey, eid, "power");
    });
  });

  return result;
}

/**
 * Met à jour les selects de la barre d'action de masse.
 */
function updateBulkSelects() {
  const s = getGroupsState();
  const keys = Object.keys(s.groups || {});

  if (!bulkScopeSelect || !bulkTargetSelect) {
    return;
  }

  // Scope
  bulkScopeSelect.innerHTML = "";
  const allScopeOpt = document.createElement("option");
  allScopeOpt.value = "all";
  allScopeOpt.textContent = "Toutes les pièces";
  bulkScopeSelect.appendChild(allScopeOpt);

  keys.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = s.groups[k]?.name || k;
    bulkScopeSelect.appendChild(opt);
  });

  // Target
  bulkTargetSelect.innerHTML = "";
  keys.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = s.groups[k]?.name || k;
    bulkTargetSelect.appendChild(opt);
  });
  const newOpt = document.createElement("option");
  newOpt.value = "__new__";
  newOpt.textContent = "+ Nouveau groupe…";
  bulkTargetSelect.appendChild(newOpt);
}

// Modal déplacement (une famille ou un seul capteur) -------------------------

function openMoveSensorModal(container, groupKey, entityIds, kind, defaultAction = "move") {
  const state = getGroupsState();
  const groups = state.groups || {};
  const groupKeys = Object.keys(groups);
  if (groupKeys.length === 0) return;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const modal = document.createElement("div");
  modal.className = "modal-content modal-small";

  const header = createElement("div", { className: "modal-header" });
  const h2 = document.createElement("h2");
  h2.textContent = "Déplacer / Copier des capteurs";

  const closeBtn = createElement("button", {
    type: "button",
    className: "modal-close-btn",
  });
  closeBtn.innerHTML = "×";
  closeBtn.addEventListener("click", () => {
    document.body.removeChild(overlay);
  });

  header.appendChild(h2);
  header.appendChild(closeBtn);

  const body = createElement("div", { className: "modal-body" });

  const info = document.createElement("p");

  const actionLabel = document.createElement("p");
  actionLabel.className = "hse-modal-or";
  actionLabel.textContent = "Action :";

  const actionSelect = createElement("select", {
    className: "hse-select hse-modal-select",
  });

  const moveOpt = document.createElement("option");
  moveOpt.value = "move";
  moveOpt.textContent = "Déplacer";

  const copyOpt = document.createElement("option");
  copyOpt.value = "copy";
  copyOpt.textContent = "Copier";

  actionSelect.appendChild(moveOpt);
  actionSelect.appendChild(copyOpt);

  // Default
  actionSelect.value = defaultAction === "copy" ? "copy" : "move";

  const idsArrayForText = Array.isArray(entityIds) ? entityIds : [entityIds];

  function updateInfoText() {
    const verb = actionSelect.value === "copy" ? "Copier" : "Déplacer";
    if (idsArrayForText.length > 1) {
      info.textContent = `${verb} ${idsArrayForText.length} capteurs (${kind}) vers :`;
    } else {
      const eid = idsArrayForText[0];
      info.textContent = `${verb} ${eid} (${kind}) vers :`;
    }
  }

  updateInfoText();

  body.appendChild(info);
  body.appendChild(actionLabel);
  body.appendChild(actionSelect);

  const select = createElement("select", {
    className: "hse-select hse-modal-select",
  });

  groupKeys
    .sort((a, b) => (groups[a]?.name || a).localeCompare(groups[b]?.name || b))
    .forEach((k) => {
      const cfg = groups[k];
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = cfg.name || k;
      if (k === groupKey) opt.selected = true;
      select.appendChild(opt);
    });

  body.appendChild(select);

  const orText = document.createElement("p");
  orText.className = "hse-modal-or";
  orText.textContent = "Ou créer un nouveau groupe :";
  body.appendChild(orText);

  const newInput = createElement("input", {
    type: "text",
    className: "hse-group-name-input hse-modal-new-input",
    placeholder: "Nom du nouveau groupe",
  });
  body.appendChild(newInput);

  const footer = createElement("div", { className: "modal-footer" });

  const cancelBtn = Button.create(
    "Annuler",
    () => {
      document.body.removeChild(overlay);
    },
    "secondary"
  );

  const confirmBtn = Button.create(
    actionSelect.value === "copy" ? "Copier" : "Déplacer",
    () => {
      let targetName = newInput.value.trim();
      if (!targetName) targetName = select.value;
      if (!targetName || targetName === groupKey) {
        document.body.removeChild(overlay);
        return;
      }

      const currentState = getGroupsState();
      const idsArray = Array.isArray(entityIds) ? entityIds : [entityIds];

      const action = actionSelect.value;
      const updated =
        action === "copy"
          ? performBulkCopy(currentState.groups, groupKey, targetName, idsArray, kind)
          : performBulkMove(currentState.groups, groupKey, targetName, idsArray, kind);

      setGroupsState(updated);

      // UI collapse states
      if (!collapsedByGroup.has(targetName)) {
        collapsedByGroup.set(targetName, false);
      }
      if (action === "move") {
        const wasCollapsedFrom = collapsedByGroup.get(groupKey);
        collapsedByGroup.set(groupKey, wasCollapsedFrom === true);
      }

      updateBulkSelects();
      renderGroupsList(container, getGroupsState().groups);
      document.body.removeChild(overlay);

      Toast.success(
        `${idsArray.length} capteur(s) ${action === "copy" ? "copié(s)" : "déplacé(s)"} vers "${targetName}".`
      );
    },
    "primary"
  );

  actionSelect.addEventListener("change", () => {
    updateInfoText();
    confirmBtn.textContent = actionSelect.value === "copy" ? "Copier" : "Déplacer";
  });

  footer.appendChild(cancelBtn);
  footer.appendChild(confirmBtn);

  modal.appendChild(header);
  modal.appendChild(body);
  modal.appendChild(footer);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

// Rendu colonnes --------------------------------------------------------------

function renderFamilyRow(container, groupKey, kind, family) {
  const famKey = family.key || family.parent || (family.all[0] || "");
  const collapseKey = keyForFamilyCollapse(groupKey, kind, famKey);
  const isCollapsed = collapsedFamilies.get(collapseKey) === true;

  const wrapper = createElement("div", { style: "margin-bottom:6px;" });

  const parentRow = createElement("div", {
    className: "hse-group-sensor-item is-clickable",
    title: "Cliquer pour déplacer/copier toute cette famille de capteurs",
    style: "font-weight:600; display:flex; align-items:center; gap:6px;",
  });

  const caret = createElement("span", {
    style:
      "display:inline-block; width:16px; color:var(--hse-text-muted); cursor:pointer;",
  });
  caret.textContent = isCollapsed ? "▶" : "▼";
  caret.addEventListener("click", (e) => {
    e.stopPropagation();
    const cur = collapsedFamilies.get(collapseKey) === true;
    collapsedFamilies.set(collapseKey, !cur);
    renderGroupsList(container, getGroupsState().groups);
  });

  const label = createElement("span", { style: "flex:1;" });
  label.textContent = family.parent || family.all[0];

  parentRow.appendChild(caret);
  parentRow.appendChild(label);

  // Clic sur parent → déplacer/copier toute la famille
  parentRow.addEventListener("click", () => {
    openMoveSensorModal(container, groupKey, family.all, kind);
  });

  wrapper.appendChild(parentRow);

  // Enfants
  if (!isCollapsed && family.children.length > 0) {
    const childrenBox = createElement("div", {
      style:
        "margin-left:22px; border-left:1px dashed var(--hse-border); padding-left:8px;",
    });

    family.children.forEach((eid) => {
      const row = createElement("div", {
        className: "hse-group-sensor-item is-clickable",
        title: "Cliquer pour déplacer/copier ce capteur seul",
      });
      row.textContent = eid;
      row.addEventListener("click", () => {
        openMoveSensorModal(container, groupKey, [eid], kind);
      });
      childrenBox.appendChild(row);
    });

    wrapper.appendChild(childrenBox);
  }

  return wrapper;
}

function renderSensorColumn(container, groupKey, title, kind, sensors) {
  const col = createElement("div", { className: "hse-group-column" });

  const titleEl = createElement("div", {
    className: "hse-group-column-title",
  });
  titleEl.textContent = title;
  col.appendChild(titleEl);

  let filtered = sensors || [];
  if (globalFilter) {
    const q = globalFilter.toLowerCase();
    filtered = filtered.filter((s) => s.toLowerCase().includes(q));
  }

  const families = buildFamilies(filtered, kind);
  const list = createElement("div", { className: "hse-group-sensor-list" });

  if (families.length === 0) {
    const empty = createElement("div", { className: "hse-group-empty" });
    empty.textContent = `Aucun ${kind}.`;
    list.appendChild(empty);
  } else {
    families.forEach((fam) => {
      list.appendChild(renderFamilyRow(container, groupKey, kind, fam));
    });
  }

  col.appendChild(list);
  return col;
}

// Rendu groupes ---------------------------------------------------------------

function renderGroupsList(container, groups) {
  container.innerHTML = "";

  const entries = Object.entries(groups || {});
  if (entries.length === 0) {
    const empty = createElement("p", { className: "hse-group-empty" });
    empty.textContent = "Aucun groupe défini pour le moment.";
    container.appendChild(empty);
    return;
  }

  if (!container.classList.contains("hse-groups-container")) {
    container.classList.add("hse-groups-container");
  }

  entries.forEach(([key, cfg]) => {
    const name = cfg.name || key;
    const mode = cfg.mode || "manual";
    const energy = cfg.energy || [];
    const power = cfg.power || [];

    const energyCount = energy.length;
    const powerCount = power.length;

    const card = createElement("div", { className: "hse-group-card" });

    // Header carte
    const header = createElement("div", { className: "hse-group-header" });

    const isCollapsed = collapsedByGroup.get(key) === true;

    const toggleBtn = createElement("button", {
      type: "button",
      className: "hse-group-toggle",
    });
    toggleBtn.textContent = isCollapsed ? "▶" : "▼";
    toggleBtn.addEventListener("click", () => {
      const current = collapsedByGroup.get(key) === true;
      collapsedByGroup.set(key, !current);
      renderGroupsList(container, getGroupsState().groups);
    });

    const titleWrapper = createElement("div", { className: "hse-group-title" });

    const iconSpan = createElement("span", { className: "hse-group-icon" });
    iconSpan.textContent = "📦";

    const nameLabel = createElement("span", { className: "hse-group-name-label" });
    nameLabel.textContent = name;

    const counts = createElement("span", { className: "hse-groups-toolbar-info" });
    counts.textContent = `${energyCount} energy / ${powerCount} power`;

    const editBtn = createElement("button", {
      type: "button",
      className: "hse-group-toggle",
      title: "Renommer ce groupe",
    });
    editBtn.textContent = "✏️";
    editBtn.addEventListener("click", () => {
      const newName = window.prompt("Nouveau nom du groupe :", name);
      if (!newName) return;
      const trimmed = newName.trim();
      if (!trimmed || trimmed === key) return;

      renameGroupInState(key, trimmed);

      const wasCollapsed = collapsedByGroup.get(key);
      collapsedByGroup.delete(key);
      collapsedByGroup.set(trimmed, wasCollapsed === true);

      [...collapsedFamilies.keys()].forEach((famK) => {
        const prefix = `${key}:`;
        if (famK.startsWith(prefix)) {
          const rest = famK.slice(prefix.length);
          const newK = `${trimmed}:${rest}`;
          const v = collapsedFamilies.get(famK);
          collapsedFamilies.delete(famK);
          collapsedFamilies.set(newK, v);
        }
      });

      updateBulkSelects();
      renderGroupsList(container, getGroupsState().groups);
    });

    // Bouton suppression de groupe
    const deleteBtn = createElement("button", {
      type: "button",
      className: "hse-group-toggle",
      title: "Supprimer ce groupe",
    });
    deleteBtn.textContent = "🗑️";
    deleteBtn.addEventListener("click", () => {
      const confirmMsg = `Supprimer le groupe "${name}" ? Les capteurs de ce groupe ne seront plus regroupés dans cette interface.`;
      if (!window.confirm(confirmMsg)) return;

      const s = getGroupsState();
      const g = JSON.parse(JSON.stringify(s.groups || {}));
      // Suppression de la clé de groupe dans l'objet
      delete g[key];

      setGroupsState(g);

      // Nettoyage de l'état UI associé
      collapsedByGroup.delete(key);
      [...collapsedFamilies.keys()].forEach((famK) => {
        if (famK.startsWith(`${key}:`)) {
          collapsedFamilies.delete(famK);
        }
      });

      updateBulkSelects();
      renderGroupsList(container, getGroupsState().groups);

      Toast.success(`Groupe "${name}" supprimé.`);
    });

    titleWrapper.appendChild(iconSpan);
    titleWrapper.appendChild(nameLabel);
    titleWrapper.appendChild(counts);
    titleWrapper.appendChild(editBtn);
    titleWrapper.appendChild(deleteBtn);

    const modeSelect = createElement("select", {
      className: "hse-group-mode hse-select",
    });
    ["auto", "manual", "mixed"].forEach((m) => {
      const opt = createElement("option", { value: m });
      opt.textContent = m;
      if (mode === m) opt.selected = true;
      modeSelect.appendChild(opt);
    });
    modeSelect.addEventListener("change", () => {
      setGroupModeInState(key, modeSelect.value);
    });

    header.appendChild(toggleBtn);
    header.appendChild(titleWrapper);
    header.appendChild(modeSelect);

    card.appendChild(header);

    // Corps carte
    const body = createElement("div", { className: "hse-group-body" });
    if (isCollapsed) body.style.display = "none";

    const energyCol = renderSensorColumn(
      container,
      key,
      "Capteurs energy",
      "energy",
      energy
    );
    const powerCol = renderSensorColumn(
      container,
      key,
      "Capteurs power",
      "power",
      power
    );

    body.appendChild(energyCol);
    body.appendChild(powerCol);

    card.appendChild(body);
    container.appendChild(card);
  });
}

// Entrée du panel ------------------------------------------------------------

export async function renderGroupsPanel(container) {
  if (!container) {
    console.error("[customisation][groupsPanel] container manquant");
    return;
  }

  container.innerHTML = "";

  const listContainer = createElement("div");
  listContainer.classList.add("hse-groups-container");

  // === Barre d'actions principales ===
  const header = createElement("div", { className: "hse-groups-headerbar" });

  const title = createElement("h3", { className: "hse-groups-title" });
  title.textContent = "Regroupement des capteurs";

  const spacer = createElement("div", { className: "hse-groups-spacer" });

  const filterInput = createElement("input", {
    type: "text",
    placeholder: "Filtrer les capteurs…",
    className: "hse-group-name-input hse-groups-filter",
  });
  filterInput.addEventListener("input", () => {
    globalFilter = filterInput.value || "";
    renderGroupsList(listContainer, getGroupsState().groups);
  });

  const sortBtn = Button.create(
    sortAsc ? "Tri A→Z" : "Tri Z→A",
    () => {
      sortAsc = !sortAsc;
      sortBtn.textContent = sortAsc ? "Tri A→Z" : "Tri Z→A";
      renderGroupsList(listContainer, getGroupsState().groups);
    },
    "secondary"
  );

  const addGroupBtn = Button.create(
    "+ Ajouter une pièce",
    () => {
      const name = window.prompt("Nom de la nouvelle pièce :");
      if (!name) return;
      const trimmed = name.trim();
      if (!trimmed) return;

      const s = getGroupsState();
      const g = JSON.parse(JSON.stringify(s.groups || {}));
      if (!g[trimmed]) {
        g[trimmed] = { name: trimmed, mode: "manual", energy: [], power: [] };
        setGroupsState(g);
        collapsedByGroup.set(trimmed, false);
        updateBulkSelects();
        renderGroupsList(listContainer, getGroupsState().groups);
      } else {
        Toast.error("Un groupe avec ce nom existe déjà.");
      }
    },
    "secondary"
  );

  const refreshBtn = Button.create(
    "Rafraîchir",
    async () => {
      try {
        refreshBtn.disabled = true;
        const groups = await getGroups();
        setGroupsState(groups);
        updateBulkSelects();
        renderGroupsList(listContainer, getGroupsState().groups);
        Toast.success("Groupes rechargés depuis le backend.");
      } catch (e) {
        console.error("[customisation][groupsPanel] Erreur refresh getGroups:", e);
        Toast.error("Erreur lors du rechargement des groupes.");
      } finally {
        refreshBtn.disabled = false;
      }
    },
    "secondary"
  );

  const autoBtn = Button.create(
    "Regrouper automatiquement",
    async () => {
      try {
        autoBtn.disabled = true;
        const groups = await autoGroup();
        setGroupsState(groups);
        updateBulkSelects();
        renderGroupsList(listContainer, getGroupsState().groups);
        Toast.success("Regroupement automatique effectué.");
      } catch (e) {
        console.error("[customisation][groupsPanel] Erreur autoGroup:", e);
        Toast.error("Erreur lors du regroupement automatique.");
      } finally {
        autoBtn.disabled = false;
      }
    },
    "primary"
  );

  const saveBtn = Button.create(
    "Enregistrer les groupes",
    async () => {
      try {
        saveBtn.disabled = true;
        const current = getGroupsState().groups;
        await saveGroups(current);
        Toast.success("Groupes enregistrés avec succès.");
      } catch (e) {
        console.error("[customisation][groupsPanel] Erreur saveGroups:", e);
        Toast.error("Erreur lors de l'enregistrement des groupes.");
      } finally {
        saveBtn.disabled = false;
      }
    },
    "success"
  );

  header.appendChild(title);
  header.appendChild(spacer);
  header.appendChild(filterInput);
  header.appendChild(sortBtn);
  header.appendChild(addGroupBtn);
  header.appendChild(refreshBtn);
  header.appendChild(autoBtn);
  header.appendChild(saveBtn);

  container.appendChild(header);

  // === Actions de masse par mot-clé ===
  const bulkBar = createElement("div", { className: "hse-groups-bulkbar" });

  const bulkLabel = createElement("span", { className: "hse-groups-bulk-label" });
  bulkLabel.textContent = "Action de masse :";

  const keywordInput = createElement("input", {
    type: "text",
    placeholder: "Mot-clé (ex: emma)…",
    className: "hse-group-name-input hse-groups-keyword",
  });

  const scopeSelect = createElement("select", {
    className: "hse-select hse-groups-select hse-groups-scope",
  });

  const targetSelect = createElement("select", {
    className: "hse-select hse-groups-select hse-groups-target",
  });

  const actionSelect = createElement("select", {
    className: "hse-select hse-groups-select",
  });

  const actionMoveOpt = document.createElement("option");
  actionMoveOpt.value = "move";
  actionMoveOpt.textContent = "Déplacer";

  const actionCopyOpt = document.createElement("option");
  actionCopyOpt.value = "copy";
  actionCopyOpt.textContent = "Copier";

  actionSelect.appendChild(actionMoveOpt);
  actionSelect.appendChild(actionCopyOpt);
  actionSelect.value = "move";

  // Stocke les références globales pour que updateBulkSelects puisse les manipuler
  bulkScopeSelect = scopeSelect;
  bulkTargetSelect = targetSelect;

  const bulkBtn = Button.create(
    "Déplacer en masse",
    () => {
      const kw = keywordInput.value.trim();
      if (!kw) {
        Toast.error("Veuillez saisir un mot-clé.");
        return;
      }

      let targetKey = targetSelect.value;
      if (targetKey === "__new__") {
        const newName = window.prompt("Nom du nouveau groupe :");
        if (!newName) return;
        targetKey = newName.trim();
        if (!targetKey) return;
      }

      const scope = scopeSelect.value;
      const action = actionSelect.value;

      const s = getGroupsState();
      const updated =
        action === "copy"
          ? performKeywordBulkCopy(s.groups, kw, targetKey, scope)
          : performKeywordBulkMove(s.groups, kw, targetKey, scope);

      setGroupsState(updated);
      updateBulkSelects();
      renderGroupsList(listContainer, getGroupsState().groups);

      Toast.success(
        `Capteurs contenant "${kw}" ${action === "copy" ? "copiés" : "déplacés"} vers "${targetKey}".`
      );
    },
    "primary"
  );

  actionSelect.addEventListener("change", () => {
    bulkBtn.textContent = actionSelect.value === "copy" ? "Copier en masse" : "Déplacer en masse";
  });

  bulkBar.appendChild(bulkLabel);
  bulkBar.appendChild(keywordInput);
  bulkBar.appendChild(scopeSelect);
  bulkBar.appendChild(targetSelect);
  bulkBar.appendChild(actionSelect);
  bulkBar.appendChild(bulkBtn);

  container.appendChild(bulkBar);

  // === Légende ===
  const legend = createElement("div", {
    className: "hse-groups-legend hse-groups-toolbar-info",
  });
  const autoLegend = document.createElement("div");
  autoLegend.innerHTML = "<strong>AUTO</strong> : groupe géré automatiquement.";
  const manualLegend = document.createElement("div");
  manualLegend.innerHTML =
    "<strong>MANUAL</strong> : configuration entièrement manuelle.";
  const mixedLegend = document.createElement("div");
  mixedLegend.innerHTML =
    "<strong>MIXED</strong> : mélange de capteurs auto / manuels.";
  legend.appendChild(autoLegend);
  legend.appendChild(manualLegend);
  legend.appendChild(mixedLegend);

  container.appendChild(legend);
  container.appendChild(listContainer);

  // Chargement initial
  let state = getGroupsState();
  if (!state.groupsLoaded) {
    try {
      const groups = await getGroups();
      setGroupsState(groups);
      state = getGroupsState();
    } catch (e) {
      console.error("[customisation][groupsPanel] Erreur getGroups:", e);
      const err = createElement("p", { className: "hse-groups-error" });
      err.textContent = "Erreur lors du chargement des groupes.";
      container.appendChild(err);
      return;
    }
  }

  updateBulkSelects();
  renderGroupsList(listContainer, state.groups);
}
