// features/customisation/customisation.state.js
"use strict";

import { getThemeById, getDefaultTheme, THEMES, applyTheme as applyThemeRegistry } from "./logic/themesRegistry.js"; // applyTheme = write storage + set data-theme [file:168]

const STORAGE_KEY = "hse_theme";
let currentTheme = null;

let groups = {};
let groupsLoaded = false;

export function getGroupsState() {
  return { groups, groupsLoaded };
}
export function setGroupsState(newGroups) {
  groups = newGroups || {};
  groupsLoaded = true;
}
export function renameGroupInState(oldName, newName) {
  if (!groups[oldName] || oldName === newName) return;
  groups[newName] = { ...groups[oldName], name: newName };
  delete groups[oldName];
}
export function setGroupModeInState(name, mode) {
  if (!groups[name]) return;
  groups[name] = { ...groups[name], mode };
}

// --- GROUP SETS STATE ---

let groupSets = null;          // { sets: {...}, version: 1 }
let groupSetsLoaded = false;

export function getGroupSetsState() {
  return { groupSets, groupSetsLoaded };
}

export function setGroupSetsState(newGroupSets) {
  groupSets = newGroupSets || { sets: {}, version: 1 };
  groupSetsLoaded = true;
}

function ensureSet(setKey) {
  groupSets ??= { sets: {}, version: 1 };
  groupSets.sets ??= {};
  groupSets.sets[setKey] ??= { mode: "multi", groups: {} };
  groupSets.sets[setKey].groups ??= {};
}

export function addGroupInSet(setKey, groupName) {
  ensureSet(setKey);
  groupSets.sets[setKey].groups[groupName] ??= [];
}

export function renameGroupInSet(setKey, oldName, newName) {
  ensureSet(setKey);
  const groups = groupSets.sets[setKey].groups;
  if (!(oldName in groups) || oldName === newName) return;
  if (newName in groups) throw new Error("Group already exists");
  groups[newName] = groups[oldName];
  delete groups[oldName];
}

export function deleteGroupInSet(setKey, groupName) {
  ensureSet(setKey);
  delete groupSets.sets[setKey].groups[groupName];
}

export function setSetModeInState(setKey, mode) {
  ensureSet(setKey);
  groupSets.sets[setKey].mode = mode;
}

export function setGroupEntitiesInSet(setKey, groupName, entityIds) {
  ensureSet(setKey);
  const uniq = Array.from(new Set((entityIds || []).filter(Boolean)));
  groupSets.sets[setKey].groups[groupName] = uniq;
}

// Important: pour rooms exclusive uniquement
export function assignEntityInSet(setKey, groupName, entityId) {
  ensureSet(setKey);

  const set = groupSets.sets[setKey];
  const groupsObj = set.groups;

  if (set.mode === "exclusive") {
    for (const g of Object.keys(groupsObj)) {
      groupsObj[g] = (groupsObj[g] || []).filter((e) => e !== entityId);
    }
  }

  groupsObj[groupName] ??= [];
  if (!groupsObj[groupName].includes(entityId)) groupsObj[groupName].push(entityId);
}


// --- THEME STATE (single source of truth = themesRegistry) ---


function resolveThemeKey(idOrKey) {
  const theme = getThemeById(idOrKey) || getDefaultTheme() || THEMES[0];
  return theme?.key || "dark"; // dark est default:true dans le manifest [file:168]
}

export function getCurrentTheme() {
  if (currentTheme) return currentTheme;

  // Ne lit plus "hse_theme": le registry lit déjà "hse_theme_key" dans initThemes() [file:168]
  const fallback = resolveThemeKey(null);
  currentTheme = fallback;
  return currentTheme;
}

export function setCurrentTheme(idOrKey) {
  const key = resolveThemeKey(idOrKey);
  currentTheme = key;

  // Délègue au registry: persiste dans hse_theme_key + applique html[data-theme] [file:168]
  applyThemeRegistry(key);

  return key;
}
