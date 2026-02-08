"use strict";

import { createElement } from "../../../shared/utils/dom.js";
import { Button } from "../../../shared/components/Button.js";
import { Toast } from "../../../shared/components/Toast.js";

import {
  getGroupSets,
  saveGroupSets,
  refreshGroupTotals,
} from "../customisation.api.js";
import {
  getGroupSetsState,
  setGroupSetsState,
} from "../customisation.state.js";

function ensureSet(gs, setKey, defaultMode) {
  gs.sets ??= {};
  gs.sets[setKey] ??= { mode: defaultMode, groups: {} };
  gs.sets[setKey].groups ??= {};
}

function parseEntities(text) {
  return Array.from(
    new Set(
      (text || "")
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean)
    )
  );
}

// -----------------------------------------------------------------------------
// Compat: legacy group values vs new group object
// legacy: groups[groupName] = ["sensor.xxx", ...]
// new:    groups[groupName] = { name, mode, energy:[...], power:[...] }
// -----------------------------------------------------------------------------

function isNewGroupObject(v) {
  return v && typeof v === "object" && !Array.isArray(v);
}

function getEntitiesForTextarea(setKey, groupValue) {
  if (Array.isArray(groupValue)) return groupValue;

  if (isNewGroupObject(groupValue)) {
    const energy = Array.isArray(groupValue.energy) ? groupValue.energy : [];
    const power = Array.isArray(groupValue.power) ? groupValue.power : [];

    // UX choice: rooms -> energy, types -> power
    return setKey === "types" ? power : energy;
  }

  return [];
}

function setEntitiesFromTextarea(setKey, groups, groupName, ids) {
  const curVal = groups[groupName];

  // legacy / unset
  if (Array.isArray(curVal) || curVal == null) {
    groups[groupName] = ids;
    return;
  }

  // new
  if (isNewGroupObject(curVal)) {
    if (setKey === "types") curVal.power = ids;
    else curVal.energy = ids;
    groups[groupName] = curVal;
    return;
  }

  // fallback
  groups[groupName] = ids;
}

function makeNewGroupValue(setKey, name) {
  // Same canonical shape for both sets; editor chooses which list to edit.
  return {
    name,
    mode: "manual",
    energy: [],
    power: [],
  };
}

