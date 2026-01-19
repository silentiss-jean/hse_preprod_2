/* userConfigPanel.js (theming refactor)
   - Suppression des styles inline
   - Ajout de classes dédiées pour stylage via configuration.css (tokens v3)
*/

'use strict';
/**
 * userConfigPanel.js
 * Panel de configuration tarifaire utilisateur (abonnement, tarifs HP/HC)
 * Migré depuis index.html - Section "Configuration tarifaire"
 *
 * Convention:
 * - type_contrat: "prix_unique" | "heures_creuses"
 */

import { showToast } from '../../../shared/uiToast.js';

/**
 * Génère le HTML du panel de configuration utilisateur
 * @returns {string} HTML du panel
 */
export function renderUserConfigPanel() {
  return `
    <div class="user-config-card config-section hse-config-root">
      <div class="section-header">
        <h3>⚙️ Configuration Tarifaire</h3>
      </div>

      <!-- ✅ MESSAGE D'INFORMATION EN PREMIER -->
      <div class="config-note hse-config-note">
        <p class="hse-config-note-text">
          ℹ️ Les modifications seront appliquées après sauvegarde. Les calculs seront mis à jour automatiquement.
        </p>
      </div>

      <div class="config-grid hse-config-grid">
        <!-- Type de contrat -->
        <div class="config-row hse-config-row">
          <label for="type_contrat" class="hse-config-label">Type de contrat :</label>
          <select id="type_contrat" class="config-input hse-config-input">
            <option value="prix_unique">Prix fixe</option>
            <option value="heures_creuses">Heures Pleines / Creuses</option>
          </select>
        </div>

        <!-- Abonnement -->
        <div class="hse-config-grid-2">
          <div class="config-row hse-config-row">
            <label for="abonnement_ht" class="hse-config-label">Abonnement mensuel HT (€) :</label>
            <input type="number" id="abonnement_ht" class="config-input hse-config-input" step="0.01" min="0" placeholder="13.79" />
          </div>
          <div class="config-row hse-config-row">
            <label for="abonnement_ttc" class="hse-config-label">Abonnement mensuel TTC (€) :</label>
            <input type="number" id="abonnement_ttc" class="config-input hse-config-input" step="0.01" min="0" placeholder="19.79" />
          </div>
        </div>

        <!-- Tarif Fixe -->
        <div id="tarifFixeSection" class="tarif-section hse-tarif-section">
          <h4 class="hse-tarif-title">⚡ Tarif Fixe</h4>
          <div class="hse-config-grid-2">
            <div class="config-row hse-config-row">
              <label for="tarifFixeHT" class="hse-config-label">Prix HT (€/kWh) :</label>
              <input type="number" id="tarifFixeHT" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1327" />
            </div>
            <div class="config-row hse-config-row">
              <label for="tarifFixeTTC" class="hse-config-label">Prix TTC (€/kWh) :</label>
              <input type="number" id="tarifFixeTTC" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1952" />
            </div>
          </div>
        </div>

        <!-- Tarif HP/HC -->
        <div id="tarifHPHCSection" class="tarif-section hse-tarif-section" style="display: none;">
          <h4 class="hse-tarif-title">☀️ Heures Pleines</h4>
          <div class="hse-config-grid-2 hse-mb-20">
            <div class="config-row hse-config-row">
              <label for="tarifHPHT" class="hse-config-label">Prix HP HT (€/kWh) :</label>
              <input type="number" id="tarifHPHT" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1327" />
            </div>
            <div class="config-row hse-config-row">
              <label for="tarifHPTTC" class="hse-config-label">Prix HP TTC (€/kWh) :</label>
              <input type="number" id="tarifHPTTC" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1952" />
            </div>
          </div>

          <h4 class="hse-tarif-title">🌙 Heures Creuses</h4>
          <div class="hse-config-grid-2 hse-mb-20">
            <div class="config-row hse-config-row">
              <label for="tarifHCHT" class="hse-config-label">Prix HC HT (€/kWh) :</label>
              <input type="number" id="tarifHCHT" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1327" />
            </div>
            <div class="config-row hse-config-row">
              <label for="tarifHCTTC" class="hse-config-label">Prix HC TTC (€/kWh) :</label>
              <input type="number" id="tarifHCTTC" class="config-input hse-config-input" step="0.0001" min="0" placeholder="0.1952" />
            </div>
          </div>

          <h4 class="hse-tarif-title">🕐 Plage Horaire HC</h4>
          <div class="hse-config-grid-2">
            <div class="config-row hse-config-row">
              <label for="heuresHPDebut" class="hse-config-label">Début (HH:MM) :</label>
              <input type="time" id="heuresHPDebut" class="config-input hse-config-input" value="22:00" />
            </div>
            <div class="config-row hse-config-row">
              <label for="heuresHPFin" class="hse-config-label">Fin (HH:MM) :</label>
              <input type="time" id="heuresHPFin" class="config-input hse-config-input" value="06:00" />
            </div>
          </div>
        </div>

        <!-- Capteurs coût (runtime) -->
        <div class="tarif-section hse-tarif-section hse-runtime-section">
          <h4 class="hse-tarif-title">Capteurs coût (runtime)</h4>

          <label class="hse-inline-check">
            <input type="checkbox" id="enable_cost_sensors_runtime" />
            Activer les capteurs coût (runtime)
          </label>

          <div class="hse-runtime-actions">
            <button id="btnGenerateCostSensors" type="button" class="btn hse-btn-compact">
              Générer / Mettre à jour maintenant
            </button>
            <span id="costSensorsStatus" class="hse-muted">Statut : non chargé</span>
          </div>
        </div>

        <!-- ✅ BOUTON TAILLE NORMALE EN BAS -->
        <div class="config-actions hse-config-actions">
          <button id="saveUserConfig" class="btn btn-primary hse-save-config">
            💾 Sauvegarder la configuration
          </button>
        </div>
      </div>
    </div>
  `;
}

