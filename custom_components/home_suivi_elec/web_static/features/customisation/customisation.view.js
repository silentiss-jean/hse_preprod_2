"use strict";

import { THEMES, initThemes, applyTheme, getDefaultTheme } from "./logic/themesRegistry.js";

export function renderCustomisationLayout() {
  // IMPORTANT: THEMES peut être vide au premier render (avant initThemes()).
  return `
    <div class="customisation-layout">
      <div class="customisation-header">
        <h2>Apparence & Thème</h2>
      </div>

      <div class="customisation-content">
        <label for="hse-theme-select">Thème de l'interface :</label>
        <select id="hse-theme-select" class="hse-select"></select>
        <p class="hint">Le thème est mémorisé dans ce navigateur (localStorage).</p>
      </div>

      <section class="hse-custom-section">
        <h2>Regroupement des capteurs</h2>
        <div id="hse-groups-panel"></div>
      </section>
    </div>
  `;
}
