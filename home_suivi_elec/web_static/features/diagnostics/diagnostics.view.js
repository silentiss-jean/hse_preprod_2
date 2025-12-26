"use strict";

/**
 * Génération du layout HTML pour le module diagnostics
 */

// Ré-exporter les vues communes
export { renderLoader, renderError } from '../../shared/views/commonViews.js';

/**
 * Génère le HTML complet du layout diagnostics
 * @returns {string} HTML (conservé pour compatibilité avec loadDiagnostics)
 */
export function renderDiagnosticsLayout() {
  return `
    <div class="diagnostics-enrichi-layout">
      <!-- Header -->
      <div class="diagnostics-header">
        <h2>🔍 Diagnostics Complets</h2>
        <p class="subtitle">Surveillance approfondie de votre système</p>
      </div>

      <!-- Navigation sous-onglets -->
      <nav class="diagnostics-subnav">
        <button class="subtab-btn active" data-tab="capteurs">
          🔌 Capteurs
        </button>
        <button class="subtab-btn" data-tab="integrations">
          🔗 Intégrations
        </button>
        <button class="subtab-btn" data-tab="health">
          ❤️ Santé Backend
        </button>
      </nav>

      <!-- Container de contenu -->
      <div id="diagnostics-tab-content" class="diagnostics-content">
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Chargement...</p>
        </div>
      </div>
    </div>
  `;
}
