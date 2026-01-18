'use strict';

/**
 * Panel d'affichage des groupes HSE (parents/enfants/orphelins)
 * Vue compacte 3-4 colonnes, filtres stats cliquables, scroll interne
 */

import { getDiagnosticGroups, createMissingParents } from '../diagnostics.api.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[groupsPanel] Module chargé (vue compacte + filtres)');

// État UI filtres
const uiState = {
  filterActive: 'all',   // all | active | inactive
  filterType: 'all',     // all | power | energy | orphans | cost
};

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

    showToast(
      `${data.stats.total_parents} parents (${data.stats.active_parents} actifs), ${data.stats.total_children} enfants`,
      'success'
    );

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

  // Stats cliquables
  const statsDiv = createElement('div', { class: 'groups-stats clickable' }, [
    createStatBadge(`Parents: ${data.stats.total_parents}`, 'info', () => resetFilters()),
    createStatBadge(`Actifs: ${data.stats.active_parents}`, 'success', () => setActiveFilter('active')),
    createStatBadge(`Inactifs: ${data.stats.inactive_parents}`, 'secondary', () => setActiveFilter('inactive')),
    createStatBadge(`Power: ${data.stats.power_parents}`, 'warning', () => setTypeFilter('power')),
    createStatBadge(`Energy: ${data.stats.energy_parents}`, 'info', () => setTypeFilter('energy')),
    createStatBadge(`Enfants: ${data.stats.total_children}`, 'success', () => resetFilters()),
    createStatBadge(
      `Orphelins: ${data.stats.orphans}`,
      data.stats.orphans > 0 ? 'warning' : 'success',
      () => setTypeFilter('orphans')
    ),
    createStatBadge(`Coût actif: ${data.stats.cost_enabled_children}`, 'info', () => setTypeFilter('cost')),
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

  const mainCard = Card.create('Groupes & Relations (Diagnostic)', content);

  // Bouton refresh
  const refreshBtn = Button.create(
    'Actualiser',
    () => loadGroupsPanel(container),
    'secondary'
  );

  // Option A: wrapper (card + actions)
  const panel = createElement('div', { class: 'diagnostics-panel' }, [
    mainCard,
    refreshBtn
  ]);

  container.appendChild(panel);

  // Appliquer filtres par défaut
  setTimeout(() => applyFilters(), 50);
}

/**
 * Filtres rapides (ajout après stats cliquables)
 */
function renderQuickFilters() {
  const filters = [
    { label: 'Tous', action: () => resetFilters(), variant: 'secondary' },
    { label: '⚠️ Sans cycles uniquement', action: () => filterNoCycles(), variant: 'warning' },
    { label: '🔴 Unavailable uniquement', action: () => filterUnavailable(), variant: 'error' },
    { label: '✓ Avec cycles uniquement', action: () => filterWithCycles(), variant: 'success' },
  ];

  return createElement('div', { class: 'quick-filters' }, 
    filters.map(f => Button.create(f.label, f.action, f.variant))
  );
}

function filterNoCycles() {
  const container = document.querySelector('.parents-grid');
  if (!container) return;
  
  container.querySelectorAll('.parent-group').forEach(card => {
    const cyclesText = card.querySelector('summary').textContent;
    const cyclesMatch = cyclesText.match(/(\d+)\s*cycle/i);
    const cyclesCount = cyclesMatch ? parseInt(cyclesMatch[1]) : 0;
    card.style.display = cyclesCount === 0 ? '' : 'none';
  });

  // Forcer l'ouverture des cards sans cycles
  container.querySelectorAll('.parent-group[style=""]').forEach(card => {
    card.setAttribute('open', 'true');
  });
}

function filterUnavailable() {
  const container = document.querySelector('.parents-grid');
  if (!container) return;
  
  container.querySelectorAll('.parent-group').forEach(card => {
    const hasUnavailable = card.querySelector('.badge.error') !== null;
    card.style.display = hasUnavailable ? '' : 'none';
  });
}

function filterWithCycles() {
  const container = document.querySelector('.parents-grid');
  if (!container) return;
  
  container.querySelectorAll('.parent-group').forEach(card => {
    const cyclesText = card.querySelector('summary').textContent;
    const cyclesMatch = cyclesText.match(/(\d+)\s*cycle/i);
    const cyclesCount = cyclesMatch ? parseInt(cyclesMatch[1]) : 0;
    card.style.display = cyclesCount > 0 ? '' : 'none';
  });
}


/**
 * Section Relations Parents → Enfants
 */
function renderRelationsSection(parents, childrenByParent) {
  if (!parents || parents.length === 0) {
    return createElement('div', { class: 'no-parents' }, [
      createElement('p', {}, '⚠️ Aucun capteur parent détecté')
    ]);
  }

  const relationsDiv = createElement('div', { class: 'relations-section' });
  
  const title = createElement('h3', {}, 'Relations Parents → Enfants Cycles');
  relationsDiv.appendChild(title);

  // NOUVEAU: Quick filters
  const quickFilters = renderQuickFilters();
  relationsDiv.appendChild(quickFilters);

  // Grille parents
  const parentsContainer = createElement('div', { class: 'parents-grid' });
  
  parents.forEach(parent => {
    const childrenData = childrenByParent[parent.entity_id] || { cycles: {} };
    const parentCard = renderParentCard(parent, childrenData);
    parentsContainer.appendChild(parentCard);
  });

  relationsDiv.appendChild(parentsContainer);

  return relationsDiv;
}

/**
 * Carte d'un parent avec ses enfants cycles
 */
function renderParentCard(parent, childrenData) {
  // Aplatir tous les cycles
  const allChildren = [];
  Object.entries(childrenData.cycles || {}).forEach(([cycle, children]) => {
    allChildren.push(...children.map(c => ({ ...c, cycle })));
  });

  const hasCost = allChildren.some(c => c.cost_enabled);

  const parentDiv = createElement('details', { 
    class: `parent-group ${parent.active ? 'parent-active' : 'parent-inactive'}`,
    'data-active': String(parent.active),
    'data-type': parent.type,
    'data-has-cost': String(hasCost),
    open: false
  });

  // Header (summary)
  const statusBadge = parent.active 
    ? Badge.create('✓ Actif', 'success')
    : Badge.create('○ Inactif', 'secondary');

  const summary = createElement('summary', { class: 'parent-header' }, [
    createElement('span', { class: 'parent-icon' }, [parent.type === 'power' ? '⚡' : '🔋']),
    createElement('strong', {}, [parent.friendly_name || parent.entity_id]),
    Badge.create(parent.type, parent.type === 'power' ? 'warning' : 'info'),
    Badge.create(parent.integration || '?', 'secondary'),
    statusBadge,
    Badge.create(`${allChildren.length} cycle(s)`, allChildren.length > 0 ? 'success' : 'warning'),
  ]);

  parentDiv.appendChild(summary);

  // Métadonnées parent (rapide)
  const metaDiv = createElement('div', { class: 'parent-meta' }, [
    createElement('div', {}, [
      createElement('strong', {}, ['Sélectionné: ']),
      createElement('span', {}, [parent.selected ? '✓ Oui' : '✗ Non'])
    ]),
    createElement('div', {}, [
      createElement('strong', {}, ['Activé: ']),
      createElement('span', {}, [parent.enabled ? '✓ Oui' : '✗ Non'])
    ]),
    parent.related_power ? createElement('div', {}, [
      createElement('strong', {}, ['Power lié: ']),
      createElement('code', {}, [parent.related_power])
    ]) : null,
    parent.related_energy ? createElement('div', {}, [
      createElement('strong', {}, ['Energy lié: ']),
      createElement('code', {}, [parent.related_energy])
    ]) : null,
    createElement('div', {}, [
      createElement('strong', {}, ['État: ']),
      Badge.create(parent.state, getStateVariant(parent.state))
    ])
  ].filter(Boolean));

  parentDiv.appendChild(metaDiv);

  // Contenu (enfants par cycle) - SCROLLABLE
  if (allChildren.length === 0) {
    const noChildren = createElement('div', { class: 'no-children' }, [
      createElement('p', {}, '⚠️ Aucun capteur cycle HSE détecté')
    ]);
    parentDiv.appendChild(noChildren);
  } else {
    const cyclesDiv = createElement('div', { class: 'cycles-container' });
    
    // Grouper par cycle
    const cycles = ['hourly', 'daily', 'weekly', 'monthly', 'yearly'];
    cycles.forEach(cycle => {
      const cycleChildren = (childrenData.cycles || {})[cycle] || [];
      if (cycleChildren.length > 0) {
        const cycleSection = renderCycleSection(cycle, cycleChildren);
        cyclesDiv.appendChild(cycleSection);
      }
    });
    
    const scrollWrap = createElement('div', { class: 'parent-details-scroll' }, [cyclesDiv]);
    parentDiv.appendChild(scrollWrap);
  }

  return parentDiv;
}

/**
 * Section pour un cycle donné
 */
function renderCycleSection(cycle, children) {
  const cycleDiv = createElement('div', { class: 'cycle-section' });
  
  const cycleHeader = createElement('h4', { class: 'cycle-header' }, [
    createElement('span', {}, ['📊 ']),
    getCycleLabel(cycle),
    Badge.create(`${children.length}`, 'info')
  ]);
  
  cycleDiv.appendChild(cycleHeader);
  
  const childrenList = createElement('div', { class: 'children-list' }, 
    children.map(child => renderChildRow(child))
  );
  
  cycleDiv.appendChild(childrenList);
  
  return cycleDiv;
}

/**
 * Ligne d'un enfant
 */
function renderChildRow(child) {
  return createElement('div', { class: 'child-row' }, [
    createElement('span', { class: 'child-icon' }, ['📊']),
    createElement('div', { class: 'child-info' }, [
      createElement('strong', {}, [child.friendly_name || child.entity_id]),
      createElement('br'),
      createElement('code', { class: 'entity-id-small' }, [child.entity_id])
    ]),
    Badge.create(child.state, getStateVariant(child.state)),
    child.cost_enabled 
      ? Badge.create('💰 Coût', 'success')
      : Badge.create('○ Coût', 'secondary'),
    child.cost_entity_id 
      ? createElement('code', { class: 'cost-entity' }, [child.cost_entity_id])
      : null
  ].filter(Boolean));
}

/**
 * Section Orphelins (VERSION B: bouton auto-create)
 */
function renderOrphansSection(orphans) {
  const orphansDiv = createElement('div', { class: 'orphans-section' });

  const title = createElement('h3', {}, [
    createElement('span', {}, ['⚠️ Capteurs orphelins (', String(orphans.length), ')'])
  ]);

  const description = createElement('p', {}, 
    'Ces capteurs cycles HSE n\'ont pas de parent power/energy correspondant'
  );

  const orphansList = createElement('div', { class: 'orphans-list' },
    orphans.map(orphan => renderOrphanRow(orphan))
  );

  // Boutons d'action
  const actionsDiv = createElement('div', { class: 'orphans-actions' }, [
    Button.create(
      `🔧 Créer ${orphans.length} parents manquants`,
      () => autoCreateMissingParents(orphans),
      'primary'
    ),
    Button.create(
      '📋 Copier liste entity_id',
      () => copyOrphansToClipboard(orphans),
      'secondary'
    )
  ]);

  orphansDiv.appendChild(title);
  orphansDiv.appendChild(description);
  orphansDiv.appendChild(orphansList);
  orphansDiv.appendChild(actionsDiv);

  return orphansDiv;
}

/**
 * Auto-création des parents manquants (appel API backend)
 */
async function autoCreateMissingParents(orphans) {
  const confirmMsg = `Créer automatiquement ${orphans.length} capteurs parents manquants ?\n\nCela va générer des utility_meter avec source par défaut.\nVous pourrez les configurer ensuite dans Migration capteurs.`;
  
  if (!confirm(confirmMsg)) return;

  try {
    showToast(`Création de ${orphans.length} parents en cours...`, 'info');

    // Appel via l'API centralisée
    const result = await createMissingParents(orphans.map(o => o.entity_id));

    if (result.success) {
      showToast(`✅ ${result.created_count} parents créés avec succès`, 'success');
      
      // Reload après 2s pour voir les nouveaux parents
      setTimeout(() => {
        const container = document.querySelector('[data-panel="groups"]');
        if (container) {
          loadGroupsPanel(container);
        }
      }, 2000);
    }

  } catch (error) {
    console.error('[autoCreateMissingParents] Erreur:', error);
    showToast(`❌ Erreur: ${error.message}`, 'error');
  }
}


/**
 * Copier la liste des orphelins dans le presse-papier
 */
function copyOrphansToClipboard(orphans) {
  const text = orphans.map(o => o.entity_id).join('\n');
  navigator.clipboard.writeText(text).then(() => {
    showToast('Liste copiée dans le presse-papier', 'success');
  }).catch(err => {
    console.error('[copyOrphansToClipboard]', err);
    showToast('Échec copie', 'error');
  });
}

/**
 * Ligne d'un orphelin
 */
function renderOrphanRow(orphan) {
  return createElement('div', { class: 'orphan-row' }, [
    createElement('span', { class: 'orphan-icon' }, ['🔴']),
    createElement('div', { class: 'orphan-info' }, [
      createElement('code', {}, [orphan.entity_id]),
      createElement('br'),
      createElement('small', {}, [`Cycle: ${getCycleLabel(orphan.cycle)}`])
    ]),
    Badge.create(orphan.state, getStateVariant(orphan.state)),
    orphan.cost_enabled 
      ? Badge.create('💰', 'success')
      : null
  ].filter(Boolean));
}

/**
 * Fallback en cas d'erreur
 */
function renderGroupsFallback(container, error) {
  console.warn('[groupsPanel] Fallback:', error);

  const fallbackCard = Card.create('Groupes & Relations', createElement('div', {}, [
    createElement('p', {}, '❌ Impossible de charger les groupes'),
    createElement('p', {}, `Erreur: ${error.message || error}`),
    createElement('p', {}, 'Endpoint: /api/home_suivi_elec/diagnostic_groups')
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadGroupsPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('Erreur de chargement des groupes', 'error');
}

// ---- Filtres ----

function createStatBadge(label, variant, onClick) {
  const b = Badge.create(label, variant);
  b.classList.add('stat-badge');
  b.addEventListener('click', (e) => {
    e.preventDefault();
    onClick();
  });
  return b;
}

function setActiveFilter(mode) {
  uiState.filterActive = mode;
  uiState.filterType = 'all'; // reset type
  applyFilters();
}

function setTypeFilter(mode) {
  uiState.filterType = mode;
  uiState.filterActive = 'all'; // reset active
  applyFilters();
}

function resetFilters() {
  uiState.filterActive = 'all';
  uiState.filterType = 'all';
  applyFilters();
}

function applyFilters() {
  const container = document.querySelector('.parents-grid');
  if (!container) return;

  // reset
  container.querySelectorAll('.parent-group').forEach(card => (card.style.display = ''));

  // active filter
  if (uiState.filterActive !== 'all') {
    container.querySelectorAll('.parent-group').forEach(card => {
      const isActive = card.dataset.active === 'true';
      if (uiState.filterActive === 'active' && !isActive) card.style.display = 'none';
      if (uiState.filterActive === 'inactive' && isActive) card.style.display = 'none';
    });
  }

  // type filter
  if (uiState.filterType !== 'all') {
    container.querySelectorAll('.parent-group').forEach(card => {
      const t = card.dataset.type;
      const hasCost = card.dataset.hasCost === 'true';
      
      if (uiState.filterType === 'power' && t !== 'power') card.style.display = 'none';
      if (uiState.filterType === 'energy' && t !== 'energy') card.style.display = 'none';
      if (uiState.filterType === 'cost' && !hasCost) card.style.display = 'none';
    });
  }

  // orphans filter
  const orphansSection = document.querySelector('.orphans-section');
  if (orphansSection) {
    orphansSection.style.display = 
      (uiState.filterType === 'orphans' || uiState.filterType === 'all') ? '' : 'none';
  }
}

// ---- Helpers ----

function getCycleLabel(cycle) {
  const labels = {
    'hourly': '⏱️ Horaire',
    'daily': '📅 Journalier',
    'weekly': '📆 Hebdo.',
    'monthly': '📊 Mensuel',
    'yearly': '📈 Annuel',
  };
  return labels[cycle] || cycle;
}

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
