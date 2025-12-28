'use strict';

/**
 * Panel d'affichage des groupes HSE (parents/enfants/orphelins)
 */

import { getDiagnosticGroups } from '../diagnostics.api.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[groupsPanel] Module chargé');

/**
 * Point d'entrée principal
 */
export async function loadGroupsPanel(container) {
  try {
    console.log('[groupsPanel] Chargement...');

    // Loader
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Chargement des groupes...')
    ]));

    // API call
    const data = await getDiagnosticGroups();

    // Render
    renderGroupsInterface(container, data);

    showToast(`${data.stats.parents} parents, ${data.stats.children} enfants, ${data.stats.orphans} orphelins`, 'success');

  } catch (error) {
    console.error('[groupsPanel] Erreur:', error);
    renderGroupsFallback(container, error);
  }
}

/**
 * Rendu de l'interface
 */
function renderGroupsInterface(container, data) {
  container.innerHTML = '';

  // Stats en haut
  const statsDiv = createElement('div', { class: 'groups-stats' }, [
    Badge.create(`Parents HSE live: ${data.stats.parents}`, 'info'),
    Badge.create(`Capteurs enfants: ${data.stats.children}`, 'success'),
    Badge.create(
      `Orphelins: ${data.stats.orphans}`,
      data.stats.orphans > 0 ? 'warning' : 'success'
    )
  ]);

  // Section Relations Parents → Enfants
  const relationsSection = renderRelationsSection(data.parents, data.children_by_parent);

  // Section Orphelins (si présents)
  const orphansSection = data.orphans.length > 0 
    ? renderOrphansSection(data.orphans)
    : null;

  // Assemblage
  const content = createElement('div', { class: 'groups-content' }, [
    statsDiv,
    relationsSection,
    orphansSection
  ].filter(Boolean));

  const mainCard = Card.create('Groupes & Relations HSE', content);
  container.appendChild(mainCard);

  // Bouton refresh
  const refreshBtn = Button.create(
    'Actualiser',
    () => loadGroupsPanel(container),
    'secondary'
  );
  container.appendChild(refreshBtn);
}

/**
 * Section Relations Parents → Enfants
 */
function renderRelationsSection(parents, childrenByParent) {
  if (!parents || parents.length === 0) {
    return createElement('div', { class: 'no-parents' }, [
      createElement('p', {}, '⚠️ Aucun capteur parent HSE live détecté')
    ]);
  }

  const relationsDiv = createElement('div', { class: 'relations-section' });
  
  const title = createElement('h3', {}, 'Relations Parents → Enfants');
  relationsDiv.appendChild(title);

  parents.forEach(parent => {
    const children = childrenByParent[parent.entity_id] || [];
    const parentCard = renderParentCard(parent, children);
    relationsDiv.appendChild(parentCard);
  });

  return relationsDiv;
}

/**
 * Carte d'un parent avec ses enfants
 */
function renderParentCard(parent, children) {
  const parentDiv = createElement('details', { 
    class: 'parent-group',
    open: children.length === 0 || children.some(c => c.state === 'unavailable')
  });

  // Header (summary)
  const summary = createElement('summary', { class: 'parent-header' }, [
    createElement('span', { class: 'parent-icon' }, ['👨‍👧‍👦']),
    createElement('strong', {}, [parent.friendly_name || parent.entity_id]),
    createElement('code', { class: 'entity-id-small' }, [parent.entity_id]),
    Badge.create(`${children.length} enfant(s)`, children.length > 0 ? 'success' : 'warning'),
    Badge.create(parent.state, getStateVariant(parent.state))
  ]);

  parentDiv.appendChild(summary);

  // Contenu (enfants)
  if (children.length === 0) {
    const noChildren = createElement('div', { class: 'no-children' }, [
      createElement('p', {}, '⚠️ Aucun capteur enfant détecté pour ce parent')
    ]);
    parentDiv.appendChild(noChildren);
  } else {
    const childrenList = createElement('div', { class: 'children-list' }, 
      children.map(child => renderChildRow(child))
    );
    parentDiv.appendChild(childrenList);
  }

  return parentDiv;
}

/**
 * Ligne d'un enfant
 */
