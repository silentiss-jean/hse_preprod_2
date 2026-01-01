"use strict";

/**
 * Module de génération de cartes Lovelace
 * Compatible avec l'architecture existante
 */

import { renderGenerationLayout } from './generation.view.js';
import { getLovelaceSensors } from './generation.api.js';
import { generateDashboardYaml } from './logic/yamlComposer.js';

export class LovelaceGenerator {
  constructor() {
    this.sensors = [];
    this.generatedYAML = '';
    this._handlers = {}; // Stocker les handlers
  }

  async init() {
    console.log('🎨 Initialisation du générateur Lovelace');

    this.attachEvents();
    await this.loadSensors();
  }

  attachEvents() {
    console.log('🔧 Attachement des event listeners...');

    const btnGenerate = document.getElementById('btn-generate-yaml');
    const btnDownload = document.getElementById('btn-download-yaml');
    const btnPreview = document.getElementById('btn-preview');
    const btnCopy = document.getElementById('btn-copy-yaml');
    const btnRefresh = document.getElementById('refreshGenerate');

    console.log('🔍 Boutons trouvés:', {
      btnGenerate: !!btnGenerate,
      btnDownload: !!btnDownload,
      btnPreview: !!btnPreview,
      btnCopy: !!btnCopy,
      btnRefresh: !!btnRefresh
    });

    // Retirer les anciens listeners avant d'ajouter les nouveaux

    if (btnGenerate) {
      if (this._handlers.generate) {
        btnGenerate.removeEventListener('click', this._handlers.generate);
      }
      this._handlers.generate = () => {
        console.log('🎨 Bouton Générer cliqué');
        this.generateYAML();
      };
      btnGenerate.addEventListener('click', this._handlers.generate);
      console.log('✅ Listener ajouté: Générer YAML');
    } else {
      console.error('❌ Bouton btn-generate-yaml non trouvé');
    }

    if (btnDownload) {
      if (this._handlers.download) {
        btnDownload.removeEventListener('click', this._handlers.download);
      }
      this._handlers.download = () => {
        console.log('📥 Bouton Télécharger cliqué');
        this.downloadYAML();
      };
      btnDownload.addEventListener('click', this._handlers.download);
      console.log('✅ Listener ajouté: Télécharger');
    } else {
      console.error('❌ Bouton btn-download-yaml non trouvé');
    }

    if (btnPreview) {
      if (this._handlers.preview) {
        btnPreview.removeEventListener('click', this._handlers.preview);
      }
      this._handlers.preview = () => {
        console.log('👁️ Bouton Aperçu cliqué');
        this.togglePreview();
      };
      btnPreview.addEventListener('click', this._handlers.preview);
      console.log('✅ Listener ajouté: Aperçu');
    } else {
      console.error('❌ Bouton btn-preview non trouvé');
    }

    if (btnCopy) {
      if (this._handlers.copy) {
        btnCopy.removeEventListener('click', this._handlers.copy);
      }
      this._handlers.copy = () => {
        console.log('📋 Bouton Copier cliqué');
        this.copyToClipboard();
      };
      btnCopy.addEventListener('click', this._handlers.copy);
      console.log('✅ Listener ajouté: Copier');
    } else {
      console.error('❌ Bouton btn-copy-yaml non trouvé');
    }

    if (btnRefresh) {
      if (this._handlers.refresh) {
        btnRefresh.removeEventListener('click', this._handlers.refresh);
      }
      this._handlers.refresh = () => {
        console.log('🔄 Bouton Actualiser cliqué');
        this.loadSensors();
      };
      btnRefresh.addEventListener('click', this._handlers.refresh);
      console.log('✅ Listener ajouté: Actualiser');
    } else {
      console.error('❌ Bouton refreshGenerate non trouvé');
    }
  }

  async loadSensors() {
    try {
      console.log('🔍 Chargement des sensors HSE via REST API locale...');
      const sensors = await getLovelaceSensors(); // ✅ API extraite
      this.sensors = sensors;

      const countEl = document.getElementById('sensor-count');
      if (countEl) {
        countEl.textContent = this.sensors.length > 0 ? this.sensors.length : 'Aucun trouvé';
        countEl.style.color = this.sensors.length > 0 ? 'inherit' : 'red';
      }

      console.log(`✅ ${this.sensors.length} sensors HSE trouvés`);
      if (this.sensors.length > 0) {
        console.log('📋 Exemples de sensors HSE:');
        this.sensors.slice(0, 5).forEach(s => {
          console.log(`  - ${s.entity_id} (${s.state})`);
        });
      } else {
        console.warn('⚠️ Aucun sensor HSE trouvé ! Vérifiez que les sensors existent.');
      }
    } catch (error) {
      console.error('❌ Erreur chargement sensors:', error);
      const countEl = document.getElementById('sensor-count');
      if (countEl) {
        countEl.textContent = `Erreur: ${error.message}`;
        countEl.style.color = 'red';
      }
    }
  }

