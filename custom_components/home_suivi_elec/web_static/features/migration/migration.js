// features/migration/migration.js
"use strict";

import { migrationState } from "./migration.state.js";
import { MigrationView } from "./migration.view.js";
import { AutoHelperExporter } from "./exporters/autoHelper.js";

export class Migration {
  constructor() {
    this.state = migrationState;
    this.view = new MigrationView(this);
  }

  async init() {
    console.log("[migration] module initialized");
    await this.loadSensorsFromConfig();
    this.view.render();
  }

  async loadSensorsFromConfig() {
    try {
      const configState = window.configurationState;
      if (configState && typeof configState.getSelectedSensors === "function") {
        const sensors = configState.getSelectedSensors();
        this.state.setSelectedSensors(sensors);
      }
    } catch (error) {
      console.error(
        "[migration] Erreur chargement capteurs depuis configuration:",
        error
      );
    }
  }

  /**
   * Normalise les capteurs en tableau pour les exports (utile surtout pour les logs).
   */
  getSelectedSensorsSafe() {
    if (typeof this.state.getSelectedSensors === "function") {
      const sensors = this.state.getSelectedSensors() || [];
      return Array.isArray(sensors) ? sensors : Object.values(sensors);
    }
    return [];
  }

  async exportUtilityMeter() {
    const sensors = this.getSelectedSensorsSafe();
    const { UtilityMeterExporter } = await import("./exporters/utilityMeter.js");
    return UtilityMeterExporter.export(sensors);
  }

  async previewUtilityMeter() {
    const sensors = this.getSelectedSensorsSafe();
    const { UtilityMeterExporter } = await import("./exporters/utilityMeter.js");
    return UtilityMeterExporter.preview(sensors);
  }

  async exportTemplates() {
    const sensors = this.getSelectedSensorsSafe();
    const { TemplateSensorExporter } = await import(
      "./exporters/templateSensor.js"
    );
    return TemplateSensorExporter.export(sensors);
  }

  async previewTemplates() {
    const sensors = this.getSelectedSensorsSafe();
    const { TemplateSensorExporter } = await import(
      "./exporters/templateSensor.js"
    );
    return TemplateSensorExporter.preview(sensors);
  }

  // Option 3 : helpers auto via backend
  async createHelpersAuto(progressCallback) {
    const sensors = this.getSelectedSensorsSafe();
    const cycles =
      (this.state.getSelectedCycles && this.state.getSelectedCycles()) || null;

    return AutoHelperExporter.createAuto(sensors, cycles, progressCallback);
  }
}

// Instance globale
export const migration = new Migration();

/**
 * Point d’entrée attendu par router.js:
 * import('../features/migration/migration.js') → loadMigration()
 */
export async function loadMigration() {
  await migration.init();
}
