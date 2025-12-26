'use strict';

/**
 * Panel d'affichage des intégrations
 */

import { getSensorsData } from '../diagnostics.api.js';
import { setCachedData } from '../diagnostics.state.js';
import { extractIntegrations, getIntegrationsStats, getIntegrationIcon } from '../logic/integrationExtractor.js';
import { showToast } from '../../../shared/uiToast.js';
import { createElement } from '../../../shared/utils/dom.js';
// ✅ Tous les composants partagés en import namespace
import { Badge } from '../../../shared/components/Badge.js';
import { Button } from '../../../shared/components/Button.js';
import { Card } from '../../../shared/components/Card.js';
import { Table } from '../../../shared/components/Table.js'; 

console.info('[integrationsPanel] Module chargé');

/**
 * Point d'entrée principal
 */
export async function loadIntegrationsPanel(container) {
  if (!container) {
    console.error('[integrationsPanel] Container requis');
    return;
  }

  try {
    console.log('[integrationsPanel] Chargement...');

    // Loader
    container.innerHTML = '';
    container.appendChild(createElement('div', { class: 'loading-state' }, [
      createElement('div', { class: 'spinner' }),
      createElement('p', {}, 'Chargement des intégrations...')
    ]));

    // Récupérer données API
    const apiData = await getSensorsData();
    if (!apiData) throw new Error('Aucune donnée reçue');

    console.log('[integrationsPanel] API:', apiData);

    // Extraire intégrations
    const integrations = extractIntegrations(apiData);
    setCachedData('integrations', integrations);

    const count = Object.keys(integrations).length;
    console.log('[integrationsPanel]', count, 'intégrations');

    if (count === 0) {
      container.innerHTML = '';
      container.appendChild(
        Card.create('Aucune intégration', createElement('p', {}, 'Aucune intégration détectée'))
      );
      return;
    }

    // Render
    renderIntegrationsInterface(container, integrations);
    showToast(`${count} intégrations chargées`, 'success');

  } catch (error) {
    console.error('[integrationsPanel] Erreur:', error);
    container.innerHTML = '';
    container.appendChild(
      Card.create('Erreur', createElement('div', {}, [
        createElement('p', {}, error.message),
        createElement('p', {}, 'Endpoint: /api/home_suivi_elec/get_sensors')
      ]))
    );
    showToast(`Erreur: ${error.message}`, 'error');
  }
}

/**
 * Rendu de l'interface
 */
function renderIntegrationsInterface(container, integrations) {
  container.innerHTML = '';

  const integrationsArray = Object.entries(integrations);
  const stats = getIntegrationsStats(integrations);

  // Préparer données pour le tableau
  const tableData = integrationsArray.map(([key, integration]) => ({
    integrationKey: key,
    integration: integration,
    displayName: integration.displayName,
    icon: integration.icon,
    state: integration.state,
    selectedCount: integration.selected.length,
    availableCount: integration.available.length,
    total: integration.total
  }));

  // Colonnes du tableau
  const columns = [
    {
      key: 'displayName',
      label: 'Intégration',
      render: (value, row) => {
        return createElement('span', {}, `${row.icon} ${value}`);
      }
    },
    {
      key: 'state',
      label: 'État',
      render: (value) => {
        return Badge.create(
          value.toUpperCase(),
          value === 'active' ? 'success' : 'error'
        );
      }
    },
    {
      key: 'selectedCount',
      label: 'Sélectionnés'
    },
    {
      key: 'availableCount',
      label: 'Disponibles'
    },
    {
      key: 'total',
      label: 'Total'
    },
    {
      key: 'integrationKey',
      label: 'Actions',
      render: (value, row) => {
        return Button.create(
          'Détails',
          () => showIntegrationDetails(value, row.integration),
          'secondary'
        );
      }
    }
  ];

  // Créer tableau
  const table = Table.create(columns, tableData);

  // Contenu
  const content = createElement('div', {}, [
    createElement('p', { class: 'subtitle' }, 
      `${integrationsArray.length} intégrations détectées • ${stats.totalSensors} capteurs`
    ),
    table
  ]);

  const mainCard = Card.create('Intégrations énergétiques', content);
  container.appendChild(mainCard);

  // Bouton refresh
  const refreshBtn = Button.create('Actualiser', () => loadIntegrationsPanel(container), 'secondary');
  container.appendChild(refreshBtn);
}

/**
 * Affiche les détails d'une intégration dans une modal
 */
function showIntegrationDetails(integrationKey, integration) {
  console.log('[integrationsPanel] Détails:', integrationKey, integration);

  // Overlay (clic dessus ferme la modal)
  const overlay = createElement('div', {
    class: 'modal-overlay',
    id: 'integration-modal'
  });

  // Fermer au clic sur l'overlay
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeIntegrationModal();
    }
  });

  // Modal content
  const modalContent = createElement('div', { class: 'modal-content' });

  // Header avec titre et croix
  const modalHeader = createElement('div', { class: 'modal-header' }, [
    createElement('h2', {}, `${integration.icon} ${integration.displayName}`),
    createElement('button', {
      class: 'modal-close-btn',
      'aria-label': 'Fermer'
    }, '✕')
  ]);

  // Ajouter event sur la croix
  const closeBtn = modalHeader.querySelector('.modal-close-btn');
  closeBtn.addEventListener('click', closeIntegrationModal);

  // Section capteurs sélectionnés
  const selectedSection = createElement('div', { class: 'details-section' }, [
    createElement('h3', {}, `Capteurs sélectionnés (${integration.selected.length})`),
    integration.selected.length > 0
      ? createElement('ul', { class: 'sensor-list' }, 
          integration.selected.map(sensor => 
            createElement('li', {}, [
              createElement('strong', {}, sensor.entity_id),
              createElement('br'),
              createElement('small', {}, sensor.friendly_name || sensor.nom || 'Sans nom')
            ])
          )
        )
      : createElement('p', {}, 'Aucun capteur sélectionné')
  ]);

  // Section capteurs disponibles
  const availableSection = createElement('div', { class: 'details-section' }, [
    createElement('h3', {}, `Capteurs disponibles (${integration.available.length})`),
    integration.available.length > 0
      ? createElement('ul', { class: 'sensor-list' },
          integration.available.map(sensor =>
            createElement('li', {}, [
              createElement('strong', {}, sensor.entity_id),
              createElement('br'),
              createElement('small', {}, sensor.friendly_name || sensor.nom || 'Sans nom')
            ])
          )
        )
      : createElement('p', {}, 'Aucun capteur disponible')
  ]);

  // Body
  const modalBody = createElement('div', { class: 'modal-body' }, [
    selectedSection,
    availableSection
  ]);

  // Footer avec bouton Fermer
  const modalFooter = createElement('div', { class: 'modal-footer' });
  const closeBtnFooter = Button.create('Fermer', closeIntegrationModal, 'secondary');
  modalFooter.appendChild(closeBtnFooter);

  // Assembler la modal
  modalContent.appendChild(modalHeader);
  modalContent.appendChild(modalBody);
  modalContent.appendChild(modalFooter);
  overlay.appendChild(modalContent);
  document.body.appendChild(overlay);

  // Fermer avec touche Escape
  const handleEscape = (e) => {
    if (e.key === 'Escape') {
      closeIntegrationModal();
      document.removeEventListener('keydown', handleEscape);
    }
  };
  document.addEventListener('keydown', handleEscape);
}

/**
 * Ferme la modal
 */
function closeIntegrationModal() {
  const modal = document.getElementById('integration-modal');
  if (modal) {
    modal.remove();
  }
}
