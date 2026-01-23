"use strict";

/**
 * Module de génération de cartes Lovelace
 * Compatible avec l'architecture existante
 */

import { renderGenerationLayout } from "./generation.view.js";
import { getLovelaceSensors } from "./generation.api.js";
import { generateDashboardYaml } from "./logic/yamlComposer.js";

export class LovelaceGenerator {
  constructor() {
    this.sensors = [];
    this.generatedYAML = "";
    this._handlers = {}; // Stocker les handlers

    // Power flow UI state
    this._pf_row_seq = 0;
    this._pf_all_facture_total = [];
  }

  async init() {
    console.log("🎨 Initialisation du générateur Lovelace");

    this.attachEvents();
    await this.loadSensors();
    this._init_power_flow_ui();
  }

  attachEvents() {
    console.log("🔧 Attachement des event listeners...");

    const btnGenerate = document.getElementById("btn-generate-yaml");
    const btnDownload = document.getElementById("btn-download-yaml");
    const btnPreview = document.getElementById("btn-preview");
    const btnCopy = document.getElementById("btn-copy-yaml");
    const btnRefresh = document.getElementById("refreshGenerate");

    console.log("🔍 Boutons trouvés:", {
      btnGenerate: !!btnGenerate,
      btnDownload: !!btnDownload,
      btnPreview: !!btnPreview,
      btnCopy: !!btnCopy,
      btnRefresh: !!btnRefresh,
    });

    // Retirer les anciens listeners avant d'ajouter les nouveaux

    if (btnGenerate) {
      if (this._handlers.generate) {
        btnGenerate.removeEventListener("click", this._handlers.generate);
      }
      this._handlers.generate = () => {
        console.log("🎨 Bouton Générer cliqué");
        this.generateYAML();
      };
      btnGenerate.addEventListener("click", this._handlers.generate);
      console.log("✅ Listener ajouté: Générer YAML");
    } else {
      console.error("❌ Bouton btn-generate-yaml non trouvé");
    }

    if (btnDownload) {
      if (this._handlers.download) {
        btnDownload.removeEventListener("click", this._handlers.download);
      }
      this._handlers.download = () => {
        console.log("📥 Bouton Télécharger cliqué");
        this.downloadYAML();
      };
      btnDownload.addEventListener("click", this._handlers.download);
      console.log("✅ Listener ajouté: Télécharger");
    } else {
      console.error("❌ Bouton btn-download-yaml non trouvé");
    }

    if (btnPreview) {
      if (this._handlers.preview) {
        btnPreview.removeEventListener("click", this._handlers.preview);
      }
      this._handlers.preview = () => {
        console.log("👁️ Bouton Aperçu cliqué");
        this.togglePreview();
      };
      btnPreview.addEventListener("click", this._handlers.preview);
      console.log("✅ Listener ajouté: Aperçu");
    } else {
      console.error("❌ Bouton btn-preview non trouvé");
    }

    if (btnCopy) {
      if (this._handlers.copy) {
        btnCopy.removeEventListener("click", this._handlers.copy);
      }
      this._handlers.copy = () => {
        console.log("📋 Bouton Copier cliqué");
        this.copyToClipboard();
      };
      btnCopy.addEventListener("click", this._handlers.copy);
      console.log("✅ Listener ajouté: Copier");
    } else {
      console.error("❌ Bouton btn-copy-yaml non trouvé");
    }

    if (btnRefresh) {
      if (this._handlers.refresh) {
        btnRefresh.removeEventListener("click", this._handlers.refresh);
      }
      this._handlers.refresh = () => {
        console.log("🔄 Bouton Actualiser cliqué");
        this.loadSensors().then(() => {
          this._populate_power_flow_selects();
        });
      };
      btnRefresh.addEventListener("click", this._handlers.refresh);
      console.log("✅ Listener ajouté: Actualiser");
    } else {
      console.error("❌ Bouton refreshGenerate non trouvé");
    }

    // Power flow listeners (safe if elements not present yet)
    const card_type_el = document.getElementById("card_type");
    const pf_title_el = document.getElementById("pf_title");
    const pf_home_cost_keyword_el = document.getElementById("pf_home_cost_keyword");
    const pf_add_individual_el = document.getElementById("pf_add_individual");

    if (card_type_el) {
      card_type_el.addEventListener("change", () => this._apply_card_type_visibility());
    }

    if (pf_title_el) {
      pf_title_el.addEventListener("input", () => {
        this._suggest_home_cost_from_title();
      });
    }

    if (pf_home_cost_keyword_el) {
      pf_home_cost_keyword_el.addEventListener("input", () => {
        this._render_home_cost_total_options();
      });
    }

    if (pf_add_individual_el) {
      pf_add_individual_el.addEventListener("click", () => {
        this._add_power_flow_individual_row();
      });
    }
  }

