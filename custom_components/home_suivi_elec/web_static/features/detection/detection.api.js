"use strict";

const BASE_URL = "/api/home_suivi_elec";

export async function getSensorsDetection() {
    const resp = await fetch(`${BASE_URL}/get_sensors_health`);
    if (!resp.ok) {
        throw new Error(`Erreur API get_sensors_health: ${resp.status}`);
    }
    const json = await resp.json();

    // json = { success: true, sensors: { entity_id: { ... } } }

    const sensorsArray = Object.entries(json.sensors || {}).map(
        ([entity_id, payload]) => ({
            entity_id,
            ...payload,
        })
    );

    // On renvoie dans le format attendu par loadDetection :
    // data.selected = tableau de capteurs
    return {
        selected: sensorsArray,
        alternatives: [],
        reference_sensor: null,
    };
}
