// features/migration/exporters/autoHelper.js

"use strict";

import { MigrationAPI } from "../migration.api.js";
import { Toast } from "../../../shared/components/Toast.js";
import { MIGRATION_CYCLES } from "../../../shared/constants.js";
import { HelperValidator } from "../validators/helperValidator.js";

/**
 * Exporteur pour la création automatique de helpers via l'API backend.
 *
 * Remarque : nécessite que le backend implémente bien
 *  - action "create_helpers_auto"
 *  - action "validate_helpers"
 * sur l'endpoint MIGRATION.
 */
export class AutoHelperExporter {
  /**
   * Crée automatiquement les helpers utility_meter via l’API.
   *
   * @param {Array|null} sensors Capteurs sélectionnés (optionnel si le backend lit la sélection)
   * @param {Array|null} selectedCycles Liste de cycles (daily, weekly, ...)
   * @param {Function|null} progressCallback (progress, currentStep, totalSteps) - réservé pour plus tard
   * @returns {Promise<{success:boolean, created:string[], errors:string[]}>}
   */
  static async createAuto(sensors, selectedCycles, progressCallback) {
    const count = sensors?.length ?? 0;
    const hasExplicitSelection = count > 0;

    // Cycles par défaut si rien n’est sélectionné
    const cycles =
      selectedCycles && selectedCycles.length > 0
        ? selectedCycles
        : Object.values(MIGRATION_CYCLES);

    const totalHelpersEstimate = hasExplicitSelection
      ? count * cycles.length
      : null;

    if (hasExplicitSelection) {
      Toast.info(
        `Création automatique de ${totalHelpersEstimate} helpers ` +
          `(${count} capteurs × ${cycles.length} cycles)...`
      );
    } else {
      Toast.info(
        "Création automatique de helpers utility_meter pour les capteurs sélectionnés " +
          "dans Home Suivi Élec..."
      );
    }

    try {
      const result = await MigrationAPI.createHelpersAuto(
        sensors ?? [],
        cycles,
        progressCallback
      );

      if (!result || !result.success) {
        const message =
          result && result.errors && result.errors.length
            ? result.errors.join(", ")
            : "Erreur inconnue";
        Toast.error(`Échec création helpers : ${message}`);
        return result || { success: false, created: [], errors: [message] };
      }

      Toast.success(
        `${result.created.length} helpers créés avec succès. ` +
          "Rechargez l’interface pour les voir.",
        0
      );

      // Validation optionnelle des helpers créés
      if (result.created && result.created.length > 0) {
        const validation = await AutoHelperExporter.validate(result.created);
        if (!validation.valid) {
          Toast.warning(
            "Certains helpers ne sont pas encore détectés. " +
              "Patientez quelques secondes puis rechargez."
          );
        }
      }

      return result;
    } catch (error) {
      console.error("[AutoHelperExporter] Erreur création auto:", error);
      Toast.error(error.message || "Erreur création helpers");
      return { success: false, created: [], errors: [error.message] };
    }
  }

  /**
   * Valide que les helpers existent bien côté backend.
   *
   * @param {string[]} helperNames
   * @returns {Promise<{valid:boolean, details:Object}>}
   */
  static async validate(helperNames) {
    try {
      return await HelperValidator.validateHelpers(helperNames);
    } catch (error) {
      console.error("[AutoHelperExporter] Erreur validation helpers:", error);
      return { valid: false, details: {} };
    }
  }



  /**
   * Estime le temps de création (petit helper UX).
   *
   * @param {number} sensorCount
   * @param {number} cycleCount
   * @returns {string} ex: "5s" ou "1m 20s"
   */
  static estimateTime(sensorCount, cycleCount) {
    const totalHelpers = (sensorCount || 0) * (cycleCount || 0);
    // approx 0.5s par helper (à ajuster après mesure réelle)
    const seconds = Math.ceil(totalHelpers * 0.5);
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  }
}
