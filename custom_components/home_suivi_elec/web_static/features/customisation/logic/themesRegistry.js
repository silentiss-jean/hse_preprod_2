// features/customisation/logic/themesRegistry.js
"use strict";

export const THEMES = [
  { id: "hse_light",   key: "light",   label: "Light (clair moderne)",      default: false },
  { id: "hse_dark",    key: "dark",    label: "Dark (sombre élégant)",      default: true  },
  { id: "hse_ocean",   key: "ocean",   label: "Ocean (bleu profond)",       default: false },
  { id: "hse_forest",  key: "forest",  label: "Forest (vert nature)",       default: false },
  { id: "hse_sunset",  key: "sunset",  label: "Sunset (coucher de soleil)", default: false },
  { id: "hse_minimal", key: "minimal", label: "Minimal (noir & blanc)",     default: false },
  { id: "hse_neon",    key: "neon",    label: "Neon (cyberpunk)",           default: false },
];

/**
 * Retourne un thème à partir d'un id (classe CSS) ou d'une key logique.
 * Accepte 'hse_dark' OU 'dark'.
 */
export function getThemeById(idOrKey) {
  if (!idOrKey) return undefined;
  return (
    THEMES.find((t) => t.id === idOrKey) ||
    THEMES.find((t) => t.key === idOrKey)
  );
}

/**
 * Thème par défaut (flag default:true ou premier de la liste).
 */
export function getDefaultTheme() {
  return THEMES.find((t) => t.default) || THEMES[0];
}
