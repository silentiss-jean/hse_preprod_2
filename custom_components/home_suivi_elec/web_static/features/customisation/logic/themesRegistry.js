// features/customisation/logic/themesRegistry.js
"use strict";

export const THEMES = [];

/**
 * Retourne un thème à partir d'un id (classe CSS) ou d'une key logique.
 */
export function getThemeById(idOrKey) {
  if (!idOrKey) return undefined;
  return THEMES.find((t) => t.id === idOrKey) || THEMES.find((t) => t.key === idOrKey);
}

/**
 * Thème par défaut (flag default:true ou premier de la liste).
 */
export function getDefaultTheme() {
  return THEMES.find((t) => t.default) || THEMES[0];
}

/* HSE_PHASE2_PATCH_START */
const THEME_STORAGE_KEY = "hse_theme_key";
const LEGACY_STORAGE_KEY = "hse_theme"; // si tu veux migrer l’ancien storage

async function loadThemeManifest() {
  const url = "features/customisation/logic/themes.manifest.json";
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Theme manifest not found: ${url} (${res.status})`);
  return res.json();
}

function setThemeOnDom(themeKey) {
  document.documentElement.dataset.theme = themeKey || "";
}

export function applyTheme(themeKey) {
  if (themeKey) {
    localStorage.setItem(THEME_STORAGE_KEY, themeKey);
  }
  setThemeOnDom(themeKey);
}

export async function initThemes() {
  const manifest = await loadThemeManifest();
  const themes = Array.isArray(manifest.themes) ? manifest.themes : [];

  THEMES.length = 0;
  themes.forEach((t) => THEMES.push(t));

  // Migration legacy: si hse_theme existe mais pas hse_theme_key, on copie
  let stored = null;
  try {
    stored = localStorage.getItem(THEME_STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
  } catch (e) {}

  const defaultTheme = themes.find((t) => t.default) || themes[0];
  const chosen = themes.find((t) => t.key === stored) || getThemeById(stored) || defaultTheme;

  if (chosen?.key) {
    applyTheme(chosen.key);
  }

  // Optionnel: on nettoie l’ancien storage
  try {
    if (localStorage.getItem(LEGACY_STORAGE_KEY)) localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch (e) {}
}
/* HSE_PHASE2_PATCH_END */
