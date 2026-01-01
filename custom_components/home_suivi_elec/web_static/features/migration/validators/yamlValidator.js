// features/migration/validators/yamlValidator.js
"use strict";

/**
 * Validation basique de YAML côté frontend.
 * Pour l'instant : vérifie juste que le texte n'est pas vide.
 */
export class YamlValidator {
  /**
   * Retourne true si le YAML semble non vide.
   *
   * @param {string} text
   * @returns {boolean}
   */
  static isValidYaml(text) {
    if (typeof text !== "string") {
      return false;
    }
    const trimmed = text.trim();
    if (trimmed.length === 0) {
      return false;
    }

    // Petit heuristique: la plupart de nos exports commencent par une clé de haut niveau
    // (utility_meter:, template:, sensor:). On peut vérifier qu'il y a au moins un `:` sur une ligne.
    return trimmed.split("\n").some((line) => line.includes(":"));
  }
}