  async loadSensors() {
    try {
      console.log("🔍 Chargement des sensors HSE via REST API locale...");
      const sensors = await getLovelaceSensors(); // ✅ API extraite
      this.sensors = sensors;

      const countEl = document.getElementById("sensor-count");
      if (countEl) {
        const has = this.sensors.length > 0;
        countEl.textContent = has ? this.sensors.length : "Aucun trouvé";
        countEl.classList.toggle("is-error", !has);
      }

      console.log(`✅ ${this.sensors.length} sensors HSE trouvés`);
      if (this.sensors.length > 0) {
        console.log("📋 Exemples de sensors HSE:");
        this.sensors.slice(0, 5).forEach((s) => {
          console.log(`  - ${s.entity_id} (${s.state})`);
        });
      } else {
        console.warn("⚠️ Aucun sensor HSE trouvé ! Vérifiez que les sensors existent.");
      }
    } catch (error) {
      console.error("❌ Erreur chargement sensors:", error);
      const countEl = document.getElementById("sensor-count");
      if (countEl) {
        countEl.textContent = `Erreur: ${error.message}`;
        countEl.classList.add("is-error");
      }
    }
  }

  _init_power_flow_ui() {
    this._apply_card_type_visibility();
    this._populate_power_flow_selects();

    // 1 row by default in PF mode
    const pf_individuals = document.getElementById("pf_individuals");
    if (pf_individuals && pf_individuals.children.length === 0) {
      this._add_power_flow_individual_row();
    }

    // Try suggestion if title already has value (or after load)
    this._suggest_home_cost_from_title();
  }

  _apply_card_type_visibility() {
    const card_type_el = document.getElementById("card_type");
    const pf_options_el = document.getElementById("power_flow_options");

    if (!card_type_el || !pf_options_el) return;

    const is_pf = card_type_el.value === "power_flow_card_plus";
    pf_options_el.classList.toggle("is-hidden", !is_pf);
  }

