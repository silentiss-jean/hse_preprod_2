// features/migration/validators/helperValidator.js
"use strict";

import { MigrationAPI } from "../migration.api.js";

/**
 * Validator pour les helpers créés (utility_meter, etc.).
 * Interroge le backend pour savoir si les helpers existent bien.
 */
export class HelperValidator {
  /**
   * Valide que les helpers existent bien côté backend.
   *
   * @param {string[]} helperNames  Liste de noms de helpers (entity_id ou id logique selon backend)
   * @returns {Promise<{valid:boolean, details:Object}>}
   */
  static async validateHelpers(helperNames) {
    if (!Array.isArray(helperNames) || helperNames.length === 0) {
      return { valid: false, details: {} };
    }

    try {
      const result = await MigrationAPI.validateHelpers(helperNames);
      // On attend un format { valid: bool, details: { name: bool, ... } }
      if (!result || typeof result.valid !== "boolean") {
        return { valid: false, details: {} };
      }
      return result;
    } catch (error) {
      console.error("[HelperValidator] Erreur validation helpers:", error);
      return { valid: false, details: {} };
    }
  }
}
