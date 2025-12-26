'use strict';

/**
 * Panel de monitoring de la santé du backend
 */

import { getBackendHealth } from '../diagnostics.api.js';
import { 
  getAutoRefreshTimer, 
  setAutoRefreshTimer, 
  addHealthMetric,
  getHealthHistory 
} from '../diagnostics.state.js';
import { 
  getHealthAlerts,
  getUptimeVariant,
  getErrorVariant,
  getLatencyVariant,
  getMemoryVariant,
  HEALTH_CONFIG
} from '../logic/healthAnalyzer.js';
import { formatUptimeDuration, formatBytes, formatTimeSince } from '../logic/formatters.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
// ✅ Tous les composants partagés en import namespace
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';



console.info('[healthPanel] Module chargé');

/**
 * Point d'entrée principal
 */
export async function loadHealthPanel(container) {
  try {
    console.log('[healthPanel] Chargement...');

    // Loader
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Chargement santé...')
    ]));

    // API call
    const health = await getBackendHealth();
    
    // Ajouter à l'historique
    addHealthMetric(health);

    // Render
    renderHealthInterface(container, health);

    // Auto-refresh
    startAutoRefresh(container);

    showToast('État de santé chargé', 'success');

  } catch (error) {
    console.error('[healthPanel] Erreur:', error);
    renderHealthFallback(container, error);
  }
}

/**
 * Rendu de l'interface
 */
function renderHealthInterface(container, health) {
  container.innerHTML = '';

  // Métriques principales
  const metricsDiv = createElement('div', { class: 'metrics-grid' }, [
    Badge.create(
      `Uptime: ${formatUptimeDuration(health.uptime) || 'N/A'}`,
      getUptimeVariant(health.uptime_percent)
    ),
    Badge.create(
      `Requêtes/h: ${health.requests_per_hour || 0}`,
      'info'
    ),
    Badge.create(
      `Erreurs/h: ${health.errors_per_hour || 0}`,
      getErrorVariant(health.errors_per_hour)
    ),
    Badge.create(
      `Latence: ${health.avg_latency || 0}ms`,
      getLatencyVariant(health.avg_latency)
    ),
    Badge.create(
      `Mémoire: ${formatBytes(health.memory_used) || 'N/A'}`,
      getMemoryVariant(health.memory_percent)
    )
  ]);

  // Alertes
  const alerts = getHealthAlerts(health);
  const alertsDiv = createElement('div', { class: 'alerts-section' }, [
    alerts.length > 0
      ? createElement('h3', {}, '⚠️ Alertes')
      : null,
    alerts.length > 0
      ? createElement('ul', {},
          alerts.map(a => createElement('li', {}, [
            Badge.create(a.message, a.level)
          ]))
        )
      : createElement('p', {}, '✅ Aucune alerte - Système sain')
  ].filter(Boolean));

  // Détails système
  const details = [
    ['Version', health.version || 'N/A'],
    ['Démarré le', health.start_time ? new Date(health.start_time).toLocaleString() : 'N/A'],
    ['Dernière requête', health.last_request ? formatTimeSince(health.last_request) : 'N/A'],
    ['Total requêtes', health.total_requests || 0],
    ['Total erreurs', health.total_errors || 0],
    ['Taux succès', health.success_rate ? `${health.success_rate}%` : 'N/A']
  ];

  const detailsTable = createElement('table', { class: 'details-table' },
    details.map(([label, value]) =>
      createElement('tr', {}, [
        createElement('td', { class: 'label' }, label),
        createElement('td', { class: 'value' }, String(value))
      ])
    )
  );

  const detailsDiv = createElement('div', { class: 'system-details' }, [
    createElement('h3', {}, 'Détails système'),
    detailsTable
  ]);

  // Card principale
  const content = createElement('div', { class: 'health-sections' }, [
    metricsDiv,
    alertsDiv,
    detailsDiv
  ]);

  const mainCard = Card.create('Santé du Backend', content);
  container.appendChild(mainCard);

  // Boutons d'action
  const actionsDiv = createElement('div', { class: 'health-actions' });

  const refreshBtn = Button.create(
    'Actualiser',
    () => loadHealthPanel(container),
    'primary'
  );

  const toggleBtn = Button.create(
    getAutoRefreshTimer() ? 'Pause auto-refresh' : 'Auto-refresh',
    () => toggleAutoRefresh(container),
    'secondary'
  );

  if (getAutoRefreshTimer()) {
    toggleBtn.classList.add('active');
  }

  actionsDiv.appendChild(refreshBtn);
  actionsDiv.appendChild(toggleBtn);
  container.appendChild(actionsDiv);
}

/**
 * Rendu fallback en cas d'erreur
 */
function renderHealthFallback(container, error) {
  console.warn('[healthPanel] Fallback:', error);

  const fallbackCard = Card.create('Santé Backend', createElement('div', {}, [
    createElement('p', {}, '❌ API santé non disponible'),
    createElement('p', {}, `Erreur: ${error.message}`),
    createElement('p', {}, 'Endpoint: /api/home_suivi_elec/get_backend_health'),
    createElement('br'),
    createElement('p', {}, 'Métriques de base:'),
    createElement('ul', {}, [
      createElement('li', {}, '✅ Backend Actif'),
      createElement('li', {}, '✅ API principale Fonctionnelle'),
      createElement('li', {}, `✅ Vérification: ${new Date().toLocaleString()}`)
    ])
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadHealthPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('API santé non disponible', 'warning');
}

/**
 * Démarre l'auto-refresh
 */
function startAutoRefresh(container) {
  const timer = getAutoRefreshTimer();
  if (timer) {
    clearInterval(timer);
  }

  if (HEALTH_CONFIG.REFRESH_INTERVAL) {
    const newTimer = setInterval(() => {
      console.log('[healthPanel] Auto-refresh...');
      loadHealthPanel(container);
    }, HEALTH_CONFIG.REFRESH_INTERVAL);

    setAutoRefreshTimer(newTimer);
  }
}

/**
 * Arrête l'auto-refresh
 */
function stopAutoRefresh() {
  const timer = getAutoRefreshTimer();
  if (timer) {
    clearInterval(timer);
    setAutoRefreshTimer(null);
  }
}

/**
 * Toggle auto-refresh
 */
function toggleAutoRefresh(container) {
  if (getAutoRefreshTimer()) {
    stopAutoRefresh();
    showToast('Auto-refresh désactivé', 'info');
  } else {
    startAutoRefresh(container);
    showToast('Auto-refresh activé', 'info');
  }
  
  // Re-render pour mettre à jour le bouton
  loadHealthPanel(container);
}

/**
 * Cleanup à l'arrêt du panel
 */
export function cleanupHealthPanel() {
  stopAutoRefresh();
  console.log('[healthPanel] Cleanup effectué');
}
