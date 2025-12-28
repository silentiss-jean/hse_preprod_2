'use strict';

/**
 * Panel Vue d'ensemble - Dashboard de santé globale
 */

import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[overviewPanel] Module chargé');

/**
 * Point d'entrée principal
 */
export async function loadOverviewPanel(container) {
  try {
    console.log('[overviewPanel] Chargement...');

    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Analyse de la santé globale...')
    ]));

    const diagnosticData = await fetchDeepDiagnostics();

    renderOverviewInterface(container, diagnosticData);

    showToast('Vue d\'ensemble chargée', 'success');

  } catch (error) {
    console.error('[overviewPanel] Erreur:', error);
    renderOverviewFallback(container, error);
  }
}

/**
 * Récupère le diagnostic complet depuis le backend
 */
async function fetchDeepDiagnostics() {
  const response = await fetch('/api/home_suivi_elec/deep_diagnostics');
  const result = await response.json();

  if (result?.error === true) {
    throw new Error(result.message || 'Erreur API');
  }

  // IMPORTANT: accepter "enveloppé" OU "direct"
  return result.data || result;
}


/**
 * Rendu de l'interface
 */
function renderOverviewInterface(container, data) {
  container.innerHTML = '';

  const scoreCard = renderScoreCard(data.health_score, data.summary);
  const componentsCard = renderComponentsStatus(data);
  const alertsCard = renderPriorityAlerts(data);
  const recommendationsCard = renderRecommendations(data.recommendations);
  const actionsCard = renderQuickActions();

  const grid = createElement('div', { class: 'overview-grid' }, [
    scoreCard,
    componentsCard,
    alertsCard,
    recommendationsCard,
    actionsCard
  ]);

  container.appendChild(grid);
}

/**
 * Carte du score de santé (Hero)
 */
function renderScoreCard(health_score, summary) {
  const { score, grade } = health_score;
  const gradeInfo = getHealthGradeInfo(score);

  const scoreNumber = createElement('span', { class: 'score-number' });
  scoreNumber.textContent = String(score);

  const scoreTotal = createElement('span', { class: 'score-total' });
  scoreTotal.textContent = '/100';

  const scoreValue = createElement('div', { class: 'score-value' });
  scoreValue.appendChild(scoreNumber);
  scoreValue.appendChild(scoreTotal);

  const scoreCircle = createElement('div', { class: 'score-circle' });
  scoreCircle.appendChild(scoreValue);

  const gradeEmoji = createElement('span', { class: 'grade-emoji' });
  gradeEmoji.textContent = gradeInfo.emoji;

  const gradeLetter = createElement('span', { class: 'grade-letter' });
  gradeLetter.textContent = `Note: ${grade}`;

  const scoreGrade = createElement('div', { class: 'score-grade' });
  scoreGrade.appendChild(gradeEmoji);
  scoreGrade.appendChild(gradeLetter);

  const scoreDisplay = createElement('div', { class: 'score-display' });
  scoreDisplay.appendChild(scoreCircle);
  scoreDisplay.appendChild(scoreGrade);

  const description = createElement('p', { class: 'score-description' });
  description.textContent = summary || getScoreDescription(score);

  const title = createElement('h3');
  title.textContent = '🏥 Santé Globale HSE';

  const content = createElement('div', { class: 'score-card-content' });
  content.appendChild(title);
  content.appendChild(scoreDisplay);
  content.appendChild(description);

  const hero = createElement('div', { class: 'hse-score-hero' });
  hero.appendChild(content);

  return Card.create('', hero, 'hse-score-card');
}

function getHealthGradeInfo(score) {
  if (score >= 90) return { emoji: '🌟', color: 'success' };
  if (score >= 75) return { emoji: '✅', color: 'success' };
  if (score >= 60) return { emoji: '⚠️', color: 'warning' };
  if (score >= 40) return { emoji: '😕', color: 'warning' };
  return { emoji: '❌', color: 'error' };
}

function getScoreDescription(score) {
  if (score >= 90) return 'Excellent ! Tout fonctionne parfaitement.';
  if (score >= 75) return 'Bon état général, quelques optimisations possibles.';
  if (score >= 60) return 'État correct, attention aux alertes.';
  if (score >= 40) return 'Plusieurs problèmes nécessitent votre attention.';
  return 'État critique ! Intervention requise.';
}

/**
 * Carte du statut des composants
 */
