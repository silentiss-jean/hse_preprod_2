/* theme-bridge.js
 * Objectif: appliquer un thème via html[data-theme="..."] le plus tôt possible.
 * - Lit localStorage (clé v2: hse_theme_key) + fallback legacy
 * - Lit body.className (anciennes classes) si besoin
 * - Pose documentElement.dataset.theme / setAttribute("data-theme", ...)
 * - Optionnel: purge certaines classes legacy qui perturbent l'affichage
 */

(function () {
  // Priorité: clé actuelle utilisée par features/customisation
  const STORAGE_KEYS = ["hse_theme_key", "hse_theme", "theme", "hseTheme", "hse_ui_theme"];

  // mapping legacy (classes body) -> key data-theme
  const LEGACY_CLASS_TO_KEY = {
    hse_forest: "forest",
  };

  // mapping legacy (ids) -> key data-theme
  const LEGACY_ID_TO_KEY = {
    hseocean: "ocean",
    hseforest: "forest",
    hsesunset: "sunset",
    hseminimal: "minimal",
    hseneon: "neon",
    hseaurora: "aurora",
  };

  // mapping classes -> key data-theme
  const BODYCLASS_TO_KEY = {
    hselight: "light",
    hsedark: "dark",
    hseglass: "glass",
    hseneuro: "neuro",
    hsecyberpunk: "neon",
    hseneon: "neon",
    hseaurora: "aurora",
    hseocean: "ocean",
    hseforest: "forest",
    hsesunset: "sunset",
    hseminimal: "minimal",
  };

  // Liste des thèmes supportés par le manifest + v4
  const KNOWN_THEME_KEYS = new Set([
    "light",
    "dark",
    "glass",
    "neuro",
    "aurora",
    "ocean",
    "forest",
    "sunset",
    "minimal",
    "neon",
    // compat: ancien nom du thème forest
    "hseforest",
    // compat: thème cyberpunk si encore utilisé quelque part
    "cyberpunk",
  ]);

  function getStoredThemeRaw() {
    for (const k of STORAGE_KEYS) {
      try {
        const v = localStorage.getItem(k);
        if (v && v !== "null" && v !== "undefined") return v;
      } catch (_) {}
    }
    return null;
  }

  function normalizeToKey(themeRaw, bodyClassName) {
    const raw = (themeRaw || "").trim().toLowerCase();
    const cls = (bodyClassName || "").trim();

    // 1) Si une classe legacy connue est présente, elle gagne
    for (const legacy in LEGACY_CLASS_TO_KEY) {
      if (cls.split(/\s+/).includes(legacy)) return LEGACY_CLASS_TO_KEY[legacy];
    }

    // 2) Si localStorage contient un id legacy (ex: hseforest/hseocean...), le mapper vers key
    if (LEGACY_ID_TO_KEY[raw]) return LEGACY_ID_TO_KEY[raw];

    // 3) Si localStorage contient une key connue, la garder
    if (KNOWN_THEME_KEYS.has(raw)) return raw;

    // 4) Sinon, dériver depuis classes body standard
    for (const token of cls.split(/\s+/)) {
      const t = token.toLowerCase();
      if (BODYCLASS_TO_KEY[t]) return BODYCLASS_TO_KEY[t];
    }

    // 5) fallback
    return "dark";
  }

  function applyDataTheme(themeKey) {
    document.documentElement.setAttribute("data-theme", themeKey);
  }

  function purgeLegacyClasses() {
    // IMPORTANT: ne purge pas "hse-header" etc, seulement les thèmes connus
    const remove = new Set([
      "hselight",
      "hsedark",
      "hseglass",
      "hseneuro",
      "hsecyberpunk",
      "hseneon",
      "hseaurora",
      "hseocean",
      "hseforest",
      "hsesunset",
      "hseminimal",
      "hsecontrast",
      "hseblue",
      "hsegreen",
      "hsecolor",
      "hserainbow",
      "hse_forest",
    ]);

    for (const c of Array.from(document.body.classList)) {
      if (remove.has(c)) document.body.classList.remove(c);
    }
  }

  function run() {
    const stored = getStoredThemeRaw();
    const themeKey = normalizeToKey(stored, document.body.className);

    applyDataTheme(themeKey);

    // Optionnel mais conseillé: évite que style.css (legacy body.hse...) écrase les tokens v4
    purgeLegacyClasses();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
