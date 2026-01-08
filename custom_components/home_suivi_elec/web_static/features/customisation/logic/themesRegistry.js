// features/customisation/logic/themesRegistry.js
"use strict";

/**
 * Registry des thèmes disponibles
 * Correspond aux thèmes définis dans style.hse.themes.css
 */

export const THEMES = [
  { 
    id: "hse_light", 
    key: "light", 
    label: "Light (clair moderne)", 
    description: "Thème clair épuré avec ombres douces",
    icon: "☀️",
    default: true 
  },
  { 
    id: "hse_dark", 
    key: "dark", 
    label: "Dark (sombre élégant)", 
    description: "Thème sombre avec effets de lueur",
    icon: "🌙",
    default: false 
  },
  { 
    id: "hse_glass", 
    key: "glass", 
    label: "Glassmorphism (verre givré)", 
    description: "Transparence et flou d'arrière-plan",
    icon: "💎",
    default: false 
  },
  { 
    id: "hse_neuro", 
    key: "neuro", 
    label: "Neumorphism (relief 3D)", 
    description: "Ombres internes et effet de profondeur",
    icon: "🎨",
    default: false 
  },
  { 
    id: "hse_cyberpunk", 
    key: "cyberpunk", 
    label: "Cyberpunk (futuriste néon)", 
    description: "Néons magenta/cyan avec effets glitch",
    icon: "⚡",
    default: false 
  },
  { 
    id: "hse_aurora", 
    key: "aurora", 
    label: "Aurora Borealis (aurore boréale)", 
    description: "Dégradés animés multicolores",
    icon: "🌌",
    default: false 
  }
];

/**
 * Retourne un thème à partir d'un id (classe CSS) ou d'une key logique.
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