function renderSet(container, setKey, title) {
  const state = getGroupSetsState();
  const gs = state.groupSets || { sets: {}, version: 1 };

  const setDefaultMode = setKey === "rooms" ? "exclusive" : "multi";
  ensureSet(gs, setKey, setDefaultMode);

  const section = createElement("div", { className: "hse-group-sets-section" });

  const header = createElement("div", {
    className: "hse-groups-headerbar",
  });

  const h3 = document.createElement("h3");
  h3.textContent = title;

  const modeBadge = createElement("span", { className: "hse-groups-toolbar-info" });
  modeBadge.textContent = `mode: ${gs.sets[setKey].mode}`;

  const spacer = createElement("div", { className: "hse-groups-spacer" });

  const addBtn = Button.create(
    "+ Ajouter un groupe",
    () => {
      const name = window.prompt("Nom du groupe :");
      if (!name) return;
      const trimmed = name.trim();
      if (!trimmed) return;

      const cur = getGroupSetsState().groupSets || { sets: {}, version: 1 };
      ensureSet(cur, setKey, setDefaultMode);

      if (cur.sets[setKey].groups[trimmed]) {
        Toast.error("Un groupe avec ce nom existe déjà.");
        return;
      }

      cur.sets[setKey].groups[trimmed] = makeNewGroupValue(setKey, trimmed);
      setGroupSetsState(cur);
      renderGroupSetsPanel(container.parentElement); // rerender global
    },
    "secondary"
  );

  header.appendChild(h3);
  header.appendChild(spacer);
  header.appendChild(modeBadge);
  header.appendChild(addBtn);
  section.appendChild(header);

  const groups = gs.sets[setKey].groups || {};
  const keys = Object.keys(groups).sort((a, b) => a.localeCompare(b));

  if (keys.length === 0) {
    const empty = createElement("p", { className: "hse-group-empty" });
    empty.textContent = "Aucun groupe.";
    section.appendChild(empty);
    return section;
  }

  keys.forEach((groupName) => {
    const card = createElement("div", { className: "hse-group-card" });

    const cardHeader = createElement("div", { className: "hse-group-header" });
    const nameEl = createElement("div", { className: "hse-group-title" });
    const nameLabel = createElement("span", { className: "hse-group-name-label" });
    nameLabel.textContent = groupName;

    const listForCount = getEntitiesForTextarea(setKey, groups[groupName]);
    const count = createElement("span", { className: "hse-groups-toolbar-info" });
    count.textContent = `${listForCount.length} entité(s)`;

    const renameBtn = createElement("button", { type: "button", className: "hse-group-toggle", title: "Renommer" });
    renameBtn.textContent = "✏️";
    renameBtn.addEventListener("click", () => {
      const newName = window.prompt("Nouveau nom :", groupName);
      if (!newName) return;
      const trimmed = newName.trim();
      if (!trimmed || trimmed === groupName) return;

      const cur = getGroupSetsState().groupSets || { sets: {}, version: 1 };
      ensureSet(cur, setKey, setDefaultMode);

      if (cur.sets[setKey].groups[trimmed]) {
        Toast.error("Un groupe avec ce nom existe déjà.");
        return;
      }

      const val = cur.sets[setKey].groups[groupName];
      cur.sets[setKey].groups[trimmed] = val;

      if (isNewGroupObject(cur.sets[setKey].groups[trimmed])) {
        cur.sets[setKey].groups[trimmed].name = trimmed;
      }

      delete cur.sets[setKey].groups[groupName];
      setGroupSetsState(cur);
      renderGroupSetsPanel(container.parentElement);
    });

    const deleteBtn = createElement("button", { type: "button", className: "hse-group-toggle", title: "Supprimer" });
    deleteBtn.textContent = "🗑️";
    deleteBtn.addEventListener("click", () => {
      if (!window.confirm(`Supprimer le groupe "${groupName}" ?`)) return;

      const cur = getGroupSetsState().groupSets || { sets: {}, version: 1 };
      ensureSet(cur, setKey, setDefaultMode);
      delete cur.sets[setKey].groups[groupName];
      setGroupSetsState(cur);
      renderGroupSetsPanel(container.parentElement);
    });

    nameEl.appendChild(nameLabel);
    nameEl.appendChild(count);
    nameEl.appendChild(renameBtn);
    nameEl.appendChild(deleteBtn);

    cardHeader.appendChild(nameEl);
    card.appendChild(cardHeader);

    const body = createElement("div", { className: "hse-group-body" });

    const ta = createElement("textarea", {
      className: "hse-textarea",
      rows: "6",
      placeholder: "1 entity_id par ligne (ex: sensor.xxx)",
    });
    ta.value = getEntitiesForTextarea(setKey, groups[groupName]).join("\n");

    const applyBtn = Button.create(
      "Appliquer",
      () => {
        const ids = parseEntities(ta.value);

        const cur = getGroupSetsState().groupSets || { sets: {}, version: 1 };
        ensureSet(cur, setKey, setDefaultMode);

        // rooms exclusive: retirer des autres groupes avant d’assigner
        if (cur.sets[setKey].mode === "exclusive") {
          for (const g of Object.keys(cur.sets[setKey].groups)) {
            if (g === groupName) continue;

            const otherList = getEntitiesForTextarea(setKey, cur.sets[setKey].groups[g]);
            const cleaned = otherList.filter((e) => !ids.includes(e));
            setEntitiesFromTextarea(setKey, cur.sets[setKey].groups, g, cleaned);
          }
        }

        setEntitiesFromTextarea(setKey, cur.sets[setKey].groups, groupName, ids);
        setGroupSetsState(cur);
        Toast.success("Modifications appliquées (non enregistrées).");
        renderGroupSetsPanel(container.parentElement);
      },
      "secondary"
    );

    const actionsRow = createElement("div", { style: "margin-top:8px;" });
    actionsRow.appendChild(applyBtn);

    body.appendChild(ta);
    body.appendChild(actionsRow);

    card.appendChild(body);
    section.appendChild(card);
  });

  return section;
}

