// features/migration/exporters/templateSensor.js

"use strict";

import { MigrationAPI } from "../migration.api.js";
import { Toast } from "../../../shared/components/Toast.js";

export class TemplateSensorExporter {
  /**
   * Lance l'export template_sensors.yaml (Riemann).
   *
   * Si sensors est vide ou null, on s’appuie sur la sélection backend,
   * comme pour l’utility_meter.
   */
  static async export(sensors) {
    try {
      const count = sensors?.length ?? 0;
      const hasExplicitSelection = count > 0;

      if (hasExplicitSelection) {
        Toast.info(`Export de ${count} capteurs en templates (Riemann)...`);
        await MigrationAPI.downloadTemplatesYAML(sensors);

        Toast.success(
          `${count} templates exportés. ` +
            "Nécessite une intégration de type Riemann pour les calculs.",
          0
        );
      } else {
        // Cas actuel : aucune liste explicite, on laisse le backend décider
        // à partir de la sélection sauvegardée (même logique que preview + téléchargement).
        Toast.info(
          "Export des capteurs sélectionnés en templates (Riemann) à partir de la configuration Home Suivi Élec..."
        );

        await MigrationAPI.downloadTemplatesYAML([]);

        Toast.success(
          "Fichier template_sensors.yaml exporté. Nécessite une intégration de type Riemann pour les calculs.",
          0
        );
      }

      return true;
    } catch (error) {
      console.error("[TemplateSensorExporter] Erreur export templates:", error);
      Toast.error(error.message || "Erreur export templates");
      return false;
    }
  }

  /**
   * Récupère le YAML templates pour aperçu.
   */
  static async preview(sensors) {
    try {
      const yaml = await MigrationAPI.previewTemplates(sensors);
      return yaml;
    } catch (error) {
      console.error("[TemplateSensorExporter] Erreur preview templates:", error);
      Toast.error("Erreur preview templates");
      return null;
    }
  }
}
