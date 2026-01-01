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
            <div class="container">
                <!-- Header avec titre et bouton refresh -->
                <div class="header-section">
                    <h1>🎨 Génération de cartes Lovelace</h1>
                    <button id="refreshGenerate" class="btn btn-refresh">🔄 Actualiser</button>
                </div>

                <!-- Stats Card -->
                <div class="stats-card">
                    <div class="stat-item">
                        <span class="stat-label">Sensors HSE détectés:</span>
                        <span id="sensor-count" class="stat-value">Chargement...</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Dernière génération:</span>
                        <span id="last-gen" class="stat-value">Jamais</span>
                    </div>
                </div>

                <!-- Actions Section -->
                <div class="actions-section">
                    <button id="btn-generate-yaml" class="btn btn-primary">
                        ⚡ Générer YAML
                    </button>
                    <button id="btn-download-yaml" class="btn btn-success">
                        📥 Télécharger
                    </button>
                    <button id="btn-preview" class="btn btn-info">
                        👁️ Aperçu
                    </button>
                    <button id="btn-copy-yaml" class="btn btn-secondary">
                        📋 Copier
                    </button>
                </div>

                <!-- YAML Output Section -->
                <div class="yaml-section">
                    <h3>📝 Code YAML généré</h3>
                    <pre id="yaml-code" class="code-block">Cliquez sur "Générer YAML" pour commencer...</pre>
                </div>

                <!-- Preview Section (hidden by default) -->
                <div id="preview-container" style="display:none;">
                    <h3>👁️ Aperçu du Dashboard</h3>
                    <div id="dashboard-preview" class="preview-grid"></div>
                </div>
            </div>
        </div>
    `;
}

