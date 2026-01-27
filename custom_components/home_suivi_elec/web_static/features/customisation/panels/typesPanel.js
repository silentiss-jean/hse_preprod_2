"use strict";

/*
 * Types panel (Customisation)
 *
 * - Basé sur le design/UX de groupsPanel.js
 * - Stockage cible : group_sets.sets.types.groups
 * - Source pool V1 : rooms (getGroups) => on type ce qui est déjà organisé en pièces
 */

import { createElement } from "../../../shared/utils/dom.js";
import { Button } from "../../../shared/components/Button.js";
import { Toast } from "../../../shared/components/Toast.js";

import { getGroups, getGroupSets, saveGroupSets } from "../customisation.api.js";
import { getGroupsState, setGroupsState, getGroupSetsState, setGroupSetsState } from "../customisation.state.js";

// État UI local
const collapsedByType = new Map();
const collapsedFamilies = new Map();
let globalFilter = "";
let sortAsc = true;
let showFacture = false;

let bulkScopeSelect = null;
let bulkTargetSelect = null;

// ---------------------------------------------------------------------------
// Utils (copiés/adaptés de groupsPanel.js pour rester cohérent)
// ---------------------------------------------------------------------------

function keyForFamilyCollapse(typeKey, kind, familyKey) {
  return `${typeKey}:${kind}:${familyKey}`;
}

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

function uniq(list) {
  return Array.from(new Set((list || []).filter(Boolean)));
}

function ensureTypeSet(gs) {
  gs.sets ??= {};
  gs.sets.types ??= { mode: "multi", groups: {} };
  gs.sets.types.groups ??= {};
  return gs;
}

function normalizeTypeGroupValue(typeKey, value) {
  // legacy: groups[type] = ["sensor.xxx", ...] => assume power
  if (Array.isArray(value)) {
    return {
      name: typeKey,
      mode: "manual",
      power: uniq(value),
      energy: [],
    };
  }

  if (value && typeof value === "object") {
    return {
      name: value.name || typeKey,
      mode: value.mode || "manual",
      power: uniq(value.power || []),
      energy: uniq(value.energy || []),
    };
  }

  return { name: typeKey, mode: "manual", power: [], energy: [] };
}

function getTypesStateSnapshot() {
  const st = getGroupSetsState();
  const gs = ensureTypeSet(JSON.parse(JSON.stringify(st.groupSets || { sets: {}, version: 1 })));

  // Canoniser les valeurs
  const groups = gs.sets.types.groups || {};
  for (const k of Object.keys(groups)) {
    groups[k] = normalizeTypeGroupValue(k, groups[k]);
  }

  return gs;
}

function setTypesState(gs) {
  setGroupSetsState(gs);
}

function getTypeKeys(gs) {
  const groups = gs?.sets?.types?.groups || {};
  return Object.keys(groups).sort((a, b) => a.localeCompare(b));
}

// ---------------------------------------------------------------------------
// Auto types + auto energy link (depuis rooms)
// ---------------------------------------------------------------------------

const DEFAULT_TYPE_KEYWORDS = {
  tv: "TV",
  tele: "TV",
  television: "TV",
  chromecast: "TV",
  apple_tv: "TV",
  shield: "TV",

  internet: "Internet",
  box: "Internet",
  routeur: "Internet",
  router: "Internet",
  switch: "Internet",
  wifi: "Internet",

  nas: "Informatique",
  pc: "Informatique",
  ordi: "Informatique",
  computer: "Informatique",
  server: "Informatique",
  serveur: "Informatique",

  chauffage: "Chauffage",
  radiateur: "Chauffage",
  clim: "Chauffage",
  pac: "Chauffage",

  ecs: "Eau chaude",
  ballon: "Eau chaude",
  chauffe_eau: "Eau chaude",
};

