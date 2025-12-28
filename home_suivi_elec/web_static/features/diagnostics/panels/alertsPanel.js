'use strict';

/**
 * Panel d'alertes et recommandations
 * Centralise tous les problèmes détectés dans HSE
 */

import { getDiagnosticGroups } from '../diagnostics.api.js';
import { getSensorsData } from '../diagnostics.api.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[alertsPanel] Module chargé');

/**
 * Point d'entrée principal
 */
export async function loadAlertsPanel(container) {
  try {
    console.log('[alertsPanel] Chargement...');

    // Loader
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Analyse des alertes...')
    ]));

    // Charger les données nécessaires
    const [groupsData, sensorsData] = await Promise.all([
      getDiagnosticGroups(),
      getSensorsData()
    ]);

    // Construire les alertes
    const alerts = buildAlerts(groupsData, sensorsData);

    // Render
    renderAlertsInterface(container, alerts);

    const severity = alerts.length === 0 ? 'success' : 
                    alerts.some(a => a.severity === 'critical') ? 'error' : 'warning';
    showToast(
      alerts.length === 0 ? 'Aucune alerte' : `${alerts.length} alerte(s) détectée(s)`,
      severity
    );

  } catch (error) {
    console.error('[alertsPanel] Erreur:', error);
    renderAlertsFallback(container, error);
  }
}

/**
 * Rendu de l'interface
 */
function renderAlertsInterface(container, alerts) {
  container.innerHTML = '';

  if (alerts.length === 0) {
    const noAlertsDiv = createElement('div', { class: 'no-alerts success-state' }, [
      createElement('div', { class: 'success-icon' }, ['✅']),
      createElement('h3', {}, 'Tout va bien !'),
      createElement('p', {}, 'Aucune alerte détectée. Votre installation HSE est opérationnelle.')
    ]);

    const card = Card.create('Alertes & Recommandations', noAlertsDiv);
    container.appendChild(card);

    const refreshBtn = Button.create(
      'Actualiser',
      () => loadAlertsPanel(container),
      'secondary'
    );
    container.appendChild(refreshBtn);

    return;
  }

  // Stats alertes
  const statsDiv = createElement('div', { class: 'alerts-stats' }, [
    Badge.create(`Total: ${alerts.length}`, 'info'),
    Badge.create(
      `Critiques: ${alerts.filter(a => a.severity === 'critical').length}`,
      'error'
    ),
    Badge.create(
      `Avertissements: ${alerts.filter(a => a.severity === 'warning').length}`,
      'warning'
    ),
    Badge.create(
      `Informations: ${alerts.filter(a => a.severity === 'info').length}`,
      'info'
    )
  ]);

  // Liste des alertes
  const alertsList = createElement('div', { class: 'alerts-list' },
    alerts.map(alert => renderAlertCard(alert))
  );

  const content = createElement('div', { class: 'alerts-content' }, [
    statsDiv,
    alertsList
  ]);

  const mainCard = Card.create('🔔 Alertes & Recommandations', content);
  container.appendChild(mainCard);

  // Bouton refresh
  const refreshBtn = Button.create(
    'Actualiser',
    () => loadAlertsPanel(container),
    'secondary'
  );
  container.appendChild(refreshBtn);
}

/**
 * Rendu d'une carte d'alerte
 */
function renderAlertCard(alert) {
  const severityClass = `alert-${alert.severity}`;
  
  const alertDiv = createElement('div', { class: `alert-card ${severityClass}` });

  // Header
  const header = createElement('div', { class: 'alert-header' }, [
    createElement('span', { class: 'alert-icon' }, [alert.icon]),
    createElement('strong', {}, [alert.title]),
    Badge.create(alert.severity.toUpperCase(), getSeverityVariant(alert.severity))
  ]);

  // Description
  const description = createElement('p', { class: 'alert-description' }, [alert.description]);

  // Détails supplémentaires (si présents)
  const details = alert.details 
    ? createElement('div', { class: 'alert-details' }, [
        createElement('small', {}, [alert.details])
      ])
    : null;

  // Action (bouton)
  const actionBtn = alert.action
    ? Button.create(
        alert.action.label,
        () => {
          if (alert.action.url) {
            window.location.href = alert.action.url;
          } else if (alert.action.callback) {
            alert.action.callback();
          }
        },
        alert.severity === 'critical' ? 'primary' : 'secondary'
      )
    : null;

  alertDiv.appendChild(header);
  alertDiv.appendChild(description);
  if (details) alertDiv.appendChild(details);
  if (actionBtn) alertDiv.appendChild(actionBtn);

  return alertDiv;
}

/**
 * Fallback en cas d'erreur
 */
