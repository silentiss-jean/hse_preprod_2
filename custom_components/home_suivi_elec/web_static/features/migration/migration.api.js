// features/migration/migration.api.js

"use strict";

import { httpClient } from "../../shared/api/httpClient.js";
import { ENDPOINTS } from "../../shared/constants.js";
import { fetchAuthJSON } from "../../core/auth.js";


const MIGRATION_ENDPOINT = ENDPOINTS.MIGRATION; // "/api/home_suivi_elec/migration"

export class MigrationAPI {
  // Télécharge utility_meter.yaml
  static async downloadUtilityMeterYAML(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=utility_meter`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "utility_meter.yaml";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return true;
  }

  // Télécharge template_sensors.yaml
  static async downloadTemplatesYAML(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=templates`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "template_sensors.yaml";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return true;
  }

  // Télécharge cost_sensors.yaml
  static async downloadCostYAML(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=cost`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "cost_sensors.yaml";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return true;
  }

  // Preview cost_sensors.yaml
  static async previewCostYAML(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=cost&preview=1`;
    return httpClient.get(url);
  }

  // Preview utility_meter.yaml
  static async previewUtilityMeter(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=utility_meter&preview=1`;
    return httpClient.get(url);
  }

  // Preview template_sensors.yaml
  static async previewTemplates(_sensors) {
    const url = `${MIGRATION_ENDPOINT}?type=templates&preview=1`;
    return httpClient.get(url);
  }

  // Création automatique des helpers utility_meter
  static async createHelpersAuto(sensors, cycles) {
    return httpClient.post(MIGRATION_ENDPOINT, {
      action: "create_helpers_auto",
      sensors: sensors ?? [],
      cycles: cycles ?? [],
    });
  }

  // Validation des helpers créés
  static async validateHelpers(helperNames) {
    return httpClient.post(MIGRATION_ENDPOINT, {
      action: "validate_helpers",
      helpers: helperNames ?? [],
    });
  }
}


//TO DELETE
//export async function generateCostSensors(prixData = {}) {
//  const result = await fetchAuthJSON(
//    "/api/home_suivi_elec/config/generate_cost_sensors",
//    {
//      method: "POST",
//      body: JSON.stringify(prixData),
//    }
//  );

//  if (result?.error) {
//    throw new Error(result.message || "Erreur lors de la génération");
//  }

//  return result.data;
//}