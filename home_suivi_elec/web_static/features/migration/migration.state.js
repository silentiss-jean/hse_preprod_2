// features/migration/migration.state.js
"use strict";

export class MigrationState {
  constructor() {
    this.selectedSensors = [];
    this.selectedCycles = ["daily", "weekly", "monthly", "yearly"];
    this.exportInProgress = false;
  }

  // Capteurs sélectionnés
  setSelectedSensors(sensors) {
    this.selectedSensors = sensors || [];
  }

  getSelectedSensors() {
    return this.selectedSensors;
  }

  // Cycles sélectionnés
  setSelectedCycles(cycles) {
    this.selectedCycles = cycles || [];
  }

  getSelectedCycles() {
    return this.selectedCycles;
  }

  // Flag "export en cours"
  setExportInProgress(inProgress) {
    this.exportInProgress = inProgress;
  }

  isExportInProgress() {
    return this.exportInProgress;
  }
}

// ⚠️ Export *nommé* utilisé dans migration.js
export const migrationState = new MigrationState();
