"use strict";

/**
 * Vues pour le module Generation
 */

/**
 * Génère le layout HTML complet de Generation
 * @returns {string} HTML
 */
export function renderGenerationLayout() {
  return `
        <div class="generation-layout">
            <div class="generation-container">

                <!-- Hero / Title -->
                <div class="generation-hero">
                    <div class="generation-hero-left">
                        <h1 class="generation-title">🎨 Génération de cartes Lovelace</h1>
                        <p class="generation-subtitle">Génère un YAML prêt à coller dans un dashboard Home Assistant, avec un aperçu rapide.</p>
                    </div>
                    <div class="generation-hero-right">
                        <button id="refreshGenerate" class="btn btn-refresh">🔄 Actualiser</button>
                    </div>
                </div>

                <!-- Meta + Actions grouped -->
                <div class="generation-top">
                    <div class="generation-meta">
                        <div class="generation-meta-item">
                            <span class="generation-meta-label">Sensors HSE détectés</span>
                            <span id="sensor-count" class="generation-meta-value">Chargement...</span>
                        </div>
                        <div class="generation-meta-item">
                            <span class="generation-meta-label">Dernière génération</span>
                            <span id="last-gen" class="generation-meta-value">Jamais</span>
                        </div>
                    </div>

                    <div class="generation-actions">
                        <button id="btn-generate-yaml" class="btn btn-primary">⚡ Générer</button>
                        <button id="btn-preview" class="btn btn-info">👁️ Aperçu</button>
                        <button id="btn-copy-yaml" class="btn btn-secondary">📋 Copier</button>
                        <button id="btn-download-yaml" class="btn btn-success">📥 Télécharger</button>
                    </div>
                </div>

                <!-- Panels grid (YAML + Preview) -->
                <div class="generation-panels">

                    <!-- YAML Output Section -->
                    <div class="yaml-section">
                        <div class="yaml-header">
                            <h3>📝 Code YAML</h3>
                            <div class="yaml-hint">Astuce: copier puis coller dans un nouveau dashboard, puis adapter si besoin.</div>
                        </div>
                        <pre id="yaml-code" class="code-block">Cliquez sur "Générer" pour commencer...</pre>
                    </div>

                    <!-- Preview Section (hidden by default) -->
                    <div id="preview-container" class="is-hidden">
                        <div class="preview-header">
                            <h3>👁️ Aperçu</h3>
                            <div class="preview-hint">Aperçu simplifié (affichage rapide), pas un rendu Lovelace 1:1.</div>
                        </div>
                        <div id="dashboard-preview" class="preview-grid"></div>
                    </div>

                </div>

            </div>
        </div>
    `;
}
