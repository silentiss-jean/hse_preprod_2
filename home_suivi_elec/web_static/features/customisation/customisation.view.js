"use strict";
/**
 * Vues pour le module Customisation
 */
import { THEMES } from "./logic/themesRegistry.js";

/**
 * Génère le layout HTML complet de Customisation
 * @returns {string} HTML
 */
export function renderCustomisationLayout() {
  const optionsHtml = THEMES.map(
    (t) => `<option value="${t.id}">${t.label}</option>`
  ).join("");

  return `
    <div class="customisation-layout">
      <div class="customisation-header">
        <h2>Apparence & Thème</h2>
      </div>
      <div class="customisation-content">
        <label for="hse-theme-select">Thème de l'interface :</label>
        <select id="hse-theme-select" class="hse-select">
          ${optionsHtml}
        </select>
        <p class="hint">
          Le thème est mémorisé dans ce navigateur (localStorage).
        </p>
      </div>

      <section style="margin-top:30px;">
        <h2>Regroupement des capteurs</h2>
        <div id="hse-groups-panel"></div>
      </section>
    </div>
  `;
}
