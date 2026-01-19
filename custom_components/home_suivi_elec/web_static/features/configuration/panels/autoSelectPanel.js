'use strict';

/**
 * autoSelectPanel.js
 * Panel de sélection automatique intelligente des meilleurs capteurs
 * Migré depuis index.html - Section "Sélection automatique intelligente"
 */

import { eventBus } from '../../../shared/eventBus.js';
import { showToast } from '../../../shared/uiToast.js';

/**
 * Génère le HTML du panel de sélection automatique
 * @returns {string} HTML du panel
 */
export function renderAutoSelectPanel() {
  return `
    <!-- ✅✅✅ BLOC SÉLECTION AUTO ✅✅✅ -->
    <div class="card hse-auto-panel">
      <h3>🤖 Sélection automatique intelligente</h3>
      <p class="hse-auto-desc">
        <strong>Le système analyse tous vos capteurs</strong> et sélectionne automatiquement les meilleurs selon ces critères :
      </p>
      <ul>
        <li>✅ <strong>Energy (kWh)</strong> prioritaire sur Power (W)</li>
        <li>⭐ Score de qualité optimal (intégration, fiabilité)</li>
        <li>🎯 Un seul capteur par appareil (évite les doublons)</li>
        <li>🔌 Capteurs physiques prioritaires sur virtuels</li>
      </ul>
      <button 
        id="autoSelectBtn" 
        class="primary hse-auto-btn" 
        type="button"
      >
        ✨ Lancer la sélection automatique
      </button>
      <p id="autoSelectStatus" class="hse-auto-status"></p>
    </div>
  `;
}

/**
 * Initialise le panel : binding du bouton de sélection auto
 * @param {Function} autoSelectCallback - Callback pour lancer la sélection automatique
 */
export function initAutoSelectPanel(autoSelectCallback) {
  console.info('[autoSelectPanel] Initialisation');

  const btn = document.getElementById('autoSelectBtn');
  if (!btn) {
    console.warn('[autoSelectPanel] Bouton autoSelectBtn introuvable');
    return;
  }

  // Retirer ancien listener
  const oldBtn = btn;
  const newBtn = oldBtn.cloneNode(true);
  oldBtn.parentNode.replaceChild(newBtn, oldBtn);

  // Bind nouveau listener
  const autoSelectBtn = document.getElementById('autoSelectBtn');
  autoSelectBtn.addEventListener('click', async () => {
    await handleAutoSelect(autoSelectCallback);
  });

  console.info('[autoSelectPanel] ✅ Initialisé');
}

function setStatus(statusEl, text, kind) {
  if (!statusEl) return;
  statusEl.textContent = text || '';
  statusEl.classList.remove('is-warn', 'is-ok', 'is-err');
  if (kind) statusEl.classList.add(kind);
}

/**
 * Gère le clic sur le bouton de sélection automatique
 * @param {Function} autoSelectCallback - Callback de sélection
 */
async function handleAutoSelect(autoSelectCallback) {
  const statusEl = document.getElementById('autoSelectStatus');
  const btn = document.getElementById('autoSelectBtn');

  try {
    // Désactiver le bouton pendant le traitement
    if (btn) btn.disabled = true;

    setStatus(statusEl, '⏳ Analyse des capteurs en cours...', 'is-warn');

    console.log('[autoSelectPanel] Lancement sélection automatique');

    if (typeof autoSelectCallback === 'function') {
      const result = await autoSelectCallback();

      setStatus(
        statusEl,
        `✅ ${result.count || 0} capteur(s) sélectionné(s) automatiquement !`,
        'is-ok',
      );

      showToast(
        `✨ Sélection automatique terminée : ${result.count || 0} capteur(s)`,
        'success',
      );

      // Émettre événement pour rafraîchir l'affichage
      eventBus.emit('auto-selection-completed', result);
    } else {
      console.warn('[autoSelectPanel] Callback autoSelectCallback manquant');
      setStatus(statusEl, '⚠️ Fonction de sélection non disponible', 'is-err');
    }
  } catch (error) {
    console.error('[autoSelectPanel] Erreur sélection auto:', error);
    setStatus(statusEl, '❌ Erreur lors de la sélection automatique', 'is-err');
    showToast('❌ Erreur lors de la sélection automatique', 'error');
  } finally {
    // Réactiver le bouton
    if (btn) btn.disabled = false;
  }
}

/**
 * Réinitialise le status de sélection
 */
export function resetAutoSelectStatus() {
  const statusEl = document.getElementById('autoSelectStatus');
  if (statusEl) {
    setStatus(statusEl, '');
  }
}
