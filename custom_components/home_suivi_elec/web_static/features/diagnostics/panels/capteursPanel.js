'use strict';

/**
 * Panel des capteurs enrichi avec diagnostics
 */

import { getSensorsEnrichedData } from '../diagnostics.api.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';

console.info('[capteursPanel] Module chargé');

// État du filtre
let currentFilter = 'all';

/**
 * Point d'entrée principal
 */
export async function loadCapteursPanel(container) {
  try {
    console.log('[capteursPanel] Chargement...');

    // Loader
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Analyse des capteurs...')
    ]));

    // Charger les données enrichies
    const data = await getSensorsEnrichedData();

    // Render
    renderCapteursInterface(container, data);

    showToast('Capteurs analysés avec succès', 'success');

  } catch (error) {
    console.error('[capteursPanel] Erreur:', error);
    renderCapteursFallback(container, error);
  }
}

/**
 * Rendu de l'interface
 */
function renderCapteursInterface(container, data) {
  container.innerHTML = '';

  // Calculer les stats
  const stats = calculateStats(data);

  // Header avec stats
  const statsDiv = createElement('div', { class: 'capteurs-stats' }, [
    Badge.create(`Total: ${stats.total}`, 'info'),
    Badge.create(`✅ Disponibles: ${stats.available}`, 'success'),
    Badge.create(`❌ Unavailable: ${stats.unavailable}`, 'error'),
    Badge.create(`⚠️ Unknown: ${stats.unknown}`, 'warning'),
    Badge.create(`👁️ Disabled: ${stats.disabled}`, 'secondary'),
    Badge.create(`🔄 Restored: ${stats.restored}`, 'warning')
  ]);

  // Barre de filtres
  const filtersDiv = createElement('div', { class: 'capteurs-filters' }, [
    createFilterButton('all', 'Tous', stats.total),
    createFilterButton('available', 'Disponibles', stats.available),
    createFilterButton('unavailable', 'Unavailable', stats.unavailable),
    createFilterButton('problematic', 'Problématiques', stats.unavailable + stats.unknown + stats.disabled + stats.restored)
  ]);

  // Liste des capteurs
  const capteursList = createElement('div', { class: 'capteurs-list', id: 'capteurs-list' });
  renderFilteredCapteurs(capteursList, data, currentFilter);

  // Contenu principal
  const content = createElement('div', { class: 'capteurs-content' }, [
    statsDiv,
    filtersDiv,
    capteursList
  ]);

  const mainCard = Card.create('🔌 Capteurs Groupés', content);
  container.appendChild(mainCard);

  // Bouton refresh
  const refreshBtn = Button.create(
    'Actualiser',
    () => loadCapteursPanel(container),
    'secondary'
  );
  container.appendChild(refreshBtn);
}

/**
 * Crée un bouton de filtre
 */
function createFilterButton(filter, label, count) {
  const btn = Button.create(
    `${label} (${count})`,
    () => {
      currentFilter = filter;
      
      // Mettre à jour l'état actif des boutons
      document.querySelectorAll('.capteurs-filters button').forEach(b => {
        b.classList.remove('active');
      });
      
      // Marquer le bouton comme actif
      document.querySelectorAll('.capteurs-filters button').forEach(b => {
        if (b.textContent.includes(label)) {
          b.classList.add('active');
        }
      });
      
      // Re-render la liste filtrée
      const listContainer = document.getElementById('capteurs-list');
      if (listContainer) {
        const dataCache = listContainer._sensorsDataCache; // Données stockées sur le container
        if (dataCache) {
          renderFilteredCapteurs(listContainer, dataCache, filter);
        }
      }
    },
    filter === currentFilter ? 'primary' : 'secondary'
  );
  
  if (filter === currentFilter) {
    btn.classList.add('active');
  }
  
  return btn;
}


/**
 * Rendu de la liste filtrée
 */
function renderFilteredCapteurs(container, data, filter) {
  container.innerHTML = '';
  
  // Stocker les données en cache sur le container lui-même
  container._sensorsDataCache = data;
  
  // Collecter tous les capteurs
  const allSensors = [];
  if (data.alternatives) {
    Object.values(data.alternatives).forEach(sensors => {
      allSensors.push(...sensors);
    });
  }
  
  // Filtrer selon le filtre actif
  let filteredSensors = allSensors;
  
  switch (filter) {
    case 'available':
      filteredSensors = allSensors.filter(s => s.state_type === 'available');
      break;
    case 'unavailable':
      filteredSensors = allSensors.filter(s => s.state_type === 'unavailable');
      break;
    case 'problematic':
      filteredSensors = allSensors.filter(s => 
        ['unavailable', 'unknown', 'disabled', 'restored'].includes(s.state_type)
      );
      break;
  }
  
  if (filteredSensors.length === 0) {
    container.appendChild(createElement('p', { class: 'no-results' }, [
      `Aucun capteur ${filter !== 'all' ? `de type "${filter}"` : ''}`
    ]));
    return;
  }
  
  // Afficher les capteurs
  filteredSensors.forEach(sensor => {
    container.appendChild(renderSensorCard(sensor, data));
  });
}