  async generateYAML() {
    if (this.sensors.length === 0) {
      alert('Aucun sensor HSE trouvé. Vérifiez que vos sensors sont créés.');
      return;
    }

    console.log('🎨 Génération du YAML...');

    // On conserve la logique de filtrage daily actuelle
    const dailySensors = this.sensors
      .filter(s => {
        const eid = s.entity_id;
        return eid.includes('_d') || eid.includes('daily') || eid.includes('_day');
      })
      .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
      .slice(0, 10);

    let sensorsForYaml;
    if (dailySensors.length === 0) {
      console.warn('⚠️ Aucun sensor daily trouvé, utilisation de TOUS les sensors');
      sensorsForYaml = this.sensors
        .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
        .slice(0, 10);
    } else {
      sensorsForYaml = dailySensors;
    }

    // ⚠️ Nouveau : délégation au compositeur YAML
    this.generatedYAML = generateDashboardYaml({
      sensors: sensorsForYaml,
      cardTypes: ["overview"],   // prêt pour l'extension future
      options: {}
    });

    document.getElementById('yaml-code').textContent = this.generatedYAML;

    const lastGenEl = document.getElementById('last-gen');
    if (lastGenEl) {
      lastGenEl.textContent = new Date().toLocaleString('fr-FR');
    }

    console.log('✅ YAML généré');
  }

  downloadYAML() {
    if (!this.generatedYAML) {
      alert('Générez d\'abord le YAML');
      return;
    }

    const blob = new Blob([this.generatedYAML], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `home_suivi_elec_dashboard_${Date.now()}.yaml`;
    a.click();
    URL.revokeObjectURL(url);

    console.log('✅ YAML téléchargé');
  }

  async copyToClipboard() {
    if (!this.generatedYAML) {
      alert('Générez d\'abord le YAML');
      return;
    }

    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(this.generatedYAML);
        alert('YAML copié dans le presse-papiers !');
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = this.generatedYAML;
        textArea.style.position = "fixed";
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.width = "2em";
        textArea.style.height = "2em";
        textArea.style.padding = "0";
        textArea.style.border = "none";
        textArea.style.outline = "none";
        textArea.style.boxShadow = "none";
        textArea.style.background = "transparent";
        document.body.appendChild(textArea);
        textArea.select();
        try {
          const success = document.execCommand('copy');
          document.body.removeChild(textArea);
          if (success) {
            alert('YAML copié dans le presse-papiers !');
          } else {
            throw new Error('execCommand a échoué');
          }
        } catch (err) {
          document.body.removeChild(textArea);
          alert('Erreur lors de la copie (fallback): ' + err.message);
        }
      }
    } catch (error) {
      alert('Erreur lors de la copie : ' + error.message);
      console.error('Erreur copie:', error);
    }
  }

  togglePreview() {
    const preview = document.getElementById('preview-container');
    const btnPreview = document.getElementById('btn-preview');

    if (!preview) {
      console.error('❌ Element #preview-container non trouvé');
      alert('Erreur: conteneur aperçu non trouvé');
      return;
    }

    const currentDisplay = window.getComputedStyle(preview).display;

    if (currentDisplay === 'none') {
      preview.style.setProperty('display', 'block', 'important');
      if (btnPreview) btnPreview.textContent = '❌ Fermer aperçu';
      this.renderPreview();
      console.log('✅ Aperçu affiché');
    } else {
      preview.style.setProperty('display', 'none', 'important');
      if (btnPreview) btnPreview.textContent = '👁️ Aperçu';
      console.log('✅ Aperçu masqué');
    }
  }

  renderPreview() {
    const preview = document.getElementById('dashboard-preview');

    if (!preview) {
      console.error('❌ Element #dashboard-preview non trouvé');
      return;
    }

    if (this.sensors.length === 0) {
      preview.innerHTML = '<p style="text-align:center;color:#999;">Aucun sensor disponible</p>';
      return;
    }

    const dailySensors = this.sensors
      .filter(s => {
        const eid = s.entity_id || '';
        return eid.includes('_d') || eid.includes('daily') || eid.includes('_day');
      })
      .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
      .slice(0, 10);

    const sensorsToShow = dailySensors.length > 0 ? dailySensors : this.sensors.slice(0, 10);

    console.log(`📊 Aperçu: affichage de ${sensorsToShow.length} sensors`);

    const cards = sensorsToShow.map(s => {
      const state = parseFloat(s.state || 0).toFixed(2);
      const unit = s.attributes?.unit_of_measurement || 'kWh';
      const name = s.attributes?.friendly_name || s.entity_id;

      const card = document.createElement('div');
      card.className = 'preview-card';
      card.innerHTML = `
        <div class="preview-card-name" title="${s.entity_id}">${name}</div>
        <div class="preview-card-value">${state} <span class="preview-card-unit">${unit}</span></div>
      `;
      return card.outerHTML;
    }).join('');

    preview.innerHTML = cards || '<p style="text-align:center;color:#999;">Erreur génération aperçu</p>';
  }
}

/**
 * Point d'entrée principal
 */
export async function loadGeneration() {
  console.log('[generation] loadGeneration appelé');

  const container = document.getElementById('generation');
  if (!container) {
    console.error('[generation] Container #generation introuvable');
    return;
  }

  // Injecter le layout HTML
  container.innerHTML = renderGenerationLayout();

  // Pattern singleton pour éviter double instanciation
  if (window._generatorInstance) {
    console.log('[generation] Generator déjà instancié, réutilisation');
    return window._generatorInstance;
  }

  const generator = new LovelaceGenerator();
  await generator.init();

  window._generatorInstance = generator;
  console.log('[generation] Generator instancié et stocké');

  return generator;
}