function renderChildRow(child) {
  const cycle = extractCycle(child.entity_id);
  const cycleLabel = getCycleLabel(cycle);

  return createElement('div', { class: 'child-row' }, [
    createElement('span', { class: 'child-icon' }, ['📊']),
    createElement('div', { class: 'child-info' }, [
      createElement('strong', {}, [child.friendly_name || child.entity_id]),
      createElement('br'),
      createElement('code', { class: 'entity-id-small' }, [child.entity_id])
    ]),
    Badge.create(cycleLabel, 'info'),
    Badge.create(child.state, getStateVariant(child.state))
  ]);
}

/**
 * Section Orphelins
 */
function renderOrphansSection(orphans) {
  const orphansDiv = createElement('div', { class: 'orphans-section warning-section' });

  const title = createElement('h3', {}, [
    createElement('span', {}, ['⚠️ Capteurs orphelins (', String(orphans.length), ')'])
  ]);

  const description = createElement('p', {}, 
    'Ces capteurs cycles n\'ont pas de parent HSE live correspondant :'
  );

  const orphansList = createElement('div', { class: 'orphans-list' },
    orphans.map(orphan => renderOrphanRow(orphan))
  );

  const actionBtn = Button.create(
    '🔧 Corriger dans Migration',
    () => {
      window.location.href = '#migration?action=fix_orphans';
    },
    'primary'
  );

  orphansDiv.appendChild(title);
  orphansDiv.appendChild(description);
  orphansDiv.appendChild(orphansList);
  orphansDiv.appendChild(actionBtn);

  return orphansDiv;
}

/**
 * Ligne d'un orphelin
 */
function renderOrphanRow(orphan) {
  const expectedParent = guessParentFromChild(orphan.entity_id);

  return createElement('div', { class: 'orphan-row' }, [
    createElement('span', { class: 'orphan-icon' }, ['🔴']),
    createElement('div', { class: 'orphan-info' }, [
      createElement('code', {}, [orphan.entity_id]),
      createElement('br'),
      createElement('small', {}, [`Parent attendu: ${expectedParent}`])
    ]),
    Badge.create(orphan.state, getStateVariant(orphan.state))
  ]);
}

/**
 * Fallback en cas d'erreur
 */
function renderGroupsFallback(container, error) {
  console.warn('[groupsPanel] Fallback:', error);

  const fallbackCard = Card.create('Groupes & Relations', createElement('div', {}, [
    createElement('p', {}, '❌ Impossible de charger les groupes'),
    createElement('p', {}, `Erreur: ${error.message}`),
    createElement('p', {}, 'Endpoint: /api/home_suivi_elec/diagnostic_groups')
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadGroupsPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('Erreur de chargement des groupes', 'error');
}

// ---- Helpers ----

/**
 * Extrait le cycle depuis l'entity_id (_h, _d, _w, _m, _y)
 */
function extractCycle(entityId) {
  if (entityId.endsWith('_h')) return 'h';
  if (entityId.endsWith('_d')) return 'd';
  if (entityId.endsWith('_w')) return 'w';
  if (entityId.endsWith('_m')) return 'm';
  if (entityId.endsWith('_y')) return 'y';
  return 'unknown';
}

/**
 * Label lisible pour un cycle
 */
function getCycleLabel(cycle) {
  const labels = {
    'h': 'Horaire',
    'd': 'Journalier',
    'w': 'Hebdomadaire',
    'm': 'Mensuel',
    'y': 'Annuel'
  };
  return labels[cycle] || cycle;
}

/**
 * Devine le parent attendu depuis un entity_id enfant
 */
function guessParentFromChild(entityId) {
  // sensor.hse_live_salon_h → sensor.hse_live_salon
  if (!entityId.startsWith('sensor.hse_')) return 'unknown';
  
  const parts = entityId.split('_');
  if (parts.length < 4) return 'unknown';
  
  // Retirer le dernier segment (cycle)
  const parentParts = parts.slice(0, -1);
  return parentParts.join('_');
}

/**
 * Variant du badge selon l'état
 */
function getStateVariant(state) {
  if (!state) return 'secondary';
  
  const stateLower = String(state).toLowerCase();
  
  if (stateLower === 'unavailable' || stateLower === 'unknown') {
    return 'error';
  }
  
  if (stateLower === 'on' || !isNaN(parseFloat(state))) {
    return 'success';
  }
  
  return 'secondary';
}
