// features/migration/migration.view.js
"use strict";

import { createElement } from "../../shared/utils/dom.js";
import { ExportCard } from "./components/ExportCard.js";
import { PreviewModal } from "./components/PreviewModal.js";
import { MIGRATION_CYCLES } from "../../shared/constants.js";
//import { MigrationAPI, generateCostSensors } from "./migration.api.js";
import { MigrationAPI } from "./migration.api.js";
import { Toast } from "../../shared/components/Toast.js";

export class MigrationView {
  constructor(controller) {
    this.controller = controller;
    this.root = null;
  }

  render() {
    const container = document.querySelector("#migration");
    if (!container) {
      console.warn("[migration.view] Conteneur #migration introuvable");
      return;
    }

    container.innerHTML = "";

    const title = createElement(
      "h2",
      { className: "page-title" },
      "Migration vers helpers Home Assistant"
    );
    container.appendChild(title);

    const intro = createElement(
      "p",
      { className: "page-intro" },
      "Exportez vos capteurs sélectionnés vers des helpers natifs Home Assistant (utility_meter et templates)."
    );
    container.appendChild(intro);

    const cardsWrapper = createElement("div", { className: "migration-cards" });
    container.appendChild(cardsWrapper);

    const options = [
      {
        id: "utility_meter",
        title: "Option 1 – Utility Meter YAML",
        description:
          "Génère un fichier utility_meter.yaml prêt à coller dans votre configuration Home Assistant.",
        features: [
          "Un utility_meter par capteur sélectionné",
          `Cycles: ${Object.values(MIGRATION_CYCLES).join(", ")}`,
          "Compatible avec l’intégration utility_meter",
        ],
        buttons: [
          {
            text: "Exporter",
            onClick: () => this.controller.exportUtilityMeter(),
          },
          {
            text: "Preview YAML",
            onClick: () => this.handlePreview("utility_meter"),
          },
        ],
        rating: 5,
        recommended: true,
      },
      {
        id: "templates",
        title: "Option 2 – Template Sensors (Riemann)",
        description:
          "Génère des sensors template pour calculer l’énergie à partir de vos capteurs de puissance.",
        features: ["Templates power/energy", "Pensé pour une intégration de type Riemann"],
        buttons: [
          {
            text: "Exporter",
            onClick: () => this.controller.exportTemplates(),
          },
          {
            text: "Preview YAML",
            onClick: () => this.handlePreview("templates"),
          },
        ],
        rating: 4,
      },
      // OPTION 3 (nouveau) – Génération capteurs coût
      {
        id: "cost_sensors",
        title: "Option 3 – Génération sensors coût (NOUVEAU)",
        description:
          "Génère automatiquement des sensors de coût (HT/TTC) à partir de vos sensors energy existants (daily/weekly/monthly).",
        features: [
          "Ne touche pas aux sensors existants",
          "Crée des sensors 'sensor.hse_cout_*'",
          "Utilise le prix HT/TTC fourni",
        ],
        // ExportCard ne gère pas un formulaire, donc on met un bouton qui ouvre un mini modal
        buttons: [
//          {
//            text: "Générer automatiquement",
//            onClick: () => this.generateCostSensorsAuto(),
//          },
          {
            text: "Exporter",
            onClick: () => MigrationAPI.downloadCostYAML([]), // NOUVEAU (HA natif)
          },
          {
            text: "Preview YAML",
            onClick: () => this.handlePreview("cost"), // NOUVEAU (HA natif)
          },
        ],
        rating: 3,
        recommended: true,
      },
      {
        id: "auto_helpers",
        title: "Option 4 – Création automatique (BETA)",
        description:
          "Crée automatiquement des helpers utility_meter natifs dans Home Assistant à partir de vos capteurs sélectionnés.",
        features: [
          "Création directe des helpers utility_meter via l’API",
          "Un helper par capteur × cycle sélectionné",
          "Option avancée : peut augmenter le nombre total de capteurs dans Home Assistant",
        ],
        buttons: [
          {
            text: "Créer automatiquement",
            onClick: () => this.controller.createHelpersAuto(null),
          },
        ],
        rating: 5,
      },
    ];

    options.forEach((opt) => {
      const card = ExportCard.create(opt);
      cardsWrapper.appendChild(card);
    });

    const help = createElement(
      "p",
      { className: "migration-help" },
      "Options 1 et 2 génèrent des fichiers YAML à coller dans votre configuration Home Assistant. " +
        "L’option 4 crée directement les helpers utility_meter dans Home Assistant via l’API (option avancée). " +
        "L’option 3 génère des sensors coût (HT/TTC) à partir des sensors energy existants."
    );
    container.appendChild(help);

    this.root = container;
  }

  async handlePreview(kind) {
    try {
      let yaml = null;
      let title = "Preview";
      let downloadFn = async () => {};

      if (kind === "utility_meter") {
        yaml = await this.controller.previewUtilityMeter();
        title = "Preview utility_meter.yaml";
        downloadFn = () => MigrationAPI.downloadUtilityMeterYAML([]);
      } else if (kind === "templates") {
        yaml = await this.controller.previewTemplates();
        title = "Preview template_sensors.yaml";
        downloadFn = () => MigrationAPI.downloadTemplatesYAML([]);
      } else if (kind === "cost") {
        yaml = await MigrationAPI.previewCostYAML([]);
        title = "Preview cost_sensors.yaml";
        downloadFn = () => MigrationAPI.downloadCostYAML([]);
      } else {
        Toast.error("Type de preview inconnu");
        return;
      }

      if (!yaml) return;
      PreviewModal.show(title, yaml, downloadFn);
    } catch (e) {
      console.error("[migration.view] Erreur preview:", e);
      Toast.error("Erreur preview YAML");
    }
  }

  async generateCostSensorsAuto() {
    try {
      Toast.info("Génération des sensors coût en cours...");
      const res = await generateCostSensors({}); // body vide => backend prend config_entries
      Toast.success(`${res.count} sensors coût créés`);
    } catch (e) {
      console.error("[migration.view] Erreur generateCostSensorsAuto:", e);
      Toast.error(`Erreur génération sensors coût: ${e?.message || e}`);
    }
  }
}