function buildEnergyIndexFromRooms(rooms) {
  const energyByBase = new Map();

  Object.values(rooms || {}).forEach((room) => {
    const energy = room?.energy || [];
    energy.forEach((eid) => {
      const base = familyBase(eid, "energy");
      if (!energyByBase.has(base)) energyByBase.set(base, []);
      energyByBase.get(base).push(eid);
    });
  });

  // Dédupe
  for (const [k, v] of energyByBase.entries()) {
    energyByBase.set(k, uniq(v));
  }

  return energyByBase;
}

function linkEnergyForPower(powerEntityId, energyByBase) {
  const base = familyBase(powerEntityId, "power");
  const candidates = energyByBase.get(base) || [];
  if (!candidates || candidates.length === 0) return null;
  return pickParent("energy", candidates);
}

function applyAutoTypesFromRooms(gs, rooms, typeKeywords) {
  const keywords = typeKeywords || DEFAULT_TYPE_KEYWORDS;
  const energyByBase = buildEnergyIndexFromRooms(rooms);

  const typesGroups = gs.sets.types.groups;

  let typedCount = 0;
  let linkedEnergyCount = 0;

  Object.values(rooms || {}).forEach((room) => {
    const power = room?.power || [];

    power.forEach((eid) => {
      const s = String(eid).toLowerCase();

      let targetType = null;
      for (const [kw, typeName] of Object.entries(keywords)) {
        if (s.includes(String(kw).toLowerCase())) {
          targetType = typeName;
          break;
        }
      }
      if (!targetType) return;

      const key = targetType;
      typesGroups[key] = normalizeTypeGroupValue(key, typesGroups[key]);
      typesGroups[key].mode = "auto";

      if (!typesGroups[key].power.includes(eid)) {
        typesGroups[key].power.push(eid);
        typedCount += 1;
      }

      // Auto-link energy
      const energyId = linkEnergyForPower(eid, energyByBase);
      if (energyId && !typesGroups[key].energy.includes(energyId)) {
        typesGroups[key].energy.push(energyId);
        linkedEnergyCount += 1;
      }
    });
  });

  // Dédupe final
  for (const k of Object.keys(typesGroups)) {
    typesGroups[k] = normalizeTypeGroupValue(k, typesGroups[k]);
  }

  return { gs, typedCount, linkedEnergyCount };
}

// ---------------------------------------------------------------------------
// Bulk actions (copy/move) à l'intérieur des types
// ---------------------------------------------------------------------------

function updateBulkSelects(gs) {
  const typeKeys = getTypeKeys(gs);

  if (!bulkScopeSelect || !bulkTargetSelect) return;

  // Scope
  bulkScopeSelect.innerHTML = "";
  const allOpt = document.createElement("option");
  allOpt.value = "all";
  allOpt.textContent = "Tous les types";
  bulkScopeSelect.appendChild(allOpt);

  typeKeys.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = k;
    bulkScopeSelect.appendChild(opt);
  });

  // Target
  bulkTargetSelect.innerHTML = "";
  typeKeys.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = k;
    bulkTargetSelect.appendChild(opt);
  });
  const newOpt = document.createElement("option");
  newOpt.value = "__new__";
  newOpt.textContent = "+ Nouveau type…";
  bulkTargetSelect.appendChild(newOpt);
}

function ensureType(gs, typeKey) {
  const groups = gs.sets.types.groups;
  groups[typeKey] = normalizeTypeGroupValue(typeKey, groups[typeKey]);
  return groups[typeKey];
}

function removeEntityFromType(typeCfg, entityId, kind) {
  if (!typeCfg) return;
  const list = kind === "energy" ? typeCfg.energy : typeCfg.power;
  const idx = list.indexOf(entityId);
  if (idx >= 0) list.splice(idx, 1);
}

function addEntityToType(typeCfg, entityId, kind) {
  if (!typeCfg) return;
  const list = kind === "energy" ? typeCfg.energy : typeCfg.power;
  if (!list.includes(entityId)) list.push(entityId);
}