  _normalize_text(value) {
    const raw = String(value || "").toLowerCase();
    try {
      return raw
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "")
        .replace(/[^a-z0-9_\-\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    } catch (_e) {
      // fallback for older engines
      return raw.replace(/\s+/g, " ").trim();
    }
  }

  _is_power_sensor(sensor) {
    const attrs = sensor?.attributes || {};
    const unit = String(attrs.unit_of_measurement || "").toLowerCase();
    const device_class = String(attrs.device_class || "").toLowerCase();
    const eid = String(sensor?.entity_id || "").toLowerCase();

    if (device_class === "power") return true;
    if (unit === "w" || unit === "kw") return true;
    if (eid.includes("_power") || eid.includes("puissance")) return true;

    return false;
  }

  _is_cost_daily_ttc_sensor(sensor) {
    const eid = String(sensor?.entity_id || "").toLowerCase();
    return eid.includes("_cout_daily") && eid.includes("_ttc");
  }

  _is_facture_total_sensor(sensor) {
    const eid = String(sensor?.entity_id || "").toLowerCase();
    return eid.includes("facture_total_");
  }

  _populate_power_flow_selects() {
    const home_power_el = document.getElementById("pf_home_power_entity");
    const home_cost_el = document.getElementById("pf_home_cost_entity");

    if (!home_power_el || !home_cost_el) return;

    const power_sensors = (this.sensors || []).filter((s) => this._is_power_sensor(s));
    const facture_total_sensors = (this.sensors || []).filter((s) => this._is_facture_total_sensor(s));

    this._pf_all_facture_total = facture_total_sensors;

    const power_options = power_sensors
      .map((s) => ({
        entity_id: s.entity_id,
        label: s.attributes?.friendly_name || s.entity_id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));

    home_power_el.innerHTML = "";
    for (const opt of power_options) {
      const option = document.createElement("option");
      option.value = opt.entity_id;
      option.textContent = opt.label;
      home_power_el.appendChild(option);
    }

    // Home cost: rendered through keyword filter
    this._render_home_cost_total_options();

    // Individuals existing rows rehydrate
    this._refresh_individual_rows_options();
  }

  _render_home_cost_total_options() {
    const home_cost_el = document.getElementById("pf_home_cost_entity");
    const keyword_el = document.getElementById("pf_home_cost_keyword");

    if (!home_cost_el) return;

    const current_value = String(home_cost_el.value || "");
    const keyword_raw = keyword_el ? keyword_el.value : "";
    const keyword = this._normalize_text(keyword_raw);

    let candidates = this._pf_all_facture_total || [];

    if (keyword) {
      candidates = candidates.filter((s) => {
        const eid = String(s.entity_id || "").toLowerCase();
        return eid.includes(`facture_total_${keyword}`) || eid.includes(keyword);
      });
    }

    const options = candidates
      .map((s) => ({
        entity_id: s.entity_id,
        label: s.attributes?.friendly_name || s.entity_id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));

    home_cost_el.innerHTML = "";

    const empty_opt = document.createElement("option");
    empty_opt.value = "";
    empty_opt.textContent = "— Aucun (optionnel) —";
    home_cost_el.appendChild(empty_opt);

    for (const opt of options) {
      const option = document.createElement("option");
      option.value = opt.entity_id;
      option.textContent = opt.label;
      home_cost_el.appendChild(option);
    }

    // Restore current if still present
    if (current_value && options.some((o) => o.entity_id === current_value)) {
      home_cost_el.value = current_value;
      return;
    }

    // If keyword gives exactly 1 result => auto-select
    if (!current_value && options.length === 1) {
      home_cost_el.value = options[0].entity_id;
    }

    // If keyword empty, title suggestion can select
    if (!keyword) {
      this._suggest_home_cost_from_title();
    }
  }

  _suggest_home_cost_from_title() {
    const keyword_el = document.getElementById("pf_home_cost_keyword");
    const home_cost_el = document.getElementById("pf_home_cost_entity");
    const title_el = document.getElementById("pf_title");

    if (!home_cost_el || !title_el) return;

    // User typed a keyword => do not override
    const keyword = keyword_el ? this._normalize_text(keyword_el.value) : "";
    if (keyword) return;

    const title = this._normalize_text(title_el.value);
    if (!title) return;

    const words = title.split(" ").filter((w) => w.length >= 3);
    if (words.length === 0) return;

    // Try each word in order (title contains)
    for (const w of words) {
      const match = (this._pf_all_facture_total || []).find((s) =>
        String(s.entity_id || "").toLowerCase().includes(`facture_total_${w}`)
      );
      if (match) {
        // only set if empty or not already set
        if (!home_cost_el.value) {
          home_cost_el.value = match.entity_id;
        }
        return;
      }
    }

    // No match => keep empty
    if (!home_cost_el.value) {
      home_cost_el.value = "";
    }
  }

  _refresh_individual_rows_options() {
    const container = document.getElementById("pf_individuals");
    if (!container) return;

    const power_sensors = (this.sensors || []).filter((s) => this._is_power_sensor(s));
    const cost_sensors = (this.sensors || []).filter((s) => this._is_cost_daily_ttc_sensor(s));

    const power_options = power_sensors
      .map((s) => ({
        entity_id: s.entity_id,
        label: s.attributes?.friendly_name || s.entity_id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));

    const cost_options = cost_sensors
      .map((s) => ({
        entity_id: s.entity_id,
        label: s.attributes?.friendly_name || s.entity_id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));

    const rows = container.querySelectorAll(".generation-individual-row");
    rows.forEach((row_el) => {
      const power_el = row_el.querySelector("select[data-role='pf_individual_power']");
      const cost_el = row_el.querySelector("select[data-role='pf_individual_cost']");

      if (power_el) {
        const current = power_el.value;
        power_el.innerHTML = "";
        for (const opt of power_options) {
          const option = document.createElement("option");
          option.value = opt.entity_id;
          option.textContent = opt.label;
          power_el.appendChild(option);
        }
        if (current && power_options.some((o) => o.entity_id === current)) {
          power_el.value = current;
        }
      }

      if (cost_el) {
        const current = cost_el.value;
        cost_el.innerHTML = "";

        const empty_opt = document.createElement("option");
        empty_opt.value = "";
        empty_opt.textContent = "— Aucun (optionnel) —";
        cost_el.appendChild(empty_opt);

        for (const opt of cost_options) {
          const option = document.createElement("option");
          option.value = opt.entity_id;
          option.textContent = opt.label;
          cost_el.appendChild(option);
        }

        if (current && cost_options.some((o) => o.entity_id === current)) {
          cost_el.value = current;
        }
      }
    });
  }

  _add_power_flow_individual_row() {
    const container = document.getElementById("pf_individuals");
    if (!container) return;

    const row_id = ++this._pf_row_seq;

    const row_el = document.createElement("div");
    row_el.className = "generation-individual-row";
    row_el.dataset.rowId = String(row_id);

    row_el.innerHTML = `
      <div class="generation-field">
        <label class="generation-label">Puissance</label>
        <select class="generation-input" data-role="pf_individual_power"></select>
      </div>
      <div class="generation-field">
        <label class="generation-label">Coût daily TTC (optionnel)</label>
        <select class="generation-input" data-role="pf_individual_cost"></select>
      </div>
      <button type="button" class="btn btn-danger generation-individual-remove">🗑️</button>
    `;

    const remove_btn = row_el.querySelector(".generation-individual-remove");
    if (remove_btn) {
      remove_btn.addEventListener("click", () => {
        row_el.remove();
      });
    }

    container.appendChild(row_el);
    this._refresh_individual_rows_options();
  }

  async generateYAML() {
    if (this.sensors.length === 0) {
      alert("Aucun sensor HSE trouvé. Vérifiez que vos sensors sont créés.");
      return;
    }

    const card_type_el = document.getElementById("card_type");
    const card_type = card_type_el ? card_type_el.value : "overview";

    if (card_type === "power_flow_card_plus") {
      const title_el = document.getElementById("pf_title");
      const home_power_el = document.getElementById("pf_home_power_entity");
      const home_cost_el = document.getElementById("pf_home_cost_entity");
      const individuals_container = document.getElementById("pf_individuals");

      const title = title_el ? String(title_el.value || "").trim() : "";
      const home_power_entity = home_power_el ? String(home_power_el.value || "").trim() : "";
      const home_cost_entity = home_cost_el ? String(home_cost_el.value || "").trim() : "";

      if (!home_power_entity) {
        alert("Power Flow: Home puissance obligatoire");
        return;
      }

      const individuals = [];
      if (individuals_container) {
        const rows = individuals_container.querySelectorAll(".generation-individual-row");
        rows.forEach((row_el) => {
          const power_el = row_el.querySelector("select[data-role='pf_individual_power']");
          const cost_el = row_el.querySelector("select[data-role='pf_individual_cost']");

          const power_entity = power_el ? String(power_el.value || "").trim() : "";
          const cost_entity = cost_el ? String(cost_el.value || "").trim() : "";

          if (power_entity) {
            individuals.push({ power_entity, cost_entity });
          }
        });
      }

      this.generatedYAML = generateDashboardYaml({
        sensors: this.sensors,
        cardTypes: ["power_flow_card_plus"],
        options: {
          title,
          home: {
            power_entity: home_power_entity,
            cost_entity: home_cost_entity,
          },
          individuals,
        },
      });

      document.getElementById("yaml-code").textContent = this.generatedYAML;

      const lastGenEl = document.getElementById("last-gen");
      if (lastGenEl) {
        lastGenEl.textContent = new Date().toLocaleString("fr-FR");
      }

      console.log("✅ YAML généré (power_flow_card_plus)");
      return;
    }

    console.log("🎨 Génération du YAML...");

    // On conserve la logique de filtrage daily actuelle
    const dailySensors = this.sensors
      .filter((s) => {
        const eid = s.entity_id;
        return eid.includes("_d") || eid.includes("daily") || eid.includes("_day");
      })
      .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
      .slice(0, 10);

    let sensorsForYaml;
    if (dailySensors.length === 0) {
      console.warn("⚠️ Aucun sensor daily trouvé, utilisation de TOUS les sensors");
      sensorsForYaml = this.sensors
        .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
        .slice(0, 10);
    } else {
      sensorsForYaml = dailySensors;
    }

    // ⚠️ Nouveau : délégation au compositeur YAML
    this.generatedYAML = generateDashboardYaml({
      sensors: sensorsForYaml,
      cardTypes: ["overview"],
      options: {},
    });

    document.getElementById("yaml-code").textContent = this.generatedYAML;

    const lastGenEl = document.getElementById("last-gen");
    if (lastGenEl) {
      lastGenEl.textContent = new Date().toLocaleString("fr-FR");
    }

    console.log("✅ YAML généré");
  }

  downloadYAML() {
    if (!this.generatedYAML) {
      alert("Générez d'abord le YAML");
      return;
    }

    const blob = new Blob([this.generatedYAML], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `home_suivi_elec_dashboard_${Date.now()}.yaml`;
    a.click();
    URL.revokeObjectURL(url);

    console.log("✅ YAML téléchargé");
  }

  async copyToClipboard() {
    if (!this.generatedYAML) {
      alert("Générez d'abord le YAML");
      return;
    }

    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(this.generatedYAML);
        alert("YAML copié dans le presse-papiers !");
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = this.generatedYAML;
        textArea.className = "hse-clipboard-fallback";
        document.body.appendChild(textArea);
        textArea.select();
        try {
          const success = document.execCommand("copy");
          document.body.removeChild(textArea);
          if (success) {
            alert("YAML copié dans le presse-papiers !");
          } else {
            throw new Error("execCommand a échoué");
          }
        } catch (err) {
          document.body.removeChild(textArea);
          alert("Erreur lors de la copie (fallback): " + err.message);
        }
      }
    } catch (error) {
      alert("Erreur lors de la copie : " + error.message);
      console.error("Erreur copie:", error);
    }
  }

  togglePreview() {
    const preview = document.getElementById("preview-container");
    const btnPreview = document.getElementById("btn-preview");

    if (!preview) {
      console.error("❌ Element #preview-container non trouvé");
      alert("Erreur: conteneur aperçu non trouvé");
      return;
    }

    const isHidden = preview.classList.contains("is-hidden");

    if (isHidden) {
      preview.classList.remove("is-hidden");
      if (btnPreview) btnPreview.textContent = "❌ Fermer aperçu";
      this.renderPreview();
      console.log("✅ Aperçu affiché");
    } else {
      preview.classList.add("is-hidden");
      if (btnPreview) btnPreview.textContent = "👁️ Aperçu";
      console.log("✅ Aperçu masqué");
    }
  }

  renderPreview() {
    const preview = document.getElementById("dashboard-preview");

    if (!preview) {
      console.error("❌ Element #dashboard-preview non trouvé");
      return;
    }

    if (this.sensors.length === 0) {
      preview.innerHTML = '<p class="generation-empty">Aucun sensor disponible</p>';
      return;
    }

    const dailySensors = this.sensors
      .filter((s) => {
        const eid = s.entity_id || "";
        return eid.includes("_d") || eid.includes("daily") || eid.includes("_day");
      })
      .sort((a, b) => parseFloat(b.state || 0) - parseFloat(a.state || 0))
      .slice(0, 10);

    const sensorsToShow =
      dailySensors.length > 0 ? dailySensors : this.sensors.slice(0, 10);

    console.log(`📊 Aperçu: affichage de ${sensorsToShow.length} sensors`);

    const cards = sensorsToShow
      .map((s) => {
        const state = parseFloat(s.state || 0).toFixed(2);
        const unit = s.attributes?.unit_of_measurement || "kWh";
        const name = s.attributes?.friendly_name || s.entity_id;

        const card = document.createElement("div");
        card.className = "preview-card";
        card.innerHTML = `
        <div class="preview-card-name" title="${s.entity_id}">${name}</div>
        <div class="preview-card-value">${state} <span class="preview-card-unit">${unit}</span></div>
      `;
        return card.outerHTML;
      })
      .join("");

    preview.innerHTML = cards || '<p class="generation-empty">Erreur génération aperçu</p>';
  }
}

/**
 * Point d'entrée principal
 */
export async function loadGeneration() {
  console.log("[generation] loadGeneration appelé");

  const container = document.getElementById("generation");
  if (!container) {
    console.error("[generation] Container #generation introuvable");
    return;
  }

  // Injecter le layout HTML
  container.innerHTML = renderGenerationLayout();

  // Pattern singleton pour éviter double instanciation
  if (window._generatorInstance) {
    console.log("[generation] Generator déjà instancié, réutilisation");
    return window._generatorInstance;
  }

  const generator = new LovelaceGenerator();
  await generator.init();

  window._generatorInstance = generator;
  console.log("[generation] Generator instancié et stocké");

  return generator;
}
