'use strict';

import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Card } from '../../../shared/components/Card.js';
import { Badge } from '../../../shared/components/Badge.js';
import { getDeepDiagnostics } from '../diagnostics.api.js';

console.info('[healthPanel] Module chargé');

let healthRefreshInterval = null;

export async function loadHealthPanel(container) {
  try {
    console.log('[healthPanel] Chargement...');

    cleanupHealthPanel();

    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Chargement de la santé...')
    ]));

    await refreshHealthData(container);

    healthRefreshInterval = setInterval(() => {
      refreshHealthData(container);
    }, 5000);

    showToast('Panel Santé chargé', 'success');
  } catch (error) {
    console.error('[healthPanel] Erreur:', error);
    renderHealthError(container, error);
  }
}

async function refreshHealthData(container) {
  try {
    const full_diag = await getDeepDiagnostics();
    const integration_data = full_diag?.integration ?? {};

    renderHealthInterface(container, integration_data, full_diag);
  } catch (err) {
    console.error('[healthPanel] Erreur refresh:', err);
    renderHealthError(container, err);
  }
}

function renderHealthInterface(container, integration_data, full_diag) {
  container.innerHTML = '';

  const backend_running = integration_data?.running === true;
  const health_score = full_diag?.health_score;

  const statusCard = Card.create('🔧 Statut Intégration', createElement('div', {}, [
    createElement('div', { class: 'health-status' }, [
      createElement('strong', {}, ['État : ']),
      Badge.create(
        backend_running ? '✅ Opérationnel' : '❌ Arrêté',
        backend_running ? 'success' : 'error'
      )
    ]),
    createElement('p', {}, [`Uptime: ${formatUptime(integration_data.uptime ?? 0)}`]),
    createElement('p', {}, [`Version: ${integration_data.version || 'N/A'}`]),
    ...(health_score ? [
      createElement('p', {}, [`Score: ${health_score.score}/100 (${health_score.grade})`])
    ] : [])
  ]));

  container.appendChild(statusCard);

  // Afficher alerte critique si intégration down
  if (!backend_running && Array.isArray(integration_data.issues)) {
    const critical_issue = integration_data.issues.find(i => i.type === 'backend_down');
    if (critical_issue) {
      const alertCard = Card.create('⚠️ Alerte Critique', createElement('div', {}, [
        createElement('p', { style: 'color:var(--danger,#dc3545);font-weight:bold;' }, [
          critical_issue.message || 'Intégration non opérationnelle!'
        ]),
        createElement('p', { style: 'font-size:0.9em;margin-top:8px;' }, [
          `Solution: ${critical_issue.solution || 'Vérifiez les logs'}`
        ])
      ]));
      container.appendChild(alertCard);
    }
  }
}

function renderHealthError(container, error) {
  container.innerHTML = '';

  const errorCard = Card.create('❌ Erreur', createElement('div', {}, [
    createElement('p', {}, `Impossible de charger les données de santé`),
    createElement('p', {}, `Erreur: ${error.message}`)
  ]));

  container.appendChild(errorCard);
}

function formatUptime(seconds) {
  if (!seconds) return 'N/A';
  
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) return `${days}j ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function cleanupHealthPanel() {
  if (healthRefreshInterval) {
    clearInterval(healthRefreshInterval);
    healthRefreshInterval = null;
    console.log('[healthPanel] Auto-refresh arrêté');
  }
}
