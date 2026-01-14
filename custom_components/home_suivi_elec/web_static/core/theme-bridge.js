/* theme-bridge.js
 * Objectif: activer le thème v3 basé sur data-theme même si le legacy (body classes) est encore présent.
 * - Lit localStorage (si présent)
 * - Lit body.className (ex: "hselight hse_forest")
 * - Pose documentElement.dataset.theme / setAttribute("data-theme", ...)
 * - Optionnel: purge certaines classes legacy qui perturbent l'affichage
 */

(function () {
  const STORAGE_KEYS = ["hse_theme", "theme", "hseTheme", "hse_ui_theme"];

  // mapping legacy -> v3 (à compléter si besoin)
  const LEGACY_TO_V3 = {
    hse_forest: "hseforest",
    // si tu en as: hse_ocean: "hseocean", etc.
  };

  // mapping classes -> v3 keys simples
  const BODYCLASS_TO_V3 = {
    hselight: "light",
    hsedark: "dark",
    hseglass: "glass",
    hseneuro: "neuro",
    hsecyberpunk: "cyberpunk",
    hseaurora: "aurora",
  };

  function getStoredThemeRaw() {
    for (const k of STORAGE_KEYS) {
      try {
        const v = localStorage.getItem(k);
        if (v && v !== "null" && v !== "undefined") return v;
      } catch (_) {}
    }
    return null;
  }

  function normalizeToV3(themeRaw, bodyClassName) {
    const raw = (themeRaw || "").trim();
    const cls = (bodyClassName || "").trim();

    // 1) Si une classe legacy connue est présente, elle gagne
    for (const legacy in LEGACY_TO_V3) {
      if (cls.split(/\s+/).includes(legacy)) return LEGACY_TO_V3[legacy];
    }

    // 2) Si localStorage contient déjà un id v3 (ex: "hseforest"), on le garde
    if (/^hse[a-z0-9]+$/i.test(raw)) return raw.toLowerCase();

    // 3) Si localStorage contient une key v3 (light/dark/...), on la garde
    if (/^(light|dark|glass|neuro|cyberpunk|aurora)$/i.test(raw)) return raw.toLowerCase();

    // 4) Sinon, dériver depuis classes body standard
    for (const token of cls.split(/\s+/)) {
      if (BODYCLASS_TO_V3[token]) return BODYCLASS_TO_V3[token];
    }

    // 5) fallback
    return "light";
  }

  function applyDataTheme(v3) {
    // v3 peut être "light" ou "hseforest" etc.
    document.documentElement.setAttribute("data-theme", v3);
  }

  function purgeLegacyClasses() {
    // IMPORTANT: ne purge pas "hse-header" etc, seulement les thèmes connus
    const remove = new Set([
      "hselight", "hsedark", "hseglass", "hseneuro", "hsecyberpunk", "hseaurora",
      "hsecontrast", "hseblue", "hsegreen", "hsecolor", "hserainbow",
      "hse_forest"
    ]);

    for (const c of Array.from(document.body.classList)) {
      if (remove.has(c)) document.body.classList.remove(c);
    }
  }

  function run() {
    const stored = getStoredThemeRaw();
    const v3 = normalizeToV3(stored, document.body.className);

    applyDataTheme(v3);

    // Optionnel mais conseillé: évite que style.css (legacy body.hse...) écrase v3
    purgeLegacyClasses();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
