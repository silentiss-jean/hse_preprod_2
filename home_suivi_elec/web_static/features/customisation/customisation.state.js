// features/customisation/customisation.state.js
"use strict";

import { getThemeById, getDefaultTheme } from "./logic/themesRegistry.js";

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
function safeResolveTheme(idOrKey) {
  const theme = getThemeById(idOrKey) || getDefaultTheme();
  return theme.id; // toujours retourner l'id (classe CSS) ex: "hse_dark"
}

export function getCurrentTheme() {
  if (currentTheme) {
    return currentTheme;
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      currentTheme = safeResolveTheme(stored);
      return currentTheme;
    }
  } catch (e) {
    // Ignorer erreurs localStorage
  }

  // Fallback: thème par défaut
  currentTheme = getDefaultTheme().id;
  return currentTheme;
}

export function setCurrentTheme(idOrKey) {
  const themeId = safeResolveTheme(idOrKey);
  currentTheme = themeId;
  try {
    window.localStorage.setItem(STORAGE_KEY, themeId);
  } catch (e) {
    // Ignorer erreurs localStorage
  }
  return themeId;
}