function renderComponentsStatus(data) {
  const components = [
    {
      name: '🔧 Intégration',
      status: data.integration?.running ? 'operational' : 'error',  // ← CORRIGÉ
      details: data.integration?.running 
        ? `Uptime: ${formatUptime(data.integration.uptime)}` 
        : 'Non opérationnelle'
    },
    {
      name: '🔌 Capteurs',
      status: data.sensors?.stats?.available > 0 ? 'operational' : 'warning',
      details: `${data.sensors?.stats?.available || 0}/${data.sensors?.stats?.total || 0} disponibles (${data.sensors?.stats?.unavailable || 0} KO)`
    },
    {
      name: '👨‍👧‍👦 Relations',
      status: data.relations?.stats?.parents_with_children > 0 ? 'operational' : 'warning',
      details: `${data.relations?.stats?.total_parents || 0} parent(s), ${data.relations?.stats?.parents_without_children || 0} sans cycles`
    }
  ];

  const componentsList = createElement('div', { class: 'components-list' }, 
    components.map(comp => renderComponentItem(comp))
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, ['📊 Composants']),
    componentsList
  ]);

  return Card.create('', content);
}

function renderComponentItem(component) {
  const statusBadge = Badge.create(
    component.status === 'operational' ? '✅ OK' : 
    component.status === 'warning' ? '⚠️ Attention' : '❌ Erreur',
    component.status === 'operational' ? 'success' : 
    component.status === 'warning' ? 'warning' : 'error'
  );

  return createElement('div', { class: 'component-item' }, [
    createElement('div', { class: 'component-info' }, [
      createElement('strong', {}, [component.name]),
      createElement('span', { class: 'component-details' }, [component.details])
    ]),
    statusBadge
  ]);
}

/**
 * Carte des alertes prioritaires
 */
function renderPriorityAlerts(data) {
  const allIssues = [
    ...(data.integration?.issues || []),  // ← CORRIGÉ
    ...(data.sensors?.issues || []).slice(0, 5),
    ...(data.relations?.issues || []).slice(0, 3)
  ];

  const severityOrder = { critical: 0, error: 1, warning: 2, info: 3 };
  allIssues.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  const topIssues = allIssues.slice(0, 5);

  const alertsList = topIssues.length > 0
    ? createElement('div', { class: 'alerts-list' }, 
        topIssues.map(issue => renderAlertItem(issue))
      )
    : createElement('p', { class: 'no-alerts' }, ['✅ Aucune alerte prioritaire']);

  const content = createElement('div', {}, [
    createElement('h3', {}, ['🔔 Alertes Prioritaires']),
    alertsList
  ]);

  return Card.create('', content);
}

function renderAlertItem(issue) {
  const severityIcon = {
    critical: '🔴',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };

  return createElement('div', { class: `alert-item alert-${issue.severity}` }, [
    createElement('span', { class: 'alert-icon' }, [severityIcon[issue.severity] || 'ℹ️']),
    createElement('span', { class: 'alert-message' }, [issue.message])
  ]);
}

/**
 * Carte des recommandations
 */
function renderRecommendations(recommendations) {
  const recList = (recommendations || []).length > 0
    ? createElement('div', { class: 'recommendations-list' },
        (recommendations || []).slice(0, 3).map(rec => renderRecommendationItem(rec))
      )
    : createElement('p', { class: 'no-recommendations' }, ['✅ Aucune recommandation']);

  const content = createElement('div', {}, [
    createElement('h3', {}, ['💡 Recommandations']),
    recList
  ]);

  return Card.create('', content);
}

function renderRecommendationItem(rec) {
  return createElement('div', { class: 'recommendation-item' }, [
    createElement('div', { class: 'rec-header' }, [
      createElement('span', { class: 'rec-priority' }, [`P${rec.priority}`]),
      createElement('strong', {}, [rec.title])
    ]),
    createElement('p', { class: 'rec-description' }, [rec.description]),
    createElement('p', { class: 'rec-action' }, [`➡️ ${rec.action}`])
  ]);
}

/**
 * Carte des actions rapides
 */
function renderQuickActions() {
  const actions = [
    { label: '🔄 Rafraîchir', action: () => window.location.reload() },
    { label: '🔍 Voir Capteurs', action: () => switchToTab('capteurs') },
    { label: '👨‍👧‍👦 Voir Relations', action: () => switchToTab('groups') },
    { label: '🔔 Voir Alertes', action: () => switchToTab('alerts') }
  ];

  const actionsList = createElement('div', { class: 'actions-list' }, 
    actions.map(action => 
      Button.create(action.label, action.action, 'secondary')
    )
  );

  const content = createElement('div', {}, [
    createElement('h3', {}, ['⚡ Actions Rapides']),
    actionsList
  ]);

  return Card.create('', content);
}

function switchToTab(tabName) {
  const tab = document.querySelector(`[data-tab="${tabName}"]`);
  if (tab) {
    tab.click();
  }
}

function formatUptime(seconds) {
  if (!seconds) return 'N/A';
  
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) return `${days}j ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

/**
 * Fallback en cas d'erreur
 */
function renderOverviewFallback(container, error) {
  console.warn('[overviewPanel] Fallback:', error);

  const fallbackCard = Card.create('Vue d\'ensemble', createElement('div', {}, [
    createElement('p', {}, '❌ Impossible de charger la vue d\'ensemble'),
    createElement('p', {}, `Erreur: ${error.message}`)
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadOverviewPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('Erreur de chargement', 'error');
}
