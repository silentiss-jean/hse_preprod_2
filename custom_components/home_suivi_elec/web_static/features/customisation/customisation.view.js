"use strict";
/**
 * customisation.view.js - VERSION COMPACTE HORIZONTALE
 */

import { THEMES } from "./logic/themesRegistry.js";

export function renderCustomisationLayout() {
    return `
    <div class="customisation-layout">
        <div class="customisation-header">
            <h2>Apparence & Thème</h2>
        </div>
        
        <div class="customisation-content">
            <!-- Grille de thèmes horizontale compacte -->
            <div class="theme-compact-selector">
                <p class="theme-hint">
                    🎨 Cliquez sur un thème pour l'appliquer (mémorisé dans le navigateur)
                </p>
                <div class="theme-compact-grid">
                    ${THEMES.map(theme => `
                        <div class="theme-compact-card ${theme.default ? 'is-active' : ''}" 
                             data-theme="${theme.key}"
                             role="button"
                             tabindex="0"
                             aria-label="Appliquer le thème ${theme.label}">
                            <span class="theme-compact-icon">${theme.icon}</span>
                            <div class="theme-compact-info">
                                <strong>${theme.label}</strong>
                                <span class="theme-compact-desc">${theme.description}</span>
                            </div>
                            <div class="theme-compact-colors" data-theme-preview="${theme.key}">
                                <div class="color-dot accent"></div>
                                <div class="color-dot success"></div>
                                <div class="color-dot warning"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>

        <section style="margin-top: 40px;">
            <h2>Regroupement des capteurs</h2>
            <div id="hse-groups-panel"></div>
        </section>
    </div>
    `;
}

