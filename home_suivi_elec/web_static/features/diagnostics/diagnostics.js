'use strict';

/**
 * Orchestrateur principal du module diagnostics
 * Point d'entrée Phase 3
 */

import { renderDiagnosticsLayout, renderLoader, renderError } from './diagnostics.view.js';
import { getActiveSubTab, setActiveSubTab, cleanup } from './diagnostics.state.js';
import { loadCapteursPanel } from './panels/capteursPanel.js';
import { loadIntegrationsPanel } from './panels/integrationsPanel.js';
import { loadHealthPanel, cleanupHealthPanel } from './panels/healthPanel.js';
import { showToast } from '../../shared/uiToast.js';
import { loadGroupsPanel } from './panels/groupsPanel.js';
import { loadAlertsPanel } from './panels/alertsPanel.js';
import { loadOverviewPanel } from './panels/overviewPanel.js';
import { loadHiddenSensorsPanel } from './panels/hiddenSensorsPanel.js';

console.info('[diagnostics] Module diagnostics Phase 3 chargé');

/**
 * Point d'entrée principal
 * Appelé par router.js
 */
export async function loadDiagnostics() {
  console.log('🔧 [diagnostics] loadDiagnostics démarré');

  const container = document.getElementById('diagnostics');
  if (!container) {
    console.error('❌ [diagnostics] Conteneur #diagnostics introuvable');
    return;
  }

  try {
    // 1. Générer le layout HTML (reste en innerHTML pour structure complète)
    container.innerHTML = renderDiagnosticsLayout();

    // 2. Initialiser les handlers de navigation
    initSubTabHandlers();

    // 3. Charger le premier sous-onglet (capteurs par défaut)
    await switchSubTab('overview');

    console.log('✅ [diagnostics] Diagnostics initialisé');

  } catch (error) {
    console.error('❌ [diagnostics] Erreur lors du chargement:', error);
    // ✅ Utiliser renderError au lieu de innerHTML
    renderError(container, error);
    showToast(`Erreur: ${error.message}`, 'error');
  }
}

/**
 * Initialise les handlers des sous-onglets
 */
function initSubTabHandlers() {
  const buttons = document.querySelectorAll('.diagnostics-subnav .subtab-btn');
  
  buttons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const tabName = btn.getAttribute('data-tab');
      
      // Update UI
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // Charger le sous-onglet
      await switchSubTab(tabName);
    });
  });

  console.log('[diagnostics] Handlers sous-onglets initialisés');
}

/**
 * Bascule vers un sous-onglet
 * @param {string} tabName - Nom du sous-onglet (capteurs, integrations, health)
 */
async function switchSubTab(tabName) {
  const contentContainer = document.getElementById('diagnostics-tab-content');
  if (!contentContainer) {
    console.error('[diagnostics] Container diagnostics-tab-content introuvable');
    return;
  }

  // ✅ AJOUT : Nettoyer l'auto-refresh du healthPanel avant de changer d'onglet
  cleanupHealthPanel();

  setActiveSubTab(tabName);

    // ✅ Utiliser renderLoader au lieu de innerHTML
    renderLoader(contentContainer, `Chargement ${tabName}...`);

  // AVANT tous les autres onglets, ajoutez :

  try {
    switch (tabName) {
      case 'overview':
        await loadOverviewPanel(contentContainer);
        break;

      case 'capteurs':
        await loadCapteursPanel(contentContainer);
        break;

      case 'integrations':
        await loadIntegrationsPanel(contentContainer);
        break;

      case 'health':
        await loadHealthPanel(contentContainer);
        break;
        
      // ✅ NOUVEAUX CAS
      case 'groups':
        await loadGroupsPanel(contentContainer);
        break;

      case 'alerts':
        await loadAlertsPanel(contentContainer);
        break;

      case 'Capteurs Cachés':
        await loadHiddenSensorsPanel(contentContainer);
        break;

      default:
        // ✅ Utiliser renderError
        const error = new Error(`Onglet non implémenté: ${tabName}`);
        renderError(contentContainer, error);
        console.error(`[diagnostics] Onglet inconnu: ${tabName}`);
    }

    console.log(`[diagnostics] Onglet ${tabName} chargé`);

  } catch (error) {
    console.error(`[diagnostics] Erreur onglet ${tabName}:`, error);
    // ✅ Utiliser renderError
    renderError(contentContainer, error);
    showToast(`Erreur: ${error.message}`, 'error');
  }
}

/**
 * Recharge l'onglet actif
 */
export async function reloadCurrentTab() {
  const currentTab = getActiveSubTab();
  await switchSubTab(currentTab);
  showToast('Rechargé', 'info');
}

/**
 * Cleanup à la destruction du module
 */
export function cleanupDiagnostics() {
  cleanupHealthPanel();
  cleanup();
  console.log('[diagnostics] Cleanup effectué');
}
