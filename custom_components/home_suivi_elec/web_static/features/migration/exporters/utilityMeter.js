// features/migration/exporters/utilityMeter.js

"use strict";

import { MigrationAPI } from "../migration.api.js";
import { Toast } from "../../../shared/components/Toast.js";
import { MIGRATION_CYCLES } from "../../../shared/constants.js";

export class UtilityMeterExporter {
  /**
   * Lance l'export utility_meter.yaml.
   *
   * Pour l’instant, la sélection réelle est faite côté backend (Storage API),
   * donc sensors est ignoré par l’API, mais on garde la signature pour compat.
   *
   * Si sensors est vide ou null, on s’appuie sur la sélection stockée côté backend.
   */
  static async export(sensors) {
    try {
      const count = sensors?.length ?? 0;
      const hasExplicitSelection = count > 0;

      if (hasExplicitSelection) {
        // Cas futur / avancé : le frontend fournit explicitement une sélection.
        const cyclesCount = Object.keys(MIGRATION_CYCLES).length;
        const totalHelpers = count * cyclesCount;

        Toast.info(`Export de ${count} capteurs en utility_meter...`);
        await MigrationAPI.downloadUtilityMeterYAML(sensors);

        Toast.success(
          `${totalHelpers} utility_meters exportés. ` +
            "Copiez le contenu dans configuration.yaml et redémarrez Home Assistant.",
          0 // persistant
        );
      } else {
        // Cas actuel : aucune liste explicite, on laisse le backend lire la sélection
        // depuis le Storage API (même logique que le preview + bouton Télécharger).
        Toast.info(
          "Export des capteurs sélectionnés en utility_meter à partir de la configuration Home Suivi Élec..."
        );

        // On passe un tableau vide, le backend utilise alors la sélection persistée.
        await MigrationAPI.downloadUtilityMeterYAML([]);

        Toast.success(
          "Fichier utility_meter.yaml exporté. Copiez le contenu dans configuration.yaml et redémarrez Home Assistant.",
          0 // persistant
        );
      }

      return true;
    } catch (error) {
      console.error("[UtilityMeterExporter] Erreur export utility_meter:", error);
      Toast.error(error.message || "Erreur export utility_meter");
      return false;
    }
  }

  /**
   * Récupère le YAML utility_meter pour un aperçu (modale, textarea, etc.).
   */
  static async preview(sensors) {
    try {
      const yaml = await MigrationAPI.previewUtilityMeter(sensors);
      return yaml;
    } catch (error) {
      console.error("[UtilityMeterExporter] Erreur preview utility_meter:", error);
      Toast.error("Erreur preview utility_meter");
      return null;
    }
  }
}