function renderAlertsFallback(container, error) {
  console.warn('[alertsPanel] Fallback:', error);

  const fallbackCard = Card.create('Alertes', createElement('div', {}, [
    createElement('p', {}, '❌ Impossible de charger les alertes'),
    createElement('p', {}, `Erreur: ${error.message}`)
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadAlertsPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('Erreur de chargement des alertes', 'error');
}

// ---- Logique de construction des alertes ----

/**
 * Construit la liste des alertes depuis les données
 */
function buildAlerts(groupsData, sensorsData) {
  const alerts = [];

  // 1. Aucun parent détecté (critique) - VÉRIFIER EN PREMIER
  if (groupsData.stats.parents === 0) {
    alerts.push({
      severity: 'critical',
      icon: '🚨',
      title: 'Aucun capteur HSE live détecté',
      description: 'Vous devez d\'abord configurer des capteurs de référence pour que HSE fonctionne.',
      details: 'Allez dans Configuration pour sélectionner vos capteurs source.',
      action: {
        label: '⚙️ Aller à Configuration',
        url: '#configuration'
      }
    });
    
    // Si pas de parents, inutile de continuer l'analyse
    return alerts;
  }

  // 2. Capteurs parents unavailable
  const unavailableParents = (groupsData.parents || []).filter(
    p => p.state === 'unavailable' || p.state === 'unknown'
  );

  if (unavailableParents.length > 0) {
    alerts.push({
      severity: 'error',
      icon: '❌',
      title: `${unavailableParents.length} parent(s) indisponible(s)`,
      description: 'Des capteurs HSE live sont dans l\'état "unavailable" ou "unknown".',
      details: `Capteurs: ${unavailableParents.slice(0, 5).map(p => p.entity_id).join(', ')}${unavailableParents.length > 5 ? '...' : ''}`,
      action: {
        label: '🔍 Voir les groupes',
        url: '#diagnostics?tab=groups'
      }
    });
  }

  // 3. Enfants unavailable
  const unavailableChildren = [];
  Object.values(groupsData.children_by_parent || {}).forEach(children => {
    (children || []).forEach(child => {
      if (child.state === 'unavailable' || child.state === 'unknown') {
        unavailableChildren.push(child);
      }
    });
  });

  if (unavailableChildren.length > 0) {
    alerts.push({
      severity: 'warning',
      icon: '⚠️',
      title: `${unavailableChildren.length} capteur(s) cycle(s) indisponible(s)`,
      description: 'Des capteurs cycles (h/d/w/m/y) sont dans l\'état "unavailable" ou "unknown".',
      details: `Premiers capteurs: ${unavailableChildren.slice(0, 5).map(c => c.entity_id).join(', ')}${unavailableChildren.length > 5 ? ` et ${unavailableChildren.length - 5} autres...` : ''}`,
      action: {
        label: '🔍 Voir les groupes',
        url: '#diagnostics?tab=groups'
      }
    });
  }

  // 4. Orphelins
  if (groupsData.stats.orphans > 0) {
    alerts.push({
      severity: 'warning',
      icon: '⚠️',
      title: `${groupsData.stats.orphans} capteur(s) orphelin(s)`,
      description: 'Des capteurs cycles n\'ont pas de parent HSE live correspondant.',
      details: 'Ces capteurs ne seront pas inclus dans les calculs de consommation.',
      action: {
        label: '🔧 Voir les orphelins',
        url: '#diagnostics?tab=groups'
      }
    });
  }

  // 5. Peu d'enfants par parent (info)
  const parentsWithFewChildren = (groupsData.parents || []).filter(p => {
    const children = groupsData.children_by_parent[p.entity_id] || [];
    return children.length > 0 && children.length < 3;
  });

  if (parentsWithFewChildren.length > 0) {
    alerts.push({
      severity: 'info',
      icon: 'ℹ️',
      title: `${parentsWithFewChildren.length} parent(s) avec peu de cycles`,
      description: 'Certains parents ont moins de 3 capteurs cycles associés.',
      details: 'Vérifiez que tous les cycles (h/d/w/m/y) sont bien créés.',
      action: {
        label: '📊 Voir les groupes',
        url: '#diagnostics?tab=groups'
      }
    });
  }

  // 6. Capteurs dupliqués (depuis sensorsData)
  const duplicates = countDuplicates(sensorsData);
  if (duplicates > 0) {
    alerts.push({
      severity: 'warning',
      icon: '🔄',
      title: `${duplicates} capteur(s) dupliqué(s)`,
      description: 'Des capteurs ont été détectés en double dans votre installation.',
      details: 'Cela peut créer des incohérences dans les calculs.',
      action: {
        label: '🔍 Voir les capteurs',
        url: '#diagnostics?tab=capteurs'
      }
    });
  }

  // Tri par sévérité (critical → error → warning → info)
  const severityOrder = { critical: 0, error: 1, warning: 2, info: 3 };
  alerts.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  return alerts;
}


/**
 * Compte les capteurs dupliqués
 */
function countDuplicates(sensorsData) {
  if (!sensorsData) return 0;
  
  let count = 0;
  
  // Parcourir les alternatives pour détecter les doublons
  Object.values(sensorsData.alternatives || {}).forEach(sensors => {
    if (Array.isArray(sensors)) {
      sensors.forEach(s => {
        if (s.is_duplicate) count++;
      });
    }
  });

  return count;
}

/**
 * Variant du badge selon la sévérité
 */
function getSeverityVariant(severity) {
  const variants = {
    critical: 'error',
    error: 'error',
    warning: 'warning',
    info: 'info'
  };
  return variants[severity] || 'secondary';
}