function performKeywordBulk(gs, keyword, action, targetKey, scope) {
  const q = String(keyword || "").trim().toLowerCase();
  if (!q) return { gs, moved: 0, copied: 0 };

  const groups = gs.sets.types.groups;
  const keys = scope === "all" ? Object.keys(groups) : [scope];

  const target = ensureType(gs, targetKey);

  let moved = 0;
  let copied = 0;

  keys.forEach((k) => {
    if (!groups[k]) return;
    const cfg = ensureType(gs, k);

    // power
    const powerMatches = (cfg.power || []).filter((eid) => String(eid).toLowerCase().includes(q));
    powerMatches.forEach((eid) => {
      addEntityToType(target, eid, "power");
      if (action === "move" && k !== targetKey) {
        removeEntityFromType(cfg, eid, "power");
        moved += 1;
      } else {
        copied += 1;
      }
    });

    // energy
    const energyMatches = (cfg.energy || []).filter((eid) => String(eid).toLowerCase().includes(q));
    energyMatches.forEach((eid) => {
      addEntityToType(target, eid, "energy");
      if (action === "move" && k !== targetKey) {
        removeEntityFromType(cfg, eid, "energy");
        moved += 1;
      } else {
        copied += 1;
      }
    });
  });

  // Canon
  for (const k of Object.keys(groups)) {
    groups[k] = normalizeTypeGroupValue(k, groups[k]);
  }

  return { gs, moved, copied };
}

// ---------------------------------------------------------------------------
// Modal assign (copy/move) pour une famille ou un capteur
// ---------------------------------------------------------------------------