/**
 * Rendu d'une carte capteur enrichie (repliable)
 */
function renderSensorCard(sensor, allData) {
  // <details> replié par défaut (pas d'attribut open)
  const card = createElement('details', { class: `sensor-card sensor-${sensor.state_type}` });

  // Header compact (plié) : nom + badges + mini valeur
  const summary = createElement('summary', { class: 'sensor-summary' }, [
    createElement('strong', {}, [sensor.friendly_name || sensor.entity_id]),
    getStateBadge(sensor),
    createElement('span', { class: 'sensor-mini-value' }, [String(sensor.state ?? 'N/A')]),
    sensor.is_hse_live ? Badge.create('HSE Live', 'info') : null,
    sensor.is_duplicate ? Badge.create('Doublon', 'warning') : null
  ].filter(Boolean));

  // Entity ID
  const entityIdDiv = createElement('div', { class: 'sensor-entity-id' }, [
    createElement('code', {}, [sensor.entity_id])
  ]);

  // Détails (état, intégration, dernière MAJ)
  const detailsDiv = createElement('div', { class: 'sensor-details' }, [
    createElement('div', { class: 'detail-row' }, [
      createElement('span', { class: 'detail-label' }, ['État:']),
      createElement('span', { class: 'detail-value' }, [sensor.state || 'N/A'])
    ]),
    createElement('div', { class: 'detail-row' }, [
      createElement('span', { class: 'detail-label' }, ['Intégration:']),
      createElement('span', { class: 'detail-value' }, [sensor.integration || 'Inconnue'])
    ]),
    createElement('div', { class: 'detail-row' }, [
      createElement('span', { class: 'detail-label' }, ['Dernière MAJ:']),
      createElement('span', { class: 'detail-value' }, [sensor.last_update_relative])
    ])
  ]);

  // Si HSE Live, afficher info sur la source
  let sourceInfo = null;
  if (sensor.is_hse_live && sensor.source_entity_id) {
    const sourceExists = checkIfSourceExists(sensor.source_entity_id, allData);
    sourceInfo = createElement('div', { class: `source-info ${sourceExists ? 'source-ok' : 'source-missing'}` }, [
      createElement('span', {}, ['📡 Source: ']),
      createElement('code', {}, [sensor.source_entity_id]),
      sourceExists
        ? createElement('span', { class: 'source-status' }, [' ✅'])
        : createElement('span', { class: 'source-status' }, [' ❌ Manquante'])
    ]);
  }

  // Bouton diagnostiquer si problématique
  let actionBtn = null;
  if (['unavailable', 'unknown', 'disabled', 'restored'].includes(sensor.state_type)) {
    actionBtn = Button.create(
      '🔍 Diagnostiquer',
      () => diagnoseSensor(sensor, allData),
      'primary'
    );
  }

  // Contenu déplié
  const body = createElement('div', { class: 'sensor-body' }, [
    entityIdDiv,
    detailsDiv,
    sourceInfo,
    actionBtn
  ].filter(Boolean));

  card.appendChild(summary);
  card.appendChild(body);

  return card;
}

/**
 * Retourne le badge d'état approprié
 */
function getStateBadge(sensor) {
  const badges = {
    available: Badge.create('✅ Disponible', 'success'),
    unavailable: Badge.create('❌ Unavailable', 'error'),
    unknown: Badge.create('⚠️ Unknown', 'warning'),
    disabled: Badge.create('👁️ Disabled', 'secondary'),
    restored: Badge.create('🔄 Restored', 'warning')
  };
  
  return badges[sensor.state_type] || Badge.create('❓ Inconnu', 'secondary');
}

/**
 * Vérifie si la source d'un capteur HSE Live existe
 */
function checkIfSourceExists(sourceEntityId, allData) {
  if (!allData.alternatives) return false;
  
  const allSensors = [];
  Object.values(allData.alternatives).forEach(sensors => {
    allSensors.push(...sensors);
  });
  
  return allSensors.some(s => s.entity_id === sourceEntityId);
}

/**
 * Diagnostique un capteur problématique
 */