/**
 * Initialise le panel avec les données de configuration
 * @param {Object} composedConfig - Configuration fusionnée (options prioritaires)
 */
export function initUserConfigPanel(composedConfig = {}) {
  console.info('[userConfigPanel] initUserConfigPanel avec config:', composedConfig);

  // Valeurs par défaut sécurisées
  const config = {
    type_contrat: composedConfig.type_contrat || 'prix_unique',
    abonnement_ht: parseFloat(composedConfig.abonnement_ht) || 0,
    abonnement_ttc: parseFloat(composedConfig.abonnement_ttc) || 0,
    prix_ht: parseFloat(composedConfig.prix_ht) || 0,
    prix_ttc: parseFloat(composedConfig.prix_ttc) || 0,
    prix_ht_hp: parseFloat(composedConfig.prix_ht_hp) || 0,
    prix_ttc_hp: parseFloat(composedConfig.prix_ttc_hp) || 0,
    prix_ht_hc: parseFloat(composedConfig.prix_ht_hc) || 0,
    prix_ttc_hc: parseFloat(composedConfig.prix_ttc_hc) || 0,
    hc_start: composedConfig.hc_start || '22:00',
    hc_end: composedConfig.hc_end || '06:00',
  };

  // Remplir les champs communs
  const typeContratSelect = document.getElementById('type_contrat');
  if (typeContratSelect) {
    typeContratSelect.value = config.type_contrat;
  }

  const abonnementHTInput = document.getElementById('abonnement_ht');
  if (abonnementHTInput) {
    abonnementHTInput.value = config.abonnement_ht;
  }

  const abonnementTTCInput = document.getElementById('abonnement_ttc');
  if (abonnementTTCInput) {
    abonnementTTCInput.value = config.abonnement_ttc;
  }

  // Remplir tarif fixe
  const tarifFixeHTInput = document.getElementById('tarifFixeHT');
  if (tarifFixeHTInput) {
    tarifFixeHTInput.value = config.prix_ht;
  }

  const tarifFixeTTCInput = document.getElementById('tarifFixeTTC');
  if (tarifFixeTTCInput) {
    tarifFixeTTCInput.value = config.prix_ttc;
  }

  // Remplir tarif HP/HC
  const tarifHPHTInput = document.getElementById('tarifHPHT');
  if (tarifHPHTInput) {
    tarifHPHTInput.value = config.prix_ht_hp;
  }

  const tarifHPTTCInput = document.getElementById('tarifHPTTC');
  if (tarifHPTTCInput) {
    tarifHPTTCInput.value = config.prix_ttc_hp;
  }

  const tarifHCHTInput = document.getElementById('tarifHCHT');
  if (tarifHCHTInput) {
    tarifHCHTInput.value = config.prix_ht_hc;
  }

  const tarifHCTTCInput = document.getElementById('tarifHCTTC');
  if (tarifHCTTCInput) {
    tarifHCTTCInput.value = config.prix_ttc_hc;
  }

  const heuresHPDebutInput = document.getElementById('heuresHPDebut');
  if (heuresHPDebutInput) {
    heuresHPDebutInput.value = config.hc_start;
  }

  const heuresHPFinInput = document.getElementById('heuresHPFin');
  if (heuresHPFinInput) {
    heuresHPFinInput.value = config.hc_end;
  }

  // Toggle des sections selon le type de contrat
  toggleTarifSections(config.type_contrat);

  // Binding du toggle
  if (typeContratSelect) {
    typeContratSelect.addEventListener('change', (e) => {
      toggleTarifSections(e.target.value);
    });
  }

  console.info('[userConfigPanel] Panel initialisé avec succès');
}