function openAssignModal(listContainer, fromTypeKey, entityIds, kind) {
  const gs = getTypesStateSnapshot();
  const groups = gs.sets.types.groups;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const modal = document.createElement("div");
  modal.className = "modal-content modal-small";

  const header = createElement("div", { className: "modal-header" });
  const h2 = document.createElement("h2");
  h2.textContent = "Affecter des capteurs";

  const closeBtn = createElement("button", {
    type: "button",
    className: "modal-close-btn",
  });
  closeBtn.innerHTML = "×";
  closeBtn.addEventListener("click", () => document.body.removeChild(overlay));

  header.appendChild(h2);
  header.appendChild(closeBtn);

  const body = createElement("div", { className: "modal-body" });

  const info = document.createElement("p");
  const idsArray = Array.isArray(entityIds) ? entityIds : [entityIds];
  info.textContent = idsArray.length > 1
    ? `Affecter ${idsArray.length} capteurs (${kind}) vers :`
    : `Affecter ${idsArray[0]} (${kind}) vers :`;
  body.appendChild(info);

  const actionSelect = createElement("select", { className: "hse-select hse-modal-select" });
  const optCopy = createElement("option", { value: "copy" });
  optCopy.textContent = "Copier";
  const optMove = createElement("option", { value: "move" });
  optMove.textContent = "Déplacer";
  actionSelect.appendChild(optCopy);
  actionSelect.appendChild(optMove);
  body.appendChild(actionSelect);

  const select = createElement("select", { className: "hse-select hse-modal-select" });
  const keys = Object.keys(groups).sort((a, b) => a.localeCompare(b));
  keys.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = k;
    if (k === fromTypeKey) opt.selected = true;
    select.appendChild(opt);
  });
  body.appendChild(select);

  const orText = document.createElement("p");
  orText.className = "hse-modal-or";
  orText.textContent = "Ou créer un nouveau type :";
  body.appendChild(orText);

  const newInput = createElement("input", {
    type: "text",
    className: "hse-group-name-input hse-modal-new-input",
    placeholder: "Nom du nouveau type",
  });
  body.appendChild(newInput);

  const footer = createElement("div", { className: "modal-footer" });

  const cancelBtn = Button.create(
    "Annuler",
    () => document.body.removeChild(overlay),
    "secondary"
  );

  const confirmBtn = Button.create(
    "Valider",
    () => {
      let targetKey = newInput.value.trim();
      if (!targetKey) targetKey = select.value;
      if (!targetKey) return;

      const cur = getTypesStateSnapshot();
      const tgt = ensureType(cur, targetKey);
      const from = ensureType(cur, fromTypeKey);

      const action = actionSelect.value;
      idsArray.forEach((eid) => {
        addEntityToType(tgt, eid, kind);
        if (action === "move" && fromTypeKey !== targetKey) {
          removeEntityFromType(from, eid, kind);
        }
      });

      // Canon
      for (const k of Object.keys(cur.sets.types.groups)) {
        cur.sets.types.groups[k] = normalizeTypeGroupValue(k, cur.sets.types.groups[k]);
      }

      setTypesState(cur);
      renderTypesList(listContainer, getTypesStateSnapshot());
      document.body.removeChild(overlay);

      Toast.success(`${idsArray.length} capteur(s) ${action === "move" ? "déplacé(s)" : "copié(s)"} vers "${targetKey}".`);
    },
    "primary"
  );

  footer.appendChild(cancelBtn);
  footer.appendChild(confirmBtn);

  modal.appendChild(header);
  modal.appendChild(body);
  modal.appendChild(footer);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderFamilyRow(listContainer, typeKey, kind, family) {
  const famKey = family.key || family.parent || (family.all[0] || "");
  const collapseKey = keyForFamilyCollapse(typeKey, kind, famKey);
  const isCollapsed = collapsedFamilies.get(collapseKey) === true;

  const wrapper = createElement("div", { style: "margin-bottom:6px;" });

  const parentRow = createElement("div", {
    className: "hse-group-sensor-item is-clickable",
    title: "Cliquer pour copier/déplacer toute cette famille de capteurs",
    style: "font-weight:600; display:flex; align-items:center; gap:6px;",
  });

  const caret = createElement("span", {
    style: "display:inline-block; width:16px; color:var(--hse-text-muted); cursor:pointer;",
  });
  caret.textContent = isCollapsed ? "▶" : "▼";
  caret.addEventListener("click", (e) => {
    e.stopPropagation();
    const cur = collapsedFamilies.get(collapseKey) === true;
    collapsedFamilies.set(collapseKey, !cur);
    renderTypesList(listContainer, getTypesStateSnapshot());
  });

  const label = createElement("span", { style: "flex:1;" });
  label.textContent = family.parent || family.all[0];

  parentRow.appendChild(caret);
  parentRow.appendChild(label);

  parentRow.addEventListener("click", () => {
    openAssignModal(listContainer, typeKey, family.all, kind);
  });

  wrapper.appendChild(parentRow);

  if (!isCollapsed && family.children.length > 0) {
    const childrenBox = createElement("div", {
      style: "margin-left:22px; border-left:1px dashed var(--hse-border); padding-left:8px;",
    });

    family.children.forEach((eid) => {
      const row = createElement("div", {
        className: "hse-group-sensor-item is-clickable",
        title: "Cliquer pour copier/déplacer ce capteur seul",
      });
      row.textContent = eid;
      row.addEventListener("click", () => {
        openAssignModal(listContainer, typeKey, [eid], kind);
      });
      childrenBox.appendChild(row);
    });

    wrapper.appendChild(childrenBox);
  }

  return wrapper;
}

function renderSensorColumn(listContainer, typeKey, title, kind, sensors) {
  const col = createElement("div", { className: "hse-group-column" });

  const titleEl = createElement("div", { className: "hse-group-column-title" });
  titleEl.textContent = title;
  col.appendChild(titleEl);

  let filtered = sensors || [];
  if (globalFilter) {
    const q = globalFilter.toLowerCase();
    filtered = filtered.filter((s) => String(s).toLowerCase().includes(q));
  }

  const families = buildFamilies(filtered, kind);
  const list = createElement("div", { className: "hse-group-sensor-list" });

  if (families.length === 0) {
    const empty = createElement("div", { className: "hse-group-empty" });
    empty.textContent = `Aucun ${kind}.`;
    list.appendChild(empty);
  } else {
    families.forEach((fam) => {
      list.appendChild(renderFamilyRow(listContainer, typeKey, kind, fam));
    });
  }

  col.appendChild(list);
  return col;
}

