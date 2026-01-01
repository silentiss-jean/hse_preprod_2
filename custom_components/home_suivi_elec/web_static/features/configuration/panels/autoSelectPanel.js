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
    <div class="card" style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-left: 4px solid #2196f3; margin-top: 20px;">
      <h3>🤖 Sélection automatique intelligente</h3>
      <p style="margin-bottom: 15px; line-height: 1.5;">
        <strong>Le système analyse tous vos capteurs</strong> et sélectionne automatiquement les meilleurs selon ces critères :
      </p>
      <ul style="margin-bottom: 15px; line-height: 1.6;">
        <li>✅ <strong>Energy (kWh)</strong> prioritaire sur Power (W)</li>
        <li>⭐ Score de qualité optimal (intégration, fiabilité)</li>
        <li>🎯 Un seul capteur par appareil (évite les doublons)</li>
        <li>🔌 Capteurs physiques prioritaires sur virtuels</li>
      </ul>
      <button 
        id="autoSelectBtn" 
        class="primary" 
        type="button" 
        style="background: linear-gradient(135deg, #2196f3 0%, #1976d2 100%); font-size: 16px; padding: 12px 24px; box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3);"
      >
        ✨ Lancer la sélection automatique
      </button>
      <p id="autoSelectStatus" style="margin-top: 12px; font-size: 0.9em; color: #1565c0; font-weight: 600;"></p>
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
    
    if (statusEl) {
      statusEl.textContent = '⏳ Analyse des capteurs en cours...';
      statusEl.style.color = '#ff9800';
    }

    console.log('[autoSelectPanel] Lancement sélection automatique');

    if (typeof autoSelectCallback === 'function') {
      const result = await autoSelectCallback();
      
      // Afficher le résultat
      if (statusEl) {
        statusEl.textContent = `✅ ${result.count || 0} capteur(s) sélectionné(s) automatiquement !`;
        statusEl.style.color = '#4caf50';
      }
      
      showToast(`✨ Sélection automatique terminée : ${result.count || 0} capteur(s)`, 'success');
      
      // Émettre événement pour rafraîchir l'affichage
      eventBus.emit('auto-selection-completed', result);
      
    } else {
      console.warn('[autoSelectPanel] Callback autoSelectCallback manquant');
      if (statusEl) {
        statusEl.textContent = '⚠️ Fonction de sélection non disponible';
        statusEl.style.color = '#f44336';
      }
    }

  } catch (error) {
    console.error('[autoSelectPanel] Erreur sélection auto:', error);
    
    if (statusEl) {
      statusEl.textContent = '❌ Erreur lors de la sélection automatique';
      statusEl.style.color = '#f44336';
    }
    
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
    statusEl.textContent = '';
  }
}
