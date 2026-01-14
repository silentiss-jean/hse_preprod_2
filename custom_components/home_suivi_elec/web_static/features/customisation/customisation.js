"use strict";

import { renderCustomisationLayout } from "./customisation.view.js";
import { getCurrentTheme, setCurrentTheme } from "./customisation.state.js";
import { THEMES, getThemeById, getDefaultTheme, initThemes } from "./logic/themesRegistry.js";
import { renderGroupsPanel } from "./panels/groupsPanel.js";

console.log("[customisation] Module chargé");

const LEGACY_BODY_CLASSES = new Set([
  "hselight","hsedark","hsecontrast","hseblue","hsegreen","hsecolor","hserainbow",
  "hse_light","hse_dark","hse_ocean","hse_forest","hse_sunset","hse_minimal","hse_neon",
]);

function purgeLegacyBodyThemeClasses() {
  for (const c of Array.from(document.body.classList)) {
    if (LEGACY_BODY_CLASSES.has(c)) document.body.classList.remove(c);
  }
}

export async function loadCustomisation() {
  console.log("[customisation] loadCustomisation appelé");

  try {
    await initThemes();
    console.log("[customisation] Themes initialisés:", THEMES.length);
  } catch (e) {
    console.error("[customisation] initThemes() a échoué", e);
  }

  const container = document.getElementById("customisation");
  if (!container) return;

  container.innerHTML = renderCustomisationLayout();

  const selectEl = container.querySelector("#hse-theme-select");
  if (!selectEl) return;

  if (!Array.isArray(THEMES) || THEMES.length === 0) {
    selectEl.innerHTML = `<option value="dark">Dark</option><option value="light">Light</option>`;
    selectEl.value = "dark";
    purgeLegacyBodyThemeClasses();
    setCurrentTheme("dark"); // applique + persiste via registry (si patch state) [file:168]
    return;
  }

  selectEl.innerHTML = THEMES
    .map((t) => `<option value="${t.key}">${t.label}</option>`)
    .join("");

  const stored = getCurrentTheme();
  const resolved = getThemeById(stored) || getDefaultTheme() || THEMES[0];
  const initialKey = resolved?.key || "dark"; // dark est default:true [file:168]

  selectEl.value = initialKey;
  if (selectEl.selectedIndex === -1) selectEl.selectedIndex = 0;

  purgeLegacyBodyThemeClasses();
  setCurrentTheme(selectEl.value);

  selectEl.addEventListener("change", (e) => {
    const newKey = e.target.value;
    purgeLegacyBodyThemeClasses();
    setCurrentTheme(newKey);
  });

  const groupsContainer = container.querySelector("#hse-groups-panel");
  if (groupsContainer) {
    await renderGroupsPanel(groupsContainer);
  }
}