function renderTypesList(listContainer, gs) {
  listContainer.innerHTML = "";

  const typesGroups = gs?.sets?.types?.groups || {};
  const entries = Object.entries(typesGroups);

  if (entries.length === 0) {
    const empty = createElement("p", { className: "hse-group-empty" });
    empty.textContent = "Aucun type défini pour le moment.";
    listContainer.appendChild(empty);
    return;
  }

  if (!listContainer.classList.contains("hse-groups-container")) {
    listContainer.classList.add("hse-groups-container");
  }

  // Sort by key
  entries.sort((a, b) => (sortAsc ? a[0].localeCompare(b[0]) : b[0].localeCompare(a[0])));

  entries.forEach(([key, cfgRaw]) => {
    const cfg = normalizeTypeGroupValue(key, cfgRaw);

    const power = cfg.power || [];
    const energy = cfg.energy || [];

    const card = createElement("div", { className: "hse-group-card" });

    const header = createElement("div", { className: "hse-group-header" });
    const isCollapsed = collapsedByType.get(key) === true;

    const toggleBtn = createElement("button", {
      type: "button",
      className: "hse-group-toggle",
    });
    toggleBtn.textContent = isCollapsed ? "▶" : "▼";
    toggleBtn.addEventListener("click", () => {
      const cur = collapsedByType.get(key) === true;
      collapsedByType.set(key, !cur);
      renderTypesList(listContainer, getTypesStateSnapshot());
    });

    const titleWrapper = createElement("div", { className: "hse-group-title" });

    const iconSpan = createElement("span", { className: "hse-group-icon" });
    iconSpan.textContent = "🏷️";

    const nameLabel = createElement("span", { className: "hse-group-name-label" });
    nameLabel.textContent = cfg.name || key;

    const counts = createElement("span", { className: "hse-groups-toolbar-info" });
    counts.textContent = `${energy.length} energy / ${power.length} power`;

    const deleteBtn = createElement("button", {
      type: "button",
      className: "hse-group-toggle",
      title: "Supprimer ce type",
    });
    deleteBtn.textContent = "🗑️";
    deleteBtn.addEventListener("click", () => {
      if (!window.confirm(`Supprimer le type "${key}" ?`)) return;

      const cur = getTypesStateSnapshot();
      delete cur.sets.types.groups[key];
      setTypesState(cur);

      collapsedByType.delete(key);
      [...collapsedFamilies.keys()].forEach((famK) => {
        if (famK.startsWith(`${key}:`)) collapsedFamilies.delete(famK);
      });

      renderTypesList(listContainer, getTypesStateSnapshot());
      Toast.success(`Type "${key}" supprimé.`);
    });

    titleWrapper.appendChild(iconSpan);
    titleWrapper.appendChild(nameLabel);
    titleWrapper.appendChild(counts);

    header.appendChild(toggleBtn);
    header.appendChild(titleWrapper);
    header.appendChild(deleteBtn);

    card.appendChild(header);

    const body = createElement("div", { className: "hse-group-body" });
    if (isCollapsed) body.style.display = "none";

    const powerCol = renderSensorColumn(listContainer, key, "Capteurs power", "power", power);
    body.appendChild(powerCol);

    if (showFacture) {
      const energyCol = renderSensorColumn(listContainer, key, "Capteurs energy (facture)", "energy", energy);
      body.appendChild(energyCol);
    } else {
      // placeholder: garder le layout stable en 2 colonnes si souhaité plus tard
    }

    card.appendChild(body);
    listContainer.appendChild(card);
  });
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export async function renderTypesPanel(container) {
  if (!container) return;
  container.innerHTML = "";

  const listContainer = createElement("div");
  listContainer.classList.add("hse-groups-container");

  const header = createElement("div", { className: "hse-groups-headerbar" });

  const title = createElement("h3", { className: "hse-groups-title" });
  title.textContent = "Types (catégories)";

  const spacer = createElement("div", { className: "hse-groups-spacer" });

  const filterInput = createElement("input", {
    type: "text",
    placeholder: "Filtrer les capteurs…",
    className: "hse-group-name-input hse-groups-filter",
  });
  filterInput.addEventListener("input", () => {
    globalFilter = filterInput.value || "";
    renderTypesList(listContainer, getTypesStateSnapshot());
  });

  const sortBtn = Button.create(
    sortAsc ? "Tri A→Z" : "Tri Z→A",
    () => {
      sortAsc = !sortAsc;
      sortBtn.textContent = sortAsc ? "Tri A→Z" : "Tri Z→A";
      renderTypesList(listContainer, getTypesStateSnapshot());
    },
    "secondary"
  );

  const toggleFactureBtn = Button.create(
    showFacture ? "Facture: ON" : "Facture: OFF",
    () => {
      showFacture = !showFacture;
      toggleFactureBtn.textContent = showFacture ? "Facture: ON" : "Facture: OFF";
      renderTypesList(listContainer, getTypesStateSnapshot());
    },
    "secondary"
  );

  const refreshBtn = Button.create(
    "Rafraîchir",
    async () => {
      try {
        refreshBtn.disabled = true;
        const [rooms, gs] = await Promise.all([getGroups(), getGroupSets()]);
        setGroupsState(rooms);
        setGroupSetsState(gs);

        const snapshot = getTypesStateSnapshot();
        updateBulkSelects(snapshot);
        renderTypesList(listContainer, snapshot);

        Toast.success("Types rechargés.");
      } catch (e) {
        console.error("[customisation][typesPanel] refresh error:", e);
        Toast.error("Erreur lors du rafraîchissement.");
      } finally {
        refreshBtn.disabled = false;
      }
    },
    "secondary"
  );

  const addTypeBtn = Button.create(
    "+ Ajouter un type",
    () => {
      const name = window.prompt("Nom du nouveau type :");
      if (!name) return;
      const trimmed = name.trim();
      if (!trimmed) return;

      const cur = getTypesStateSnapshot();
      if (cur.sets.types.groups[trimmed]) {
        Toast.error("Un type avec ce nom existe déjà.");
        return;
      }
      cur.sets.types.groups[trimmed] = { name: trimmed, mode: "manual", power: [], energy: [] };
      setTypesState(cur);

      collapsedByType.set(trimmed, false);
      updateBulkSelects(cur);
      renderTypesList(listContainer, cur);
    },
    "secondary"
  );

  const autoBtn = Button.create(
    "Auto types (depuis pièces)",
    async () => {
      try {
        autoBtn.disabled = true;

        // Assure rooms+group_sets en mémoire
        let roomsState = getGroupsState();
        let gsState = getGroupSetsState();

        if (!roomsState.groupsLoaded || !gsState.groupSetsLoaded) {
          const [rooms, gs] = await Promise.all([getGroups(), getGroupSets()]);
          setGroupsState(rooms);
          setGroupSetsState(gs);
          roomsState = getGroupsState();
          gsState = getGroupSetsState();
        }

        const gs = getTypesStateSnapshot();
        const { gs: updated, typedCount, linkedEnergyCount } = applyAutoTypesFromRooms(
          gs,
          roomsState.groups,
          DEFAULT_TYPE_KEYWORDS
        );

        setTypesState(updated);
        updateBulkSelects(updated);
        renderTypesList(listContainer, updated);

        Toast.success(`Auto types: ${typedCount} power affectés, ${linkedEnergyCount} energy liés.`);
      } catch (e) {
        console.error("[customisation][typesPanel] auto types error:", e);
        Toast.error("Erreur lors de la génération automatique des types.");
      } finally {
        autoBtn.disabled = false;
      }
    },
    "primary"
  );

  const saveBtn = Button.create(
    "Enregistrer les types",
    async () => {
      try {
        saveBtn.disabled = true;
        const current = getTypesStateSnapshot();
        await saveGroupSets(current);
        const gs = await getGroupSets();
        setGroupSetsState(gs);

        const snapshot = getTypesStateSnapshot();
        updateBulkSelects(snapshot);
        renderTypesList(listContainer, snapshot);

        Toast.success("Types enregistrés (group_sets).");
      } catch (e) {
        console.error("[customisation][typesPanel] save error:", e);
        Toast.error("Erreur lors de l'enregistrement.");
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
  header.appendChild(toggleFactureBtn);
  header.appendChild(addTypeBtn);
  header.appendChild(refreshBtn);
  header.appendChild(autoBtn);
  header.appendChild(saveBtn);

  container.appendChild(header);

  // Bulk bar
  const bulkBar = createElement("div", { className: "hse-groups-bulkbar" });

  const bulkLabel = createElement("span", { className: "hse-groups-bulk-label" });
  bulkLabel.textContent = "Action de masse :";

  const actionSelect = createElement("select", {
    className: "hse-select hse-groups-select hse-groups-scope",
    title: "Copier ou déplacer",
  });
  const optCopy = createElement("option", { value: "copy" });
  optCopy.textContent = "Copier";
  const optMove = createElement("option", { value: "move" });
  optMove.textContent = "Déplacer";
  actionSelect.appendChild(optCopy);
  actionSelect.appendChild(optMove);

  const keywordInput = createElement("input", {
    type: "text",
    placeholder: "Mot-clé (ex: tv)…",
    className: "hse-group-name-input hse-groups-keyword",
  });

  const scopeSelect = createElement("select", {
    className: "hse-select hse-groups-select hse-groups-scope",
  });
  const targetSelect = createElement("select", {
    className: "hse-select hse-groups-select hse-groups-target",
  });

  bulkScopeSelect = scopeSelect;
  bulkTargetSelect = targetSelect;

  const bulkBtn = Button.create(
    "Appliquer",
    () => {
      const kw = keywordInput.value.trim();
      if (!kw) {
        Toast.error("Veuillez saisir un mot-clé.");
        return;
      }

      let targetKey = targetSelect.value;
      if (targetKey === "__new__") {
        const newName = window.prompt("Nom du nouveau type :");
        if (!newName) return;
        targetKey = newName.trim();
        if (!targetKey) return;
      }

      const scope = scopeSelect.value;
      const action = actionSelect.value;

      const cur = getTypesStateSnapshot();
      // S'assure que la cible existe
      ensureType(cur, targetKey);

      const { gs: updated, moved, copied } = performKeywordBulk(cur, kw, action, targetKey, scope);
      setTypesState(updated);
      updateBulkSelects(updated);
      renderTypesList(listContainer, updated);

      Toast.success(`Bulk: ${moved} déplacé(s), ${copied} copié(s) vers "${targetKey}".`);
    },
    "primary"
  );

  bulkBar.appendChild(bulkLabel);
  bulkBar.appendChild(actionSelect);
  bulkBar.appendChild(keywordInput);
  bulkBar.appendChild(scopeSelect);
  bulkBar.appendChild(targetSelect);
  bulkBar.appendChild(bulkBtn);

  container.appendChild(bulkBar);
  container.appendChild(listContainer);

  // Load initial
  try {
    const gsState = getGroupSetsState();
    if (!gsState.groupSetsLoaded) {
      const gs = await getGroupSets();
      setGroupSetsState(gs);
    }
    const snapshot = getTypesStateSnapshot();
    updateBulkSelects(snapshot);
    renderTypesList(listContainer, snapshot);
  } catch (e) {
    console.error("[customisation][typesPanel] initial load error:", e);
    const err = createElement("p", { className: "hse-groups-error" });
    err.textContent = "Erreur lors du chargement des types.";
    container.appendChild(err);
  }
}
