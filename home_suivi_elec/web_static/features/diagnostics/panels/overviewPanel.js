'use strict';

/**
 * Panel Vue d'ensemble - Dashboard de santé globale
 * Version B: alertes détaillées + cliquables + regroupées
 */

import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[overviewPanel] Module chargé (version B - alertes enrichies)');

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
  if (score >= 60) return 'État correct (Note: C), 2 action(s) recommandée(s).';
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
      status: data.integration?.running ? 'operational' : 'error',
      details: data.integration?.running 
        ? `Uptime: ${formatUptime(data.integration.uptime)}` 
        : 'Non opérationnelle',
      tab: null
    },
    {
      name: '🔌 Capteurs',
      status: data.sensors?.stats?.available > 0 ? 'operational' : 'warning',
      details: `${data.sensors?.stats?.available || 0}/${data.sensors?.stats?.total || 0} disponibles (${data.sensors?.stats?.unavailable || 0} KO)`,
      tab: 'capteurs'
    },
    {
      name: '👨‍👧‍👦 Relations',
      status: data.relations?.stats?.parents_with_children > 0 ? 'operational' : 'warning',
      details: `${data.relations?.stats?.total_parents || 0} parent(s), ${data.relations?.stats?.parents_without_children || 0} sans cycles`,
      tab: 'groups'
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
    component.status === 'warning' ? '⚠️ ATTENTION' : '❌ ERREUR',
    component.status === 'operational' ? 'success' : 
    component.status === 'warning' ? 'warning' : 'error'
  );

  const item = createElement('div', { class: 'component-item' }, [
    createElement('div', { class: 'component-info' }, [
      createElement('strong', {}, [component.name]),
      createElement('span', { class: 'component-details' }, [component.details])
    ]),
    statusBadge
  ]);

  // Rendre cliquable si tab défini
  if (component.tab && component.status !== 'operational') {
    item.classList.add('component-clickable');
    item.style.cursor = 'pointer';
    item.addEventListener('click', () => switchToTab(component.tab));
  }

  return item;
}

/**
 * Carte des alertes prioritaires (VERSION B: détaillées + regroupées + cliquables)
 */
function renderPriorityAlerts(data) {
  const allIssues = [
    ...(data.integration?.issues || []),
    ...(data.sensors?.issues || []),
    ...(data.relations?.issues || [])
  ];

  // Regroupement par type
  const grouped = groupIssuesByType(allIssues);

  // Tri par sévérité
  const severityOrder = { critical: 0, error: 1, warning: 2, info: 3 };
  const sortedGroups = Object.values(grouped).sort((a, b) => 
    severityOrder[a.severity] - severityOrder[b.severity]
  );

  const alertsList = sortedGroups.length > 0
    ? createElement('div', { class: 'alerts-list-grouped' }, 
        sortedGroups.map(group => renderGroupedAlertItem(group))
      )
    : createElement('p', { class: 'no-alerts' }, ['✅ Aucune alerte prioritaire']);

  const content = createElement('div', {}, [
    createElement('h3', {}, ['🔔 Alertes Prioritaires']),
    alertsList
  ]);

  return Card.create('', content);
}

/**
 * Regroupe les issues par type + entities
 */
function groupIssuesByType(issues) {
  const groups = {};

  issues.forEach(issue => {
    const key = getIssueKey(issue);
    
    if (!groups[key]) {
      groups[key] = {
        type: key,
        severity: issue.severity,
        message: issue.message,
        entities: [],
        tab: getIssueTab(issue)
      };
    }

    // Extraire entity_id si présent dans le message
    const entityMatch = issue.message.match(/sensor\.[a-z0-9_]+/i);
    if (entityMatch) {
      groups[key].entities.push({
        entity_id: entityMatch[0],
        friendly_name: extractFriendlyName(issue.message) || entityMatch[0]
      });
    } else {
      // Issue générique sans entité
      groups[key].entities.push({ generic: true });
    }
  });

  return groups;
}

function getIssueKey(issue) {
  if (issue.message.includes('Parent sans')) return 'parent_no_cycles';
  if (issue.message.includes('état unknown')) return 'sensor_unknown';
  if (issue.message.includes('unavailable')) return 'sensor_unavailable';
  if (issue.message.includes('orphelin')) return 'orphan_cycles';
  return 'other';
}

function getIssueTab(issue) {
  if (issue.message.includes('Parent') || issue.message.includes('orphelin')) return 'groups';
  if (issue.message.includes('Capteur')) return 'capteurs';
  return 'alerts';
}

function extractFriendlyName(message) {
  // Tente d'extraire le friendly name entre parenthèses ou avant "sensor."
  const match = message.match(/([^(]+)\s*\(/);
  return match ? match[1].trim() : null;
}

/**
 * Rendu d'une alerte regroupée
 */
function renderGroupedAlertItem(group) {
  const severityIcon = {
    critical: '🔴',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };

  const count = group.entities.length;
  const isGeneric = group.entities[0]?.generic;

  // Message groupé
  let displayMessage = group.message;
  if (!isGeneric && count > 1) {
    displayMessage = `${count}× ${group.message}`;
  }

  // Liste entités (si plusieurs)
  const entitiesList = !isGeneric && count > 0 && count <= 3
    ? createElement('div', { class: 'alert-entities' },
        group.entities.map(e => 
          createElement('code', { class: 'entity-badge' }, [
            e.friendly_name || e.entity_id
          ])
        )
      )
    : null;

  // Bouton "Voir"
  const actionBtn = Button.create(
    count > 3 ? `Voir ${count} →` : 'Voir →',
    () => {
      if (group.tab === 'groups') {
        switchToTab('groups', { filter: group.type });
      } else {
        switchToTab(group.tab);
      }
    },
    'secondary'
  );
  actionBtn.classList.add('alert-action-btn');

  const item = createElement('div', { class: `alert-item-grouped alert-${group.severity}` }, [
    createElement('div', { class: 'alert-header' }, [
      createElement('span', { class: 'alert-icon' }, [severityIcon[group.severity] || 'ℹ️']),
      createElement('span', { class: 'alert-message' }, [displayMessage])
    ]),
    entitiesList,
    actionBtn
  ].filter(Boolean));

  return item;
}

/**
 * Carte des recommandations (VERSION B: actionnable)
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
  const actionBtn = rec.action_tab 
    ? Button.create('Action →', () => switchToTab(rec.action_tab), 'secondary')
    : null;

  return createElement('div', { class: 'recommendation-item' }, [
    createElement('div', { class: 'rec-header' }, [
      createElement('span', { class: 'rec-priority' }, [`P${rec.priority}`]),
      createElement('strong', {}, [rec.title])
    ]),
    createElement('p', { class: 'rec-description' }, [rec.description]),
    createElement('p', { class: 'rec-action' }, [`➡️ ${rec.action}`]),
    actionBtn
  ].filter(Boolean));
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

/**
 * Navigation vers un onglet (avec params optionnels)
 */
function switchToTab(tabName, params = {}) {
  const tab = document.querySelector(`[data-tab="${tabName}"]`);
  if (tab) {
    tab.click();
    
    // Passer les params via localStorage temporaire si nécessaire
    if (Object.keys(params).length > 0) {
      localStorage.setItem('hse_tab_params', JSON.stringify({ tab: tabName, ...params }));
      setTimeout(() => localStorage.removeItem('hse_tab_params'), 5000);
    }
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