function diagnoseSensor(sensor, allData) {
  let diagnosis = '';
  let solution = '';
  
  // CAS 1 : État UNKNOWN (N/A)
  if (sensor.state_type === 'unknown' || sensor.state === 'N/A') {
    diagnosis = `⚠️ Le capteur "${sensor.friendly_name}" est en état UNKNOWN (N/A).`;
    
    if (sensor.integration === 'template') {
      solution = `Ce capteur Template n'a pas encore reçu de valeur. Vérifiez que :
      
1. ✅ Le template est correctement configuré dans configuration.yaml
2. ✅ Les capteurs sources existent et ont des valeurs
3. ✅ La syntaxe du template est correcte ({{ states(...) }})
4. ✅ Home Assistant a été redémarré après la configuration

💡 Astuce : Allez dans Outils Dev → États pour voir si le capteur existe et a une valeur.`;
    } else {
      solution = `Le capteur n'a pas encore reçu de valeur depuis son intégration "${sensor.integration}".

Vérifications possibles :
1. L'appareil est-il alimenté et connecté ?
2. L'intégration fonctionne-t-elle correctement ?
3. Le capteur existe-t-il réellement sur l'appareil ?

💡 Astuce : Allez dans Paramètres → Appareils et Services → "${sensor.integration}" pour vérifier.`;
    }
  }
  
  // CAS 2 : État UNAVAILABLE
  else if (sensor.state_type === 'unavailable') {
    if (sensor.is_hse_live) {
      const sourceExists = checkIfSourceExists(sensor.source_entity_id, allData);
      if (!sourceExists) {
        diagnosis = `❌ Le capteur HSE Live "${sensor.friendly_name}" est unavailable car le capteur source "${sensor.source_entity_id}" n'existe pas.`;
        solution = `Créez le capteur source dans l'intégration Template ou via l'onglet Détection.
        
Étapes :
1. Allez dans Configuration → Entités
2. Cherchez "${sensor.source_entity_id}"
3. Si absent, créez-le dans l'intégration Template
4. Ou utilisez l'onglet Détection pour le détecter automatiquement`;
      } else {
        diagnosis = `⚠️ Le capteur HSE Live "${sensor.friendly_name}" est unavailable, mais le capteur source existe.`;
        solution = `Vérifiez les logs Home Assistant pour voir les erreurs de création du capteur :

1. Allez dans Paramètres → Système → Logs
2. Cherchez "home_suivi_elec" dans les logs
3. Vérifiez s'il y a des erreurs de création de capteur

💡 Il peut y avoir un problème de configuration ou de permissions.`;
      }
    } else {
      diagnosis = `❌ Le capteur "${sensor.friendly_name}" est unavailable.`;
      solution = `Vérifiez que l'intégration d'origine "${sensor.integration}" fonctionne correctement :

1. Allez dans Paramètres → Appareils et Services
2. Cherchez l'intégration "${sensor.integration}"
3. Vérifiez que l'appareil est en ligne
4. Si nécessaire, supprimez et réajoutez l'intégration`;
    }
  }
  
  // CAS 3 : État DISABLED
  else if (sensor.state_type === 'disabled') {
    diagnosis = `👁️ Le capteur "${sensor.friendly_name}" est désactivé.`;
    solution = `Pour le réactiver :

1. Allez dans Configuration → Entités
2. Cherchez "${sensor.entity_id}"
3. Cliquez sur l'entité
4. Cliquez sur "Activer"
5. Redémarrez Home Assistant si nécessaire`;
  }
  
  // CAS 4 : État RESTORED
  else if (sensor.state_type === 'restored') {
    diagnosis = `🔄 Le capteur "${sensor.friendly_name}" a été restauré depuis un ancien état.`;
    solution = `Ce capteur a été restauré depuis la base de données, mais n'a pas encore reçu de nouvelle valeur.

Solutions :
1. Redémarrez Home Assistant pour réinitialiser son état
2. Vérifiez que l'intégration "${sensor.integration}" fonctionne correctement
3. Si le problème persiste, supprimez et recréez le capteur`;
  }
  
  // CAS 5 : État inconnu (fallback)
  else {
    diagnosis = `❓ État du capteur "${sensor.friendly_name}" : ${sensor.state}`;
    solution = `Cause inconnue. Consultez :
    
1. Les logs Home Assistant (Paramètres → Système → Logs)
2. La documentation de l'intégration "${sensor.integration}"
3. Le forum communautaire Home Assistant

💡 Essayez de redémarrer Home Assistant et l'appareil source.`;
  }
  
  // Afficher dans une alerte stylisée
  const message = `🔍 Diagnostic de ${sensor.entity_id}\n\n${diagnosis}\n\n💡 Solution:\n${solution}`;
  
  alert(message);
  
  console.log('[capteursPanel] Diagnostic:', { sensor, diagnosis, solution });
}


/**
 * Calcule les statistiques des capteurs
 */
function calculateStats(data) {
  const stats = {
    total: 0,
    available: 0,
    unavailable: 0,
    unknown: 0,
    disabled: 0,
    restored: 0
  };
  
  if (data.alternatives) {
    Object.values(data.alternatives).forEach(sensors => {
      sensors.forEach(sensor => {
        stats.total++;
        stats[sensor.state_type]++;
      });
    });
  }
  
  return stats;
}

/**
 * Fallback en cas d'erreur
 */
function renderCapteursFallback(container, error) {
  console.warn('[capteursPanel] Fallback:', error);

  const fallbackCard = Card.create('Capteurs', createElement('div', {}, [
    createElement('p', {}, '❌ Impossible de charger les capteurs'),
    createElement('p', {}, `Erreur: ${error.message}`)
  ]));

  container.innerHTML = '';
  container.appendChild(fallbackCard);

  const retryBtn = Button.create('Réessayer', () => loadCapteursPanel(container), 'primary');
  container.appendChild(retryBtn);

  showToast('Erreur de chargement des capteurs', 'error');
}