export async function renderGroupSetsPanel(container) {
  container.innerHTML = "";

  const header = createElement("div", { className: "hse-groups-headerbar" });

  const title = createElement("h3", { className: "hse-groups-title" });
  title.textContent = "Group set config";

  const spacer = createElement("div", { className: "hse-groups-spacer" });

  const refreshBtn = Button.create(
    "Rafraîchir",
    async () => {
      try {
        refreshBtn.disabled = true;
        const gs = await getGroupSets();
        setGroupSetsState(gs);
        renderGroupSetsPanel(container);
        Toast.success("Group sets rechargés.");
      } catch (e) {
        console.error("[customisation][groupSetsPanel] refresh error:", e);
        Toast.error("Erreur lors du chargement des group sets.");
      } finally {
        refreshBtn.disabled = false;
      }
    },
    "secondary"
  );

  const saveBtn = Button.create(
    "Enregistrer",
    async () => {
      try {
        saveBtn.disabled = true;
        const current = getGroupSetsState().groupSets || { sets: {}, version: 1 };
        await saveGroupSets(current);
        // re-canoniser après save
        const gs = await getGroupSets();
        setGroupSetsState(gs);
        renderGroupSetsPanel(container);
        Toast.success("Group sets enregistrés.");
      } catch (e) {
        console.error("[customisation][groupSetsPanel] save error:", e);
        Toast.error("Erreur lors de l'enregistrement des group sets.");
      } finally {
        saveBtn.disabled = false;
      }
    },
    "success"
  );

  const recomputeRoomsBtn = Button.create(
    "Recalculer rooms",
    async () => {
      try {
        recomputeRoomsBtn.disabled = true;
        await refreshGroupTotals("rooms");
        Toast.success("Totaux rooms recalculés.");
      } catch (e) {
        console.error("[customisation][groupSetsPanel] recompute rooms error:", e);
        Toast.error("Erreur lors du recalcul des totaux rooms.");
      } finally {
        recomputeRoomsBtn.disabled = false;
      }
    },
    "secondary"
  );

  const recomputeTypesBtn = Button.create(
    "Recalculer types",
    async () => {
      try {
        recomputeTypesBtn.disabled = true;
        await refreshGroupTotals("types");
        Toast.success("Totaux types recalculés.");
      } catch (e) {
        console.error("[customisation][groupSetsPanel] recompute types error:", e);
        Toast.error("Erreur lors du recalcul des totaux types.");
      } finally {
        recomputeTypesBtn.disabled = false;
      }
    },
    "secondary"
  );

  header.appendChild(title);
  header.appendChild(spacer);
  header.appendChild(refreshBtn);
  header.appendChild(saveBtn);
  header.appendChild(recomputeRoomsBtn);
  header.appendChild(recomputeTypesBtn);
  container.appendChild(header);

  // Load initial if needed
  const state = getGroupSetsState();
  if (!state.groupSetsLoaded) {
    try {
      const gs = await getGroupSets();
      setGroupSetsState(gs);
    } catch (e) {
      console.error("[customisation][groupSetsPanel] initial load error:", e);
      const err = createElement("p", { className: "hse-groups-error" });
      err.textContent = "Erreur lors du chargement des group sets.";
      container.appendChild(err);
      return;
    }
  }

  const content = createElement("div");
  const rooms = renderSet(content, "rooms", "Rooms (exclusive)");
  const types = renderSet(content, "types", "Types (multi)");
  container.appendChild(rooms);
  container.appendChild(types);
}
