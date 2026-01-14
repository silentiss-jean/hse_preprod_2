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