/**
 * Affiche/masque les sections de tarif selon le type de contrat
 * @param {string} type_contrat - "prix_unique" | "heures_creuses"
 */
function toggleTarifSections(type_contrat) {
  const tarifFixeSection = document.getElementById('tarifFixeSection');
  const tarifHPHCSection = document.getElementById('tarifHPHCSection');

  if (type_contrat === 'heures_creuses') {
    if (tarifFixeSection) tarifFixeSection.style.display = 'none';
    if (tarifHPHCSection) tarifHPHCSection.style.display = 'block';
  } else {
    if (tarifFixeSection) tarifFixeSection.style.display = 'block';
    if (tarifHPHCSection) tarifHPHCSection.style.display = 'none';
  }
}

/**
 * Récupère la configuration actuelle depuis les champs du formulaire
 * @returns {Object} Configuration tarifaire
 */
export function getUserConfigFromForm() {
  const type_contrat = document.getElementById('type_contrat')?.value || 'prix_unique';

  const config = {
    type_contrat,
    abonnement_ht: parseFloat(document.getElementById('abonnement_ht')?.value) || 0,
    abonnement_ttc: parseFloat(document.getElementById('abonnement_ttc')?.value) || 0,
  };

  if (type_contrat === 'prix_unique') {
    config.prix_ht = parseFloat(document.getElementById('tarifFixeHT')?.value) || 0;
    config.prix_ttc = parseFloat(document.getElementById('tarifFixeTTC')?.value) || 0;
  } else {
    config.prix_ht_hp = parseFloat(document.getElementById('tarifHPHT')?.value) || 0;
    config.prix_ttc_hp = parseFloat(document.getElementById('tarifHPTTC')?.value) || 0;
    config.prix_ht_hc = parseFloat(document.getElementById('tarifHCHT')?.value) || 0;
    config.prix_ttc_hc = parseFloat(document.getElementById('tarifHCTTC')?.value) || 0;
    config.hc_start = document.getElementById('heuresHPDebut')?.value || '22:00';
    config.hc_end = document.getElementById('heuresHPFin')?.value || '06:00';
  }

  return config;
}
