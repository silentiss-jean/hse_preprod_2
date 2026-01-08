"use strict";
/**
 * customisation.view.js - VERSION AMÉLIORÉE
 */

import { THEMES } from "./logic/themesRegistry.js";

export function renderCustomisationLayout() {
  const optionsHtml = THEMES.map(
    (t) => `<option value="${t.id}">${t.icon} ${t.label}</option>`
  ).join("");

  return `
    <div class="customisation-layout">
      <div class="customisation-header">
        <h2>Apparence & Thème</h2>
      </div>
      
      <div class="customisation-content">
        <!-- Sélecteur de thème avec preview -->
        <div class="theme-selector-panel">
          <label for="hse-theme-select" class="theme-label">
            🎨 Thème de l'interface :
          </label>
          
          <select id="hse-theme-select" class="hse-select theme-select">
            ${optionsHtml}
          </select>
          
          <p class="theme-hint">
            Le thème est mémorisé dans ce navigateur (localStorage).
          </p>
        </div>

        <!-- Preview des thèmes (grille de cartes) -->
        <div class="theme-preview-grid">
          ${THEMES.map(theme => `
            <div class="theme-preview-card" data-theme="${theme.key}">
              <div class="theme-preview-header">
                <span class="theme-icon">${theme.icon}</span>
                <h3>${theme.label}</h3>
              </div>
              <div class="theme-preview-description">
                ${theme.description}
              </div>
              <div class="theme-preview-colors" data-theme-preview="${theme.key}">
                <div class="color-sample accent"></div>
                <div class="color-sample success"></div>
                <div class="color-sample warning"></div>
                <div class="color-sample error"></div>
              </div>
              <button class="hse-btn hse-btn-sm apply-theme-btn" data-theme="${theme.key}">
                Appliquer
              </button>
            </div>
          `).join('')}
        </div>
      </div>

      <section style="margin-top:30px;">
        <h2>Regroupement des capteurs</h2>
        <div id="hse-groups-panel"></div>
      </section>
    </div>
  `;
}
