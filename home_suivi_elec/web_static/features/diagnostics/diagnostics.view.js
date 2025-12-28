"use strict";


/**
 * Génération du layout HTML pour le module diagnostics
 */


// Ré-exporter les vues communes
export { renderLoader, renderError } from '../../shared/views/commonViews.js';


/**
 * Génère le layout HTML des diagnostics
 */
export function renderDiagnosticsLayout() {
  return `
    <div class="diagnostics-header">
      <h2>🔍 Diagnostics Complets</h2>
      <p class="diagnostics-subtitle">Surveillance approfondie de votre système</p>
    </div>

    <nav class="diagnostics-subnav">
      <!-- ✅ NOUVEAU : Vue d'ensemble EN PREMIER -->
      <button class="subtab-btn active" data-tab="overview">
        🏠 Vue d'ensemble
      </button>
      
      <button class="subtab-btn" data-tab="capteurs">
        🔌 Capteurs
      </button>
      
      <button class="subtab-btn" data-tab="integrations">
        🔗 Intégrations
      </button>
      
      <button class="subtab-btn" data-tab="health">
        ❤️ Santé Backend
      </button>
      
      <button class="subtab-btn" data-tab="groups">
        👨‍👧‍👦 Groupes & Relations
      </button>
      
      <button class="subtab-btn" data-tab="alerts">
        🔔 Alertes
      </button>
    </nav>

    <div id="diagnostics-tab-content" class="diagnostics-content">
      <!-- Le contenu sera chargé dynamiquement -->
    </div>
  `;
}